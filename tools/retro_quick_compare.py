# -*- coding: utf-8 -*-
r"""快速对照：新抽逆模板 vs SmartReact 反转模板（同一测试集、同一命中口径）。

只测较少目标（默认 60），因为 SmartReact 反转模板在每条目标上要全跑 9770 条，很慢。
用法: python retro_quick_compare.py [目标数]
"""
import json, sys, time
from collections import Counter
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    sys.path.insert(0, str(_p))

BIG = STAGE / "ord-data" / "data" / "11" / "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
CLUSTERED = STAGE / "reports" / "retro_templates_clustered.jsonl"
OUT = STAGE / "reports" / "retro_quick_compare.json"

import duckdb
from rdkit import Chem, RDLogger
from rdkit.Chem import rdChemReactions
from ord_schema.proto import reaction_pb2
RDLogger.DisableLog("rdApp.*")

n_test = int(sys.argv[1]) if len(sys.argv) > 1 else 60
TEST_FRAC = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
t0 = time.time()

def norm(smi):
    m = Chem.MolFromSmiles(smi)
    if m is None: return None
    for a in m.GetAtoms(): a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m)

# 测试集（全量 50% 处，不与训练集前 6 万条重叠）
con = duckdb.connect(); con.execute("SET memory_limit='1500MB'"); con.execute("SET threads=2")
total = con.execute(f"SELECT num_rows FROM parquet_file_metadata('{BIG.as_posix()}')").fetchone()[0]
off = int(total * TEST_FRAC)
rows = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') OFFSET {off} LIMIT {n_test*3}").fetchall()
tests = []
for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    try: rxn.ParseFromString(blob)
    except Exception: continue
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value), None)
    if not cx: continue
    body = cx.split("|",1)[0] if "|" in cx else cx
    parts = body.split(">")
    if len(parts) == 2: lhs, rhs = parts
    elif len(parts) == 3: lhs, _m, rhs = parts
    else: continue
    ps = [p for p in rhs.split(".") if p.strip()]
    rs = [p for p in lhs.split(".") if p.strip()]
    if len(ps) != 1 or not (1 <= len(rs) <= 3) or ":" not in ps[0]: continue
    tests.append({"reactants": rs, "product": ps[0]})
    if len(tests) >= n_test: break
print(f"测试反应 {len(tests)} 条（起点 {off:,}）")

def build_matcher(pairs):
    def match(prod, want):
        m = Chem.MolFromSmiles(prod)
        if m is None: return False
        for tpl, rx, q in pairs:
            try:
                if q is not None and not m.HasSubstructMatch(q): continue
            except Exception: continue
            try: res = rx.RunReactants((m,))
            except Exception: continue
            for tup in res[:20]:
                try:
                    got, good = set(), True
                    for pm in tup:
                        Chem.SanitizeMol(pm)
                        c = norm(Chem.MolToSmiles(pm))
                        if not c: good = False; break
                        got.add(c)
                except Exception:
                    good = False
                # ★ 口径：模板生成的前体必须【都被真实反应物覆盖】（子集判据）。
                #   用==会偏严：真实 ORD 反应的反应物列里常带未参与反应的试剂/溶剂，
                #   模板不会生成它们，== 永远不成立 -> 基线全 0 就是被这个口径坑的。
                if good and got and got <= want: return True
        return False
    return match

# 新模板
new_pairs = []
for line in open(CLUSTERED, encoding="utf-8"):
    line = line.strip()
    if not line: continue
    r = json.loads(line)
    try:
        rx = rdChemReactions.ReactionFromSmarts(r["template"])
        if rx is None or rx.GetNumReactantTemplates() != 1: continue
        new_pairs.append((r["template"], rx, rx.GetReactantTemplate(0)))
    except Exception: continue
print(f"新模板 {len(new_pairs):,} 条")

# 基线
base_pairs = []
tp = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
for line in tp.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
    f = line.split("\t")
    if len(f) != 5 or ">>" not in f[3]: continue
    lhs, rhs = f[3].split(">>", 1)
    try:
        rx = rdChemReactions.ReactionFromSmarts(f"{rhs}>>{lhs}")
        if rx is None or rx.GetNumReactantTemplates() != 1: continue
        base_pairs.append((f[0], rx, rx.GetReactantTemplate(0)))
    except Exception: continue
print(f"基线 SmartReact 反转模板 {len(base_pairs):,} 条")

m_new, m_base = build_matcher(new_pairs), build_matcher(base_pairs)
hit_new = hit_base = n_ok = 0
t1 = time.time()
for i, t in enumerate(tests):
    want = {norm(r) for r in t["reactants"]}; want.discard(None)
    if not want: continue
    n_ok += 1
    if m_new(t["product"], want): hit_new += 1
    if m_base(t["product"], want): hit_base += 1
    print(f"   {i+1}/{len(tests)}  新 {hit_new}  基线 {hit_base}  ({time.time()-t1:.0f}s)", flush=True)

res = {"criterion": "generated_precursors_subset_of_real_reactants",
       "n_test": n_ok, "test_frac": TEST_FRAC,
       "new_templates": len(new_pairs), "new_hit": hit_new,
       "new_recall": round(hit_new/max(n_ok,1), 4),
       "baseline_templates": len(base_pairs), "baseline_hit": hit_base,
       "baseline_recall": round(hit_base/max(n_ok,1), 4),
       "elapsed_sec": round(time.time()-t0, 1)}
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print()
print("=" * 88)
print(f"测试 {n_ok} 条   ★ 新抽逆模板 recall = {res['new_recall']*100:.1f}%"
      f"   SmartReact反转模板 recall = {res['baseline_recall']*100:.1f}%")
print("=" * 88)
print(f"-> {OUT.name}   {res['elapsed_sec']}s")
