# -*- coding: utf-8 -*-
r"""第十二轮（探针）：口径扩到 CXSMILES 的 agents 段，到底能多捞到多少试剂？

背景：覆盖率口径只统计 reactants 段（「声明为 REACTANT、原子没进产物」）。
      已知 azo 在 agents 段只有 1/200000、phosphine 1636 vs 3664 —— 但那只是两个分子。
      本探针把 6 个"必需件角色"的代表分子都统计一遍：它们分别出现在哪一段。

口径：扫描前 N 条；对每条 CXSMILES 的 reactants/agents 两段分别跑角色 SMARTS，
      统计命中次数（按分子名细分）。**先测再决定要不要改口径**。

用法: python probe_agents_value.py [N]
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

SMARTS = {
    "azodicarboxylate": "[NX2]=[NX2][CX3](=[OX1])[OX2]",
    "phosphine": "[PX3]([#6])([#6])[#6]",
    "carbodiimide": "[NX2]=[CX2]=[NX2]",
    "uronium_activator": "[NX3+]=[CX3]([NX3])[OX2]",
    "benzotriazole": "c1ccc2nnnc2c1",
    "borohydride": "[BH1,BH2,BH3,BH4]",
    "carbonate": "[CX3](=[OX1])([OX1-])[OX1-]",
}
PATTS = {k: Chem.MolFromSmarts(v) for k, v in SMARTS.items()}
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200000


def hits(seg: str):
    out = set()
    for frag in seg.split("."):
        if not frag:
            continue
        m = Chem.MolFromSmiles(frag)
        if m is None:
            continue
        for k, p in PATTS.items():
            if p is not None and m.HasSubstructMatch(p):
                out.add(k)
    return out


con = duckdb.connect()
con.execute("SET memory_limit='1000MB'")
con.execute("SET threads=2")
cur = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') LIMIT {N}")

c = Counter()
only_agents = Counter()
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
        body = cx.split("|", 1)[0] if "|" in cx else cx
        parts = body.split(">")
        if len(parts) == 2:
            lhs, agents = parts[0], ""
        elif len(parts) == 3:
            lhs, agents = parts[0], parts[1]
        else:
            continue
        n += 1
        hr, ha = hits(lhs), hits(agents)
        for k in hr:
            c[f"{k}:reactants"] += 1
        for k in ha:
            c[f"{k}:agents"] += 1
        for k in ha - hr:
            only_agents[k] += 1
    if n % 50000 < 5000:
        print(f"  {n:,}  {time.time()-t0:.0f}s", flush=True)

print()
print("=" * 96)
print(f"扫描 {n:,} 条带 CXSMILES 的记录，用时 {time.time()-t0:.0f}s")
print("=" * 96)
print(f"{'角色':<20}{'reactants 段':>14}{'agents 段':>12}{'只在 agents':>14}")
for k in SMARTS:
    print(f"{k:<20}{c.get(k+':reactants', 0):>14,}{c.get(k+':agents', 0):>12,}"
          f"{only_agents.get(k, 0):>14,}")
print()
print("结论口径：'只在 agents' 若与 reactants 段同量级 -> 扩口径有真收益；")
print("          若远小于 reactants 段 -> 扩口径收益低，应把时间投到反例集。")
