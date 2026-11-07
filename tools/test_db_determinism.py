# -*- coding: utf-8 -*-
r"""测：find_compounds 返回的底物集稳不稳定？

如果 DB 查询每次返回不同的行（LIMIT 无 ORDER BY），
那所有基于它的对比都会被污染 —— 这就能解释 455/454/460 三个数字。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")

from tcm_ro import use_readonly; use_readonly(); from db_utils import find_compounds

HERBS = ("甘草", "附子", "干姜")

print("=" * 88)
print("① 同一进程内连查 4 次，比对 SMILES 集合")
print("=" * 88)
sets = []
for i in range(4):
    rows = []
    for h in HERBS:
        rows.extend(find_compounds(h, limit=20))
    s = {r["smiles"] for r in rows if r.get("smiles")}
    sets.append(s)
    print(f"  第{i+1}次: {len(rows)} 行, {len(s)} 个不同 SMILES")

base = sets[0]
for i, s in enumerate(sets[1:], 2):
    print(f"  第{i}次 vs 第1次: 对称差 {len(s ^ base)}")
    if s != base:
        print(f"      仅第1次有: {len(base - s)}")
        print(f"      仅第{i}次有: {len(s - base)}")
        for x in list(s - base)[:3]:
            print(f"         + {x[:66]}")
        for x in list(base - s)[:3]:
            print(f"         - {x[:66]}")

print()
print("=" * 88)
print("② 顺序是否一致")
print("=" * 88)
for i in range(2):
    rows = []
    for h in HERBS:
        rows.extend(find_compounds(h, limit=20))
    names = [r.get("name") for r in rows]
    print(f"  第{i+1}次前 5 个: {names[:5]}")
    print(f"           后 5 个: {names[-5:]}")

print()
print("=" * 88)
print("③ 看 find_compounds 的 SQL 有没有 ORDER BY")
print("=" * 88)
import inspect
src = inspect.getsource(find_compounds)
for ln in src.splitlines():
    low = ln.lower()
    if any(k in low for k in ("select", "order by", "limit", "where", "group by")):
        print("  " + ln.strip()[:100])
