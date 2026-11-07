# -*- coding: utf-8 -*-
r"""第十三轮（探针 2）：把"疑似反例"的 ORD 原始记录打出来看，别靠关键词猜。

探针 1 的结果有两个疑点，这个脚本专门核实：
  1. notes「含否定词」119/20000 -> 但打印出来的样例明显是正常实验步骤（正则误匹配？）
     -> 本脚本按【命中的关键词】分类计数，并打印命中处上下文，判断是不是假阳性。
  2. yield==0 有 10/20000（0.06%）-> 这到底是"真·没反应"还是"数据录入为 0"？
     -> 本脚本把整条记录的关键字段原样打出来（CXSMILES / outcome / 测量的 type+details+值 / notes）。

用法: python probe_ord_zero_yield.py [N] [最多打印几条]
"""
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

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"

NEG_TERMS = ["no reaction", "does not react", "did not react", "didn't react",
             "no conversion", "not observed", "failed", "unsuccessful",
             "no product", "trace", "decompos", "intractable"]

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
MAXDUMP = int(sys.argv[2]) if len(sys.argv) > 2 else 2


def notes_text(rxn):
    n = rxn.notes
    if not n or not n.ListFields():
        return ""
    return " ".join(v for f in n.DESCRIPTOR.fields
                    if isinstance(v := getattr(n, f.name), str) and v)


def cxsmiles(rxn):
    return next((i.value for i in rxn.identifiers
                 if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES
                 and i.value), None)


def msummary(m):
    tname = reaction_pb2.ProductMeasurement.ProductMeasurementType.Name(m.type)
    bits = [f"type={tname}"]
    if m.HasField("percentage"):
        bits.append(f"percentage={m.percentage.value}")
    if m.HasField("float_value"):
        bits.append(f"float={m.float_value.value}")
    if m.string_value:
        bits.append(f"string={m.string_value[:60]!r}")
    if m.details:
        bits.append(f"details={m.details[:60]!r}")
    return " ".join(bits)


def dump(rxn, why):
    print("-" * 96)
    print(f"  why={why}  reaction_id={rxn.reaction_id}")
    cx = cxsmiles(rxn)
    print(f"  CXSMILES: {cx[:300] if cx else '<无>'}")
    print(f"  notes(is_heterogeneous={rxn.notes.is_heterogeneous}) 前 200 字: "
          f"{notes_text(rxn)[:200]!r}")
    for oi, oc in enumerate(rxn.outcomes):
        conv = f"{oc.conversion.value} (prec={oc.conversion.precision})" \
            if oc.HasField("conversion") else "<未给>"
        print(f"  outcome[{oi}] conversion={conv} products={len(oc.products)}")
        for prod in oc.products:
            ids = ",".join(f"{i.type}:{i.value}" for i in prod.identifiers)[:80]
            print(f"     product {ids}")
            for m in prod.measurements:
                print(f"       · {msummary(m)}")
    for ob in rxn.observations:
        if ob.comment:
            print(f"  observation.comment: {ob.comment[:200]!r}")


con = duckdb.connect()
con.execute("SET memory_limit='1200MB'")
con.execute("SET threads=2")
t0 = time.time()
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') LIMIT {N}").fetchall()
print(f"读入 {len(rows):,} 条（{time.time()-t0:.0f}s），开始逐条解析", flush=True)

c = Counter()
kw_hits = Counter()
kw_examples = {}
dumped_zero = 0
zero_yield_records = []
zero_conv_records = []
for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    try:
        rxn.ParseFromString(blob)
    except Exception:
        c["protobuf失败"] += 1
        continue
    c["总条数"] += 1
    txt = notes_text(rxn)
    if txt:
        c["notes非空"] += 1
        low = txt.lower()
        for kw in NEG_TERMS:
            if kw in low:
                kw_hits[kw] += 1
                if kw not in kw_examples:
                    i = low.index(kw)
                    kw_examples[kw] = txt[max(0, i - 80):i + 80].replace("\n", " ")
    hit_zero = False
    for oc in rxn.outcomes:
        if oc.HasField("conversion") and oc.conversion.value == 0:
            c["conversion==0"] += 1
            hit_zero = True
        for prod in oc.products:
            for m in prod.measurements:
                if m.type != reaction_pb2.ProductMeasurement.YIELD:
                    continue
                for key in ("percentage", "float_value"):
                    if m.HasField(key):
                        v = getattr(m, key).value
                        if v == 0:
                            c["yield==0"] += 1
                            hit_zero = True
    if hit_zero:
        c["命中0的记录数"] += 1
        if len(zero_yield_records) < MAXDUMP:
            zero_yield_records.append(blob)

print(f"扫描 {c['总条数']:,} 条，用时 {time.time()-t0:.0f}s", flush=True)
print()
print("=" * 96)
print("一、计数")
print("=" * 96)
for k in ("总条数", "notes非空", "conversion==0", "yield==0", "命中0的记录数", "protobuf失败"):
    print(f"  {k:<20} {c.get(k, 0):,}")
print()
print("=" * 96)
print("二、notes 否定词：按关键词拆开（看有几个是真命中）")
print("=" * 96)
for kw, n in kw_hits.most_common():
    print(f"  {kw:<18} {n:>6}   上下文: {kw_examples[kw][:110]!r}")
if not kw_hits:
    print("  （无命中）")

print()
print("=" * 96)
print(f"三、原样打印 {len(zero_yield_records)} 条 yield/conversion == 0 的记录")
print("=" * 96)
for blob in zero_yield_records:
    rxn = reaction_pb2.Reaction()
    rxn.ParseFromString(blob)
    dump(rxn, "yield或conversion==0")
print()
print(f"扫描范围: 前 {N:,} 条；共 {c.get('命中0的记录数', 0)} 条命中")
