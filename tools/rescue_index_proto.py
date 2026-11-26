# -*- coding: utf-8 -*-
"""抢救层检索原型：用底物原子环境索引，从低支持度模板里筛出可能匹配的。

思路（不依赖产物，生产可用）：
  模板反应物侧的每个原子 → (元素, H数, 度数, 芳香性) 特征
  底物原子 → 同样的特征（具体值）
  模板可匹配的必要条件：模板特征多重集 ⊆ 底物特征多重集
  通过后再跑真实 RDKit 反应确认。

用法：
  python tools\\rescue_index_proto.py --n 20
  python tools\\rescue_index_proto.py --n 20 --max-support 4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import candidate_table as CT  # noqa: E402

FULL = ROOT / "reports" / "mined_forward_templates_full.jsonl"
_NUM2SYM = {6: "C", 7: "N", 8: "O", 9: "F", 15: "P", 16: "S", 17: "Cl",
            35: "Br", 53: "I", 5: "B", 14: "Si", 34: "Se"}
# 两字母元素必须白名单匹配：否则 [CH2:10]、[NH2;D1] 会被当成 "Ch"、"Nh"
_TWO = ("Cl", "Br", "Si", "Se", "Na", "Li", "Mg", "Ca", "Fe", "Cu", "Zn",
        "Pd", "Ni", "Pt", "Al", "Sn", "Mn", "Co", "Cr", "Mo", "Ag", "Au",
        "Hg", "Pb", "As", "Sb", "Bi", "Te", "Ti", "Zr")
_BRACKET = re.compile(r"\[([^\]]+)\]")
_BARE = re.compile(r"Cl|Br|[BCNOPSFIcnops]")


def atom_feat(tok: str):
    """SMARTS 原子 token -> (element, H, degree, aromatic) 或 None。"""
    elem = None
    m = re.match(r"#(\d+)", tok)
    if m:
        elem = _NUM2SYM.get(int(m.group(1)))
    else:
        for s in _TWO:
            if tok.startswith(s):
                elem = s
                break
        if elem is None:
            m = re.match(r"[A-Za-z]", tok)
            if m:
                elem = m.group(0)
    if not elem:
        return None
    arom = 1 if elem[0].islower() else 0
    elem = elem[0].upper() + elem[1:].lower()
    mh = re.search(r"H(\d*)", tok)
    hv = int(mh.group(1) or 1) if mh else -1
    md = re.search(r"D(\d)", tok)
    dv = int(md.group(1)) if md else -1
    return (elem, hv, dv, arom)


def side_features(smarts: str) -> Counter:
    c = Counter()
    for tok in _BRACKET.findall(smarts):
        f = atom_feat(tok)
        if f:
            c[f] += 1
    # 去掉方括号后再看裸原子
    bare = _BRACKET.sub(" ", smarts)
    for tok in _BARE.findall(bare):
        c[(tok[0].upper() + tok[1:].lower(), -1, -1, 1 if tok[0].islower() else 0)] += 1
    return c


def mol_features(m: Chem.Mol) -> Counter:
    c = Counter()
    for a in m.GetAtoms():
        c[(a.GetSymbol(), a.GetTotalNumHs(), a.GetDegree(),
           1 if a.GetIsAromatic() else 0)] += 1
    return c


def viable(tpl: Counter, sub: Counter) -> bool:
    for f, n in tpl.items():
        have = sub.get(f, 0)
        if have >= n:
            continue
        # 模板未指定的 H/度数 视为通配：退化成 (元素, 芳香性) 计数
        e, h, d, ar = f
        if h < 0 or d < 0:
            tot = sum(v for k, v in sub.items()
                      if k[0] == e and k[3] == ar)
            if tot < n:
                return False
        else:
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--max-support", type=int, default=4)
    ap.add_argument("--table", default=str(CT.DEFAULT_DIR / "candidates_cli.parquet"))
    ap.add_argument("--meta", default=str(CT.DEFAULT_DIR / "meta_cli.json"))
    a = ap.parse_args()

    t0 = time.time()
    tpls = []
    for line in open(FULL, encoding="utf-8"):
        d = json.loads(line)
        s = int(d.get("support") or 0)
        if not (1 <= s <= a.max_support):
            continue
        t = d.get("template") or ""
        if ">>" not in t:
            continue
        left = t.split(">>", 1)[0]
        feats = side_features(left)
        if not feats:
            continue
        tpls.append((t, s, feats))
    print("模板 %d 条（support 1-%d），建索引 %.0f s"
          % (len(tpls), a.max_support, time.time() - t0), flush=True)

    df, meta = CT.load(parquet=a.table, meta=CT.load_meta(a.meta),
                       columns=["rid", "want", "n_pos", "r1", "r2"])
    rxn = df.groupby("rid", sort=False).first().reset_index()
    miss = rxn[rxn["n_pos"] == 0].reset_index(drop=True)
    step = max(1, len(miss) // a.n)
    sample = miss.iloc[::step].head(a.n).reset_index(drop=True)
    print("缺失 %d 条，抽样 %d" % (len(miss), len(sample)), flush=True)

    n_resc = 0
    t_screen = t_apply = 0.0
    for i, row in sample.iterrows():
        r1 = Chem.MolFromSmiles(row["r1"]) if row["r1"] else None
        r2 = Chem.MolFromSmiles(row["r2"]) if row["r2"] else None
        if r1 is None:
            continue
        sub = mol_features(r1)
        if r2 is not None:
            sub += mol_features(r2)
        want = Chem.MolToSmiles(Chem.MolFromSmiles(row["want"])) if row["want"] else ""

        s0 = time.time()
        cand = [(t, s) for t, s, f in tpls if viable(f, sub)]
        t_screen += time.time() - s0

        s1 = time.time()
        hit = False
        n_prod = set()
        for t, s in cand:
            try:
                rxn_obj = AllChem.ReactionFromSmarts(t)
            except Exception:
                continue
            args = (r1,) if r2 is None else (r1, r2)
            for order in ([args] if r2 is None else [args, (r2, r1)]):
                try:
                    outs = rxn_obj.RunReactants(order)
                except Exception:
                    continue
                for prod in outs:
                    for pm in prod:
                        try:
                            Chem.SanitizeMol(pm)
                            cs = Chem.MolToSmiles(pm)
                            n_prod.add(cs)
                            if cs == want:
                                hit = True
                                break
                        except Exception:
                            continue
                    if hit:
                        break
                if hit:
                    break
            if hit:
                break
        t_apply += time.time() - s1
        n_resc += hit
        print("  %2d/%d rid=%-6s 候选模板 %5d 新增产物 %5d  救回 %s  筛查 %.2fs 应用 %.2fs"
              % (i + 1, len(sample), row["rid"], len(cand), len(n_prod),
                 "Y" if hit else "-", time.time() - s0, time.time() - s1), flush=True)

    n = len(sample)
    print("\n救回 %d / %d（%.1f%%）；筛查总 %.1f s（%.2f s/反应）；应用总 %.1f s"
          % (n_resc, n, 100.0 * n_resc / max(1, n), t_screen, t_screen / max(1, n), t_apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
