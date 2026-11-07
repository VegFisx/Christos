# -*- coding: utf-8 -*-
r"""一次性探针（venv + libs）：解一条 ORD 反应，看试剂/溶剂/温度字段长什么样。"""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\libs")
import duckdb
from ord_schema.proto import reaction_pb2

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PQ = (r"D:\ProgramData\DSHNS\chemreact-staging\ord-data\data\11"
      r"\ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet")
con = duckdb.connect(":memory:")
rid, blob = con.execute(
    "SELECT reaction_id, reaction FROM read_parquet(?) LIMIT 1", [PQ]).fetchone()
print("reaction_id:", rid, "｜ blob 字节:", len(blob))
r = reaction_pb2.Reaction()
r.ParseFromString(blob)
print("字段：", [f.name for f in r.DESCRIPTOR.fields])
print("inputs:", len(r.inputs), "（map 字段）")
first = list(r.inputs.values())[0]
print("第一个 input 的文本形式（前 700 字）：")
print(str(first)[:700])
print("conditions 的文本形式：")
print(str(r.conditions)[:400])
c = r.conditions
print("temperature:", c.temperature.setpoint.value if c.temperature.HasField("setpoint") else "-")
print("pressure:", c.pressure.setpoint.value if c.pressure.HasField("setpoint") else "-")
print("stirring:", c.stirring.method if c.stirring else "-")
