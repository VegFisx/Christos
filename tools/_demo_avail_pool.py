# -*- coding: utf-8 -*-
# 第四十三轮演示：可得性例外在"受限池问答"里的效果
#   同一条编辑型切断（大分子 目标 <-> 近同前体）：
#     A 判据层：旧口径判 R1；给 available_fn 且前体在池内 -> 放行
#     B 池问答：池里"有前体" -> 路线 可用=True；（对照）池里没有 -> 找不到路线
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                       # noqa: E402
import retro_search as rs                              # noqa: E402

RDLogger.DisableLog("rdApp.*")

target, prec = None, None
for line in open(STAGE / "reports" / "_avail_demo_pair.txt", encoding="utf-8"):
    k, _, v = line.strip().partition("\t")
    if k == "target":
        target = v
    elif k == "precursor":
        prec = v
assert target and prec, "演示对文件缺失"
print("目标重原子 %d · 前体重原子 %d"
      % (Chem.MolFromSmiles(target).GetNumHeavyAtoms(),
         Chem.MolFromSmiles(prec).GetNumHeavyAtoms()))

print()
print("== A. 判据层对照 ==")
ok_old, why_old = rs.step_usability(target, (prec,))
print("  旧口径（不给 available_fn）: 可用=%s 原因=%s" % (ok_old, why_old))
ok_new, why_new = rs.step_usability(target, (prec,), available_fn=lambda s: s == prec)
print("  新口径（前体在池可得）    : 可用=%s 原因=%s" % (ok_new, why_new))
print("  USTAT.r1_pass_available =", rs.USTAT.get("r1_pass_available", 0))

print()
print("== B. 受限池问答（池里只有这条前体）==")
avail = {}
k = rs.ik(prec)
if k:
    avail[k] = "pool:demo-可得的近同前体"
tmpl = rs.load_rdchiral_templates()
eng = rs.RetroSearch(tmpl, avail, blocks_full={}, blocks_skel={})
routes, stat = eng.search(target, max_depth=1, beam=4)
print("  路线数 %d · 统计 %s" % (len(routes), stat))
for i, rt in enumerate(routes[:2], 1):
    print("  路线 %d：%d 步 · 可用=%s · 原因=%s"
          % (i, len(rt.steps), rt.usable, rt.unusable_reason))
    for j, st in enumerate(rt.steps, 1):
        print("     步 %d 前体 %s" % (j, " | ".join(p[:60] for p in st.precursors)))

print()
print("== C. 对照：池里【没有】这条前体 ==")
eng2 = rs.RetroSearch(tmpl, {}, blocks_full={}, blocks_skel={})
routes2, stat2 = eng2.search(target, max_depth=1, beam=4)
print("  路线数 %d · 统计 %s" % (len(routes2), stat2))
