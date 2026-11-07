# -*- coding: utf-8 -*-
r"""第十二轮（探针）：DEAD/PPh3 到底写在 CXSMILES 的哪一段？

背景（已实测）：
  - 覆盖率口径只统计【reactants 段里、原子没进产物】的组分（沿用 build_condition_table.py）。
  - 结果 mitsunobu 1831 条：PPh3 覆盖 59%，DEAD 只 18%。
  - 这份 ord_schema 的 ReactionInput 没有 reaction_role 字段，inputs 的 key 是机器名
    （m1_m6_m2_m7_m3），所以"角色"信息只在 CXSMILES 的段位里：
    reactants > agents > products。
假设：大量 Mitsunobu 记录把 DEAD 写在 agents 段 -> 被口径整段忽略。

口径：扫描前 N 条；对每条 CXSMILES 分成三段，分别用 SMARTS 找
      偶氮二羧酸酯 / 膦 / 硼氢化物，统计"出现在哪一段"的组合。

用法: python probe_cxsmiles_agents.py [N]
"""
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
from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"

AZO = Chem.MolFromSmarts("[NX2]=[NX2][CX3](=[OX1])[OX2]")
PHOS = Chem.MolFromSmarts("[PX3]([#6])([#6])[#6]")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200000


def has(frag_smiles: str, patt) -> bool:
    for frag in frag_smiles.split("."):
        m = Chem.MolFromSmiles(frag)
        if m is not None and m.HasSubstructMatch(patt):
            return True
    return False


con = duckdb.connect()
con.execute("SET memory_limit='1000MB'")
con.execute("SET threads=2")
cur = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') LIMIT {N}")

c = Counter()
paired = Counter()
t0 = time.time()
n = 0
while True:
    rows = cur.fetchmany(5000)
    if not rows:
        break
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            continue
        cx = next((i.value for i in rxn.identifiers
                   if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES
                   and i.value), None)
        if not cx:
            continue
        n += 1
        body = cx.split("|", 1)[0] if "|" in cx else cx
        parts = body.split(">")
        if len(parts) == 2:
            lhs, agents, rhs = parts[0], "", parts[1]
        elif len(parts) == 3:
            lhs, agents, rhs = parts
        else:
            continue
        for seg_name, seg in (("reactants", lhs), ("agents", agents)):
            if has(seg, AZO):
                c[f"azo_in_{seg_name}"] += 1
            if has(seg, PHOS):
                c[f"phosphine_in_{seg_name}"] += 1
        if has(lhs, PHOS) and has(agents, AZO):
            paired["PPh3(reactants) + DEAD(agents)"] += 1
        if has(lhs, PHOS) and has(lhs, AZO):
            paired["PPh3 + DEAD 都在 reactants"] += 1
    if n % 50000 < 5000:
        print(f"  {n:,}  {time.time()-t0:.0f}s", flush=True)

print()
print("=" * 96)
print(f"扫描 {n:,} 条带 CXSMILES 的记录，用时 {time.time()-t0:.0f}s")
print("=" * 96)
for k, v in c.most_common():
    print(f"  {k:<28} {v:,}")
print()
for k, v in paired.most_common():
    print(f"  {k:<40} {v:,}")
print()
print("结论口径：若 azo_in_agents 远大于 azo_in_reactants，则现行覆盖率口径系统性低估了")
print("          辅助试剂（它们写在 agents 段），这正是 DEAD 只有 18% 的原因。")
