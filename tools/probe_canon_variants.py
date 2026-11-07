# -*- coding: utf-8 -*-
r"""第十二轮（探针）：同一个试剂被立体化学写法拆成几个 canonical 桶？

假设：覆盖率统计里 canon_nomap() 用默认 MolToSmiles（保留 E/Z 立体），
      于是 DEAD 写成 "CCOC(=O)/N=N/C(=O)OCC"（有立体）与 "CCOC(=O)N=NC(=O)OCC"（无立体）
      被算成两个不同的试剂 -> 每个的覆盖率都被腰斩。
      PPh3 没有立体 -> 不受影响（59%），DEAD 受影响（18%）—— 与实测吻合。

本探针不猜：直接统计 azo / phosphine 片段在"保立体 vs 去立体"下的 canonical 形态数。

用法: python probe_canon_variants.py [N]
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
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100000


def canon(m, iso):
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m, isomericSmiles=iso)


con = duckdb.connect()
con.execute("SET memory_limit='1000MB'")
con.execute("SET threads=2")
cur = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') LIMIT {N}")

with_stereo = {"azo": Counter(), "phos": Counter()}
without = {"azo": Counter(), "phos": Counter()}
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
        lhs = (cx.split("|", 1)[0] if "|" in cx else cx).split(">")[0]
        for frag in lhs.split("."):
            m = Chem.MolFromSmiles(frag)
            if m is None:
                continue
            if m.HasSubstructMatch(AZO):
                with_stereo["azo"][canon(m, True)] += 1
                without["azo"][canon(m, False)] += 1
            if m.HasSubstructMatch(PHOS):
                with_stereo["phos"][canon(m, True)] += 1
                without["phos"][canon(m, False)] += 1
    if n % 25000 < 5000:
        print(f"  {n:,}  {time.time()-t0:.0f}s", flush=True)

print()
print("=" * 96)
print(f"扫描 {n:,} 条，用时 {time.time()-t0:.0f}s")
print("=" * 96)
for key in ("azo", "phos"):
    ws, wo = with_stereo[key], without[key]
    print(f"{key}: 保立体形态数 {len(ws)} / 去立体形态数 {len(wo)}"
          f"   （总命中 {sum(ws.values()):,}）")
    print("  保立体 top5:", ws.most_common(5))
    print("  去立体 top5:", wo.most_common(5))
    print()
