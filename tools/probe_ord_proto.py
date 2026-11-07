# -*- coding: utf-8 -*-
r"""用 ord_schema 正式解析 ORD 的 protobuf，回答 4 个决定性问题。

  ① identifiers 里有 REACTION_CXSMILES 吗？is_mapped=True 吗？
     （若已映射 -> 抽模板不用 rxnmapper，省掉 2.5 GB 的 GPU 折腾）
  ② inputs / outcomes 能拆成底物 / 产物吗？reaction_role 有哪些？
  ③ conditions（温度等）在不在？
  ④ 解析速度 -> 243 万条要跑多久

只读少量行。
"""
import sys
import time
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402

ORD = STAGE / "ord-data"
pq = sorted((ORD / "data").rglob("*.parquet"))
# 挑一个 3~20 MB 的文件：有真实内容又不慢
cand = min((p for p in pq if 3e6 < p.stat().st_size < 2e7),
           key=lambda p: abs(p.stat().st_size - 8e6))
print(f"取样文件: {cand.name} ({cand.stat().st_size/1024**2:.1f} MB)")

N = 300
con = duckdb.connect()
con.execute("SET memory_limit='1200MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction_id, reaction FROM read_parquet('{cand.as_posix()}') LIMIT {N}"
).fetchall()
print(f"读入 {len(rows)} 行\n")

IDT = reaction_pb2.ReactionIdentifier


def role_name(r):
    try:
        return reaction_pb2.Compound.ReactionRole.Name(r)
    except Exception:
        return f"<{r}>"


stat = Counter()
id_types = Counter()
roles = Counter()
input_keys = Counter()
t_parse = []
samples = []

for rid, blob in rows:
    t0 = time.time()
    rxn = reaction_pb2.Reaction()
    rxn.ParseFromString(blob)
    t_parse.append(time.time() - t0)

    # ---- ① identifiers ----
    idents = []
    for i in rxn.identifiers:
        tn = IDT.ReactionIdentifierType.Name(i.type)
        id_types[tn] += 1
        idents.append((tn, i.is_mapped, i.value))
    if any(t == "REACTION_CXSMILES" for t, _, _ in idents):
        stat["有 REACTION_CXSMILES"] += 1
    if any(t == "REACTION_SMILES" for t, _, _ in idents):
        stat["有 REACTION_SMILES"] += 1
    if any(m for _, m, _ in idents):
        stat["★ 带原子映射(is_mapped)"] += 1

    # ---- ② inputs ----
    n_inputs = len(rxn.inputs)
    if n_inputs:
        stat["有 inputs"] += 1
    for key, inp in rxn.inputs.items():
        input_keys[key.split("_")[0] if "_" in key else key] += 1
        for c in inp.components:
            roles[role_name(c.reaction_role)] += 1

    # ---- ② outcomes ----
    n_prod = 0
    if len(rxn.outcomes):
        stat["有 outcomes"] += 1
    for oc in rxn.outcomes:
        n_prod += len(oc.products)
        if oc.HasField("conversion"):
            stat["有 conversion"] += 1
    if n_prod:
        stat["有产物"] += 1

    # ---- ③ conditions ----
    if rxn.HasField("conditions"):
        c = rxn.conditions
        if c.HasField("temperature"):
            stat["有温度"] += 1
        if c.HasField("stirring"):
            stat["有搅拌"] += 1
        if c.HasField("ph"):
            stat["有pH"] += 1

    if len(samples) < 2:
        samples.append((rid, idents, rxn))

print("=" * 88)
print(f"统计（{len(rows)} 条反应）")
print("=" * 88)
for k, v in stat.most_common():
    print(f"   {k:<26} {v:>5}  ({v/len(rows)*100:5.1f}%)")

print("\n   identifier 类型分布:")
for k, v in id_types.most_common():
    print(f"      {k:<22} {v}")

print("\n   reaction_role 分布（底物角色）:")
for k, v in roles.most_common(12):
    print(f"      {k:<26} {v}")

print("\n   input 的 key 前缀:")
for k, v in input_keys.most_common(10):
    print(f"      {k:<20} {v}")

# ---- 样例 ----
for rid, idents, rxn in samples:
    print("\n" + "=" * 88)
    print(f"样例 {rid}")
    print("=" * 88)
    for tn, mapped, val in idents:
        s = val if len(val) <= 200 else val[:200] + f"…(共 {len(val)})"
        print(f"   [{tn}] is_mapped={mapped}")
        print(f"      {s}")
    print(f"   inputs ({len(rxn.inputs)}):")
    for key, inp in rxn.inputs.items():
        parts = []
        for c in inp.components:
            smi = next((ci.value for ci in c.identifiers
                        if ci.type == reaction_pb2.CompoundIdentifier.SMILES), None)
            if smi is None:
                smi = next((ci.value for ci in c.identifiers), None)
            parts.append(f"{role_name(c.reaction_role)}:{smi}")
        print(f"      {key}: {parts}")
    print(f"   outcomes ({len(rxn.outcomes)}):")
    for oc in rxn.outcomes:
        for p in oc.products:
            smi = next((ci.value for ci in p.identifiers), None)
            print(f"      产物 {smi}  conversion="
                  f"{oc.conversion.value if oc.HasField('conversion') else '-'}")
    if rxn.HasField("conditions") and rxn.conditions.HasField("temperature"):
        tc = rxn.conditions.temperature
        print(f"   温度: setpoint="
              f"{tc.setpoint.value if tc.HasField('setpoint') else '-'} "
              f"{tc.setpoint.units if tc.HasField('setpoint') else ''}")

avg = sum(t_parse) / len(t_parse)
print("\n" + "=" * 88)
print("速度")
print("=" * 88)
print(f"   平均解析 {avg*1000:.3f} ms/条")
print(f"   ★ 243 万条单进程预计 {2428291*avg/60:.1f} 分钟 "
      f"({2428291*avg/3600:.1f} 小时)")

con.close()
