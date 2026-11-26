# -*- coding: utf-8 -*-
"""低支持度模板能不能救回缺失反应？（定向筛查，不重挖）

数据：
  reports/mined_forward_templates_full.jsonl（287,557 条，含 support）
  缺失反应来自按生产配置建的候选表

两步：
  1. 产物侧子结构预筛：模板产物片段必须是真产物的子结构（必要不充分）
  2. 真实反应应用：对通过预筛的模板跑 RDKit 反应，看是否产出真产物

用法：
  python tools\\screen_gap_templates.py --n 100
  python tools\\screen_gap_templates.py --n 100 --min-support 1 --max-support 4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
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
_ELEM = re.compile(r"\[([A-Za-z]{1,2})")
_ORGANIC = {"C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "B", "Si", "Se"}


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def load_templates(lo, hi):
    out = []
    t0 = time.time()
    for line in open(FULL, encoding="utf-8"):
        d = json.loads(line)
        s = int(d.get("support") or 0)
        if s < lo or s > hi:
            continue
        t = d.get("template") or ""
        if ">>" not in t:
            continue
        right = t.split(">>", 1)[1]
        frags = [f for f in right.split(".") if f]
        mols = []
        for f in frags:
            m = Chem.MolFromSmarts(f)
            if m is not None and m.GetNumAtoms() > 0:
                mols.append(m)
        if not mols:
            continue
        elems = set()
        for e in _ELEM.findall(right):
            e = e[:1].upper() + e[1:].lower()
            if e in _ORGANIC:
                elems.add(e)
        out.append((t, s, mols, elems))
    print("低支持度模板 %d 条（support %d-%d，%.0f s）"
          % (len(out), lo, hi, time.time() - t0), flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--min-support", type=int, default=1)
    ap.add_argument("--max-support", type=int, default=4)
    ap.add_argument("--table", default=str(CT.DEFAULT_DIR / "candidates_cli.parquet"))
    ap.add_argument("--meta", default=str(CT.DEFAULT_DIR / "meta_cli.json"))
    a = ap.parse_args()

    tpls = load_templates(a.min_support, a.max_support)

    df, meta = CT.load(parquet=a.table, meta=CT.load_meta(a.meta),
                       columns=["rid", "want", "n_pos", "r1", "r2"])
    rxn = df.groupby("rid", sort=False).first().reset_index()
    miss = rxn[rxn["n_pos"] == 0].reset_index(drop=True)
    step = max(1, len(miss) // a.n)
    sample = miss.iloc[::step].head(a.n).reset_index(drop=True)
    print("缺失 %d 条，抽样 %d 条" % (len(miss), len(sample)), flush=True)

    n_rescue = 0
    rescue_support = []
    details = []
    rescues = []
    t0 = time.time()
    for i, row in sample.iterrows():
        want = canon(row["want"])
        mw = Chem.MolFromSmiles(want) if want else None
        if mw is None:
            continue
        wel = {a_.GetSymbol() for a_ in mw.GetAtoms()}
        r1 = Chem.MolFromSmiles(row["r1"]) if row["r1"] else None
        r2 = Chem.MolFromSmiles(row["r2"]) if row["r2"] else None
        if r1 is None:
            continue

        # 1) 产物侧预筛
        cand = []
        for t, s, mols, elems in tpls:
            if not elems <= wel:
                continue
            if any(mw.HasSubstructMatch(m) for m in mols):
                cand.append((t, s))
        # 2) 真实应用
        hit = None
        for t, s in cand:
            try:
                rxn = AllChem.ReactionFromSmarts(t)
            except Exception:
                continue
            args = (r1,) if r2 is None else (r1, r2)
            for order in ([args] if r2 is None else [args, (r2, r1)]):
                try:
                    outs = rxn.RunReactants(order)
                except Exception:
                    continue
                for prod in outs:
                    for pm in prod:
                        try:
                            Chem.SanitizeMol(pm)
                            cs = Chem.MolToSmiles(pm)
                        except Exception:
                            continue
                        if cs == want:
                            hit = (t, s)
                            break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            n_rescue += 1
            rescue_support.append(hit[1])
            rescues.append({"rid": int(row["rid"]), "support": int(hit[1]),
                            "template": hit[0], "want": want,
                            "r1": row["r1"], "r2": row["r2"]})
            if len(details) < 10:
                details.append((row["rid"], hit[1], hit[0][:70]))
        if (i + 1) % 10 == 0:
            print("  ...%d/%d  救回 %d  %.0f s"
                  % (i + 1, len(sample), n_rescue, time.time() - t0), flush=True)

    print("\n结果：%d / %d 条被低支持度模板救回（%.1f%%）"
          % (n_rescue, len(sample), 100.0 * n_rescue / max(1, len(sample))))
    if rescue_support:
        import statistics
        print("救回模板的支持度：中位 %d / 最大 %d"
              % (int(statistics.median(rescue_support)), max(rescue_support)))
    for rid, s, t in details:
        print("  rid=%-6s support=%-3d %s" % (rid, s, t))
    if rescues:
        dump = ROOT / "_diag" / ("screen_rescues_%d.json" % len(sample))
        dump.write_text(json.dumps(rescues, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        print("救回明细 -> %s" % dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
