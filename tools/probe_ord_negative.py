# -*- coding: utf-8 -*-
r"""第十三轮：ORD 里到底有没有【反例】？—— 只探查，不下结论。

背景：243 万条 ORD 全是"做过的反应"（正例），没有反例就算不出假阳性率。
     本探针只回答一件事：protobuf 里有哪些字段可能承载"没反应/失败/低转化"。

口径（先说死，避免重测）：
  采样范围：BIG parquet 的前 N 条（默认 20000）
  "反例候选 A" = 任一 outcome 的 conversion 值 == 0
  "反例候选 B" = 任一产物的 yield 测量值 == 0
  "反例候选 C" = notes/自由文本里出现否定词（no reaction / did not / failed / no conversion）
  注意：conversion=0 与 yield=0 都可能是"没测/没记录"，所以本探针只给计数与原文样例，
        不直接把它当反例用。

用法: python probe_ord_negative.py [N]
"""
import re
import sys
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

NEG_RE = re.compile(
    r"no reaction|does not react|did not react|didn'?t react|no conversion|not observed|"
    r"failed|unsuccessful|no product|trace|decompos|intractable", re.I)

print("=" * 96)
print("一、schema 里有哪些字段可能承载负例（直接读 DESCRIPTOR，不猜）")
print("=" * 96)


def show(msg, prefix=""):
    for f in msg.DESCRIPTOR.fields:
        t = f.message_type.name if f.message_type else f.type
        rep = getattr(f, "is_repeated", None)
        print(f"  {prefix}{f.name:<28} {str(t):<22} repeated={rep}")


show(reaction_pb2.Reaction())
print()
show(reaction_pb2.ReactionOutcome(), prefix="ReactionOutcome.")
print()
for nm in ("Percentage", "ReactionProduct", "ProductMeasurement", "ReactionNotes",
           "ReactionObservation"):
    msg = getattr(reaction_pb2, nm, None)
    if msg is None:
        continue
    print(f"  --- {nm} ---")
    show(msg, prefix=f"{nm}.")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
con = duckdb.connect()
con.execute("SET memory_limit='1000MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') LIMIT {N}").fetchall()
print()
print("=" * 96)
print(f"二、采样 {len(rows):,} 条，统计负例候选")
print("=" * 96)

def notes_text(rxn):
    """rxn.notes 是 ReactionNotes 消息，不是字符串（踩过）。把所有 string 字段拼起来。"""
    n = rxn.notes
    if not n or not n.ListFields():
        return ""
    parts = []
    for f in n.DESCRIPTOR.fields:
        v = getattr(n, f.name)
        if isinstance(v, str) and v:
            parts.append(v)
    return " ".join(parts)


c = Counter()
examples_conv0 = []
examples_yield0 = []
examples_negtext = []
examples_obstext = []
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
        if NEG_RE.search(txt):
            c["notes含否定词"] += 1
            if len(examples_negtext) < 3:
                examples_negtext.append(txt[:220])
    if not rxn.outcomes:
        c["无outcomes"] += 1
    for oc in rxn.outcomes:
        c["outcomes总数"] += 1
        if oc.HasField("conversion"):
            c["有conversion字段"] += 1
            v = oc.conversion.value
            if v == 0:
                c["conversion==0"] += 1
                if len(examples_conv0) < 3:
                    examples_conv0.append((rxn.reaction_id, oc.conversion.precision))
            elif v < 1:
                c["0<conversion<1"] += 1
        for prod in oc.products:
            for m in prod.measurements:
                if m.type == reaction_pb2.ProductMeasurement.YIELD:
                    c["yield测量数"] += 1
                    for key in ("percentage", "float_value"):
                        if m.HasField(key):
                            val = getattr(m, key)
                            val = val.value if key == "percentage" else val
                            if val == 0:
                                c["yield==0"] += 1
                                if len(examples_yield0) < 3:
                                    examples_yield0.append((rxn.reaction_id, key))
                            elif val < 5:
                                c["0<yield<5"] += 1
    # 自由文本类字段：observations.comment（"没观察到反应"这类话最可能写在这里）
    for ob in rxn.observations:
        if ob.comment:
            c["observations.comment非空"] += 1
            if NEG_RE.search(ob.comment):
                c["observations含否定词"] += 1
                if len(examples_obstext) < 3:
                    examples_obstext.append(ob.comment[:220])

for k in ("总条数", "无outcomes", "outcomes总数", "有conversion字段", "conversion==0",
          "0<conversion<1", "yield测量数", "yield==0", "0<yield<5",
          "notes非空", "notes含否定词", "observations.comment非空",
          "observations含否定词", "protobuf失败"):
    if c.get(k):
        print(f"  {k:<26} {c[k]:,}")
print()
print("  原文样例（conversion==0）:", examples_conv0)
print("  原文样例（yield==0）    :", examples_yield0)
print("  原文样例（notes 否定词）:")
for t in examples_negtext:
    print("    ·", t)
print("  原文样例（observations 否定词）:")
for t in examples_obstext:
    print("    ·", t)
print()
print("=" * 96)
print("口径提醒：conversion/yield 字段为 0 也可能只是「没测」，本探针不判定它是反例。")
