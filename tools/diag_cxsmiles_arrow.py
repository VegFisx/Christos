# -*- coding: utf-8 -*-
r"""确认：无 '>>' 的 CXSMILES 是不是三段式 '底物>试剂>产物'？

上一版我查 '>>' 就断定"只有单边"，可能错了 —— 例子里有单独的 '>'。
"""
import sys
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"

con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE 500 ROWS"
).fetchall()

cnt = Counter()
noarrow_samples = []

for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    rxn.ParseFromString(blob)
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES), None)
    if cx is None:
        cnt["无 CXSMILES"] += 1
        continue

    n2 = cx.count(">>")
    n1 = cx.count(">")
    cnt[f"'>>' 出现 {n2} 次"] += 1

    if n2 == 0:
        if n1 == 0:
            cnt["  无任何 '>'"] += 1
        elif n1 == 1:
            cnt["  单个 '>' (三段式?)"] += 1
            if len(noarrow_samples) < 4:
                noarrow_samples.append(cx)
        elif n1 == 2:
            cnt["  两个独立 '>'"] += 1
        else:
            cnt[f"  '>' 共 {n1} 个"] += 1

print("=" * 92)
print("'>' 出现情况（500 条抽样）")
print("=" * 92)
for k, v in cnt.most_common():
    print(f"   {k:<28} {v:>5}")

print()
print("=" * 92)
print("无 '>>' 的原始字符串样例（看真实分隔符）")
print("=" * 92)
for s in noarrow_samples:
    print(f"   长度 {len(s)}")
    print(f"   头 200: {s[:200]}")
    print(f"   尾 200: {s[-200:]}")
    print()

# 对样例尝试按 '>' 拆三段
print("=" * 92)
print("尝试按 '>' 拆三段并解析")
print("=" * 92)
for s in noarrow_samples[:3]:
    parts = s.split(">")
    print(f"   拆成 {len(parts)} 段")
    for i, p in enumerate(parts):
        comps = [x for x in p.split(".") if x]
        ok = sum(1 for c in comps if Chem.MolFromSmiles(c) is not None)
        print(f"      [{i}] 组分数 {len(comps)}, 可解析 {ok}, 头 90: {p[:90]}")
    print()

con.close()
