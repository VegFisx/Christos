# -*- coding: utf-8 -*-
r"""★ P0.5：用原子映射精确定位反应物对，测【准确】覆盖率 ★

之前（validate_ord_coverage.py / control_ord_coverage.py）用启发式猜反应物，
导致覆盖率是下界且口径有偏。现在改为：
  1. 解析 CXSMILES（支持两段式和三段式）
  2. 产物里有原子映射 -> 反查哪些底物组分的原子进了产物
  3. 恰好 2 个组分贡献 -> 那 2 个就是【真反应物】（纯客观，无启发式）
  4. 喂进 enumerate_pair，看产物能否复现

数据源：ord_dataset-1158e351….parquet（177 万条，全部带原子映射）

用法: python measure_coverage_mapped.py [抽样数]
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
REPORTS = STAGE / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
OUT = REPORTS / "coverage_mapped_reactants.json"


def split_rxn(cx):
    ext = ""
    body = cx
    if "|" in cx:
        i = cx.index("|")
        body, ext = cx[:i], cx[i:]
    parts = [p for p in body.split(">") if p.strip()]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return None, None, None


def canon_nomap(smi):
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)
    except Exception:
        return None


con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE {N} ROWS"
).fetchall()
print(f"抽样 {len(rows)} 条（文件共 1,771,032 条）\n")

enum = ReactionEnumerator()
stat = Counter()
seen = set()
hit_names = Counter()
miss_ex = []
t0 = time.time()

for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    try:
        rxn.ParseFromString(blob)
    except Exception:
        stat["protobuf失败"] += 1
        continue
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES), None)
    if cx is None:
        stat["无CXSMILES"] += 1
        continue
    lhs, agents, rhs = split_rxn(cx)
    if lhs is None or not rhs:
        stat["拆不出反应"] += 1
        continue
    if not any(s.strip() for s in lhs.split(".")):
        stat["底物侧为空"] += 1
        continue

    pm = Chem.MolFromSmiles(rhs)
    if pm is None:
        stat["产物解析失败"] += 1
        continue
    prod_maps = {a.GetAtomMapNum() for a in pm.GetAtoms() if a.GetAtomMapNum() > 0}
    if not prod_maps:
        stat["产物无映射"] += 1
        continue
    product = canon_nomap(rhs)
    if product is None:
        stat["产物规范化失败"] += 1
        continue

    # 谁贡献了原子到产物
    contributors = []
    for s in (x for x in lhs.split(".") if x):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        if maps and len(maps & prod_maps) / len(maps) > 0.5:
            cs = canon_nomap(s)
            if cs:
                contributors.append(cs)

    if len(contributors) != 2:
        stat[f"贡献组分数={len(contributors)}(跳过)"] += 1
        continue

    r1, r2 = sorted(contributors)
    key = (r1, r2, product)
    if key in seen:
        stat["★重复记录(去重)"] += 1
        continue
    seen.add(key)

    stat["可测（2 个真反应物）"] += 1
    try:
        res = enum.enumerate_pair(r1, r2)
    except Exception as ex:
        stat[f"枚举异常:{type(ex).__name__}"] += 1
        continue

    exp = product
    got = set()
    names = set()
    for r in res:
        for p in r.products:
            cp = canon_nomap(p)
            if cp:
                got.add(cp)
                if cp == exp:
                    names.add(r.reaction_name)
    if exp in got:
        stat["命中"] += 1
        for nm in names:
            hit_names[nm] += 1
    else:
        stat["未命中"] += 1
        if len(miss_ex) < 20:
            miss_ex.append({"reactants": [r1, r2], "product": product,
                            "n_products_got": len(got)})

testable = stat["可测（2 个真反应物）"]
hits = stat["命中"]

print(f"耗时 {time.time()-t0:.0f}s\n")
print("=" * 92)
print("★ 用原子映射定位反应物后的【准确】覆盖率")
print("=" * 92)
print(f"  抽样              {len(rows)}")
print(f"  可测（2 个真反应物） {testable}")
print(f"  ├ 命中            {hits}")
print(f"  └ 未命中          {testable-hits}")
if testable:
    print(f"\n  ★★ 覆盖率 = {hits/testable*100:.1f}% ★★")
print()
print("  跳过原因:")
for k, v in stat.most_common(14):
    print(f"      {k:<28} {v}")

print()
print("=" * 92)
print("命中模板分布")
print("=" * 92)
for k, v in hit_names.most_common(20):
    print(f"      {v:>5}  {k}")

OUT.write_text(json.dumps({
    "sampled": len(rows), "testable": testable, "hits": hits,
    "coverage": hits / testable if testable else None,
    "stat": dict(stat), "hit_templates": dict(hit_names),
    "miss_examples": miss_ex,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n明细已存: {OUT}")

enum.close()
con.close()
