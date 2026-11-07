# -*- coding: utf-8 -*-
r"""测 enumerate_pairs 的并行加速比，决定可取多少成分。"""
import sys
import time
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")

from smartreact import ReactionEnumerator  # noqa: E402
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

enum = ReactionEnumerator()
print(f"n_cores = {getattr(enum, 'n_cores', '?')}")

comps = find_compounds("甘草", limit=40)
smis = []
for c in comps:
    s = c.get("smiles")
    if not s:
        continue
    m = Chem.MolFromSmiles(s)
    if m is not None:
        smis.append(Chem.MolToSmiles(m))
smis = list(dict.fromkeys(smis))[:30]
print(f"取 {len(smis)} 个成分做速度测试")

pairs = [(smis[i], smis[j]) for i in range(len(smis)) for j in range(i + 1, len(smis))]
print(f"配对数 {len(pairs)}")

t0 = time.time()
r1 = enum.enumerate_pairs(pairs, parallel=False)
d1 = time.time() - t0
print(f"串行  : {d1:6.2f}s   结果 {len(r1)} 组")

t0 = time.time()
r2 = enum.enumerate_pairs(pairs, parallel=True)
d2 = time.time() - t0
print(f"并行  : {d2:6.2f}s   结果 {len(r2)} 组")
print(f"★ 加速比 {d1/d2:.2f}x" if d2 > 0 else "")

# 推算可承受规模（按并行速度）
if d2 > 0:
    per_pair = d2 / len(pairs)
    print()
    print(f"每对 {per_pair*1000:.1f} ms（并行）")
    for n in (60, 100, 150, 200, 300):
        np_ = n * (n - 1) // 2
        print(f"   {n:>3} 个成分 -> {np_:>7,} 对 -> 约 {np_*per_pair/60:6.1f} 分钟")

enum.close()
