# -*- coding: utf-8 -*-
r"""②-1 评估口径与基线：从 ORD 抽逆模板，能否在【留出测试集】上复现反应？

口径（先说清再测）
--------------------------------------------------------------------
数据 : ord_dataset-1158e351…parquet（1,771,032 条，全带原子映射）
分割 : 前 90% = 训练集（抽模板用），后 10% = 留出测试集（只评估，绝不参与抽模板）
       -> 避免"用同一条反应测自己抽的模板"的信息泄露
测试 : 对测试集里每条反应，取其【反应物】当已知条件，看模板能否生成出【真实产物】
       - 单模板命中（1 步）就算命中
       - 报告 recall = 命中数 / 可评估反应数
可评估 : 测试反应必须有映射（否则连反应中心都定不了）
基线 : ① 现有 SmartReact 9,770 条【反转】模板（就是我们怀疑不够的那套）
       ② 本轮新抽的逆模板

用法: python retro_extract_eval.py --baseline --n 2000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, r"D:\TCMAI\src")

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdChemReactions  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from build_purchasable_blocks import split_cx, canon_key  # noqa: E402

RDLogger.DisableLog("rdApp.*")

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
OUT = STAGE / "reports" / "retro_extract_eval.json"


def parse_rxn(cx):
    """CXSMILES -> (反应物SMILES列表, 产物SMILES列表)，保留映射号。"""
    sp = split_cx(cx)
    if sp is None:
        return None
    lhs, _mid, rhs = sp
    rs = [p.strip() for p in lhs.split(".") if p.strip()]
    ps = [p.strip() for p in rhs.split(".") if p.strip()]
    if not rs or not ps:
        return None
    return rs, ps


def fetch_test(n, offset_frac=0.9):
    """从留出区间取 n 条可评估的测试反应（带映射）。"""
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    total = con.execute(
        f"SELECT num_rows FROM parquet_file_metadata('{BIG.as_posix()}')").fetchone()[0]
    off = int(total * offset_frac)
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') OFFSET {off} LIMIT {n * 3}"
    ).fetchall()
    out = []
    stat = Counter()
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            stat["protobuf失败"] += 1
            continue
        cx = next((i.value for i in rxn.identifiers
                   if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value),
                  None)
        if not cx:
            stat["无CXSMILES"] += 1
            continue
        pr = parse_rxn(cx)
        if pr is None:
            stat["段数异常"] += 1
            continue
        rs, ps = pr
        stat["有CXSMILES"] += 1
        # 简化：只取【单产物 + 双反应物】的干净反应，便于判命中
        if len(ps) != 1:
            stat["多产物跳过"] += 1
            continue
        rs = [r for r in rs if not r.startswith("[") or True]
        if len(rs) < 1 or len(rs) > 3:
            stat["反应物数不在1..3"] += 1
            continue
        if ":" not in ps[0]:
            stat["产物无映射"] += 1
            continue
        out.append({"reactants": rs, "product": ps[0], "cx": cx})
        if len(out) >= n:
            break
    print(f"  取测试反应 {len(out):,} 条（起点 {off:,}）  筛选统计 {dict(stat)}")
    return out


def norm_nomap(smi):
    """去映射 + canonical；失败返回 None。"""
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m)


# ---------------------------------------------------------------- 基线：SmartReact 反转模板
def load_smartreact_retro():
    """返回 [(name, compiled_rxn)]，逆方向（产物>>底物）。"""
    path = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
    out, bad = [], 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        f = line.split("\t")
        if len(f) != 5:
            continue
        name, _tid, _ex, smarts, _cats = f
        if ">>" not in smarts:
            continue
        lhs, rhs = smarts.split(">>", 1)
        try:
            rx = rdChemReactions.ReactionFromSmarts(f"{rhs}>>{lhs}")
        except Exception:
            bad += 1
            continue
        if rx is None or rx.GetNumReactantTemplates() != 1:
            continue
        out.append((name, rx))
    print(f"  SmartReact 反转模板 {len(out):,} 条（编译失败 {bad}）")
    return out


def eval_templates(templates, tests, label, limit_each=4000):
    """模板套测试集：产物能否由反应物生成。返回命中明细。"""
    t0 = time.time()
    hit = 0
    n = 0
    hit_by = Counter()
    fails = []
    for i, t in enumerate(tests):
        m = Chem.MolFromSmiles(t["product"])
        if m is None:
            continue
        n += 1
        want = norm_nomap(t["product"])
        got_hit = False
        for name, rx in templates:
            try:
                res = rx.RunReactants((m,))
            except Exception:
                continue
            if not res:
                continue
            for tup in res[:limit_each]:
                try:
                    prods = []
                    ok = True
                    for pm in tup:
                        Chem.SanitizeMol(pm)
                        cs = norm_nomap(Chem.MolToSmiles(pm))
                        if not cs:
                            ok = False
                            break
                        prods.append(cs)
                    if not ok:
                        continue
                except Exception:
                    continue
                if want in prods:
                    hit += 1
                    hit_by[name] += 1
                    got_hit = True
                    break
            if got_hit:
                break
        if not got_hit and len(fails) < 12:
            fails.append(t["product"][:90])
        if n % 200 == 0:
            print(f"     {label}: {n}/{len(tests)} 命中 {hit} ({hit/n*100:.1f}%)"
                  f"  {time.time()-t0:.0f}s", flush=True)
    print(f"  [{label}] 可评估 {n:,}  命中 {hit:,}  recall = {hit/max(n,1)*100:.2f}%"
          f"  ({time.time()-t0:.0f}s)")
    return {"label": label, "n": n, "hit": hit, "recall": round(hit / max(n, 1), 4),
            "top_hit_types": dict(hit_by.most_common(10)), "miss_examples": fails}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--baseline", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    print("=" * 92)
    print("②-1 逆模板评估：留出测试集 + SmartReact 反转模板基线")
    print("=" * 92)

    tests = fetch_test(args.n)
    res = {"n_tests": len(tests), "results": []}
    if args.baseline:
        tmpl = load_smartreact_retro()
        r = eval_templates(tmpl, tests, "SmartReact反转模板")
        res["results"].append(r)
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n-> {OUT.name}   总耗时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
