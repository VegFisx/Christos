# -*- coding: utf-8 -*-
r"""诊断 6 条未命中的模板：看枚举器到底产出了什么，判断是"规则坏了"还是"选了另一个位点"。"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

P = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
rows = []
for line in P.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
    f = line.split("\t")
    if len(f) == 5:
        rows.append(f)

TARGET_IDS = {"3118", "3119", "3120", "3121", "7833", "7834"}

enum = ReactionEnumerator()

for rname, tid, example, smarts, cats in rows:
    if tid not in TARGET_IDS:
        continue
    lhs, rhs = example.split(">>", 1)
    ra, rb = [s for s in lhs.split(".") if s]
    print("=" * 88)
    print(f"[{rname}] id={tid}")
    print(f"  底物 A : {ra}")
    print(f"  底物 B : {rb}")
    print(f"  期望产物: {rhs}")
    print(f"  SMARTS  : {smarts[:150]}")
    print(f"  categories: {cats}")
    try:
        res = enum.enumerate_pair(ra, rb)
    except Exception as ex:
        print(f"  ✗ {type(ex).__name__}: {ex}")
        continue
    print(f"  → 枚举器返回 {len(res)} 组结果:")
    for r in res:
        same = "  ★同类" if r.reaction_name == rname else ""
        for p in r.products:
            mark = "  ✓与期望一致" if Chem.CanonSmiles(p) == Chem.CanonSmiles(rhs) else ""
            print(f"      [{r.reaction_name}]{same} {p}{mark}")
    print()

enum.close()
