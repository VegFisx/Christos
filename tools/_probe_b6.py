# -*- coding: utf-8 -*-
# B6 验证（一次性）：strict_elem_complete 开关的实际效果 ——
#  ① 环盲区样例（当前判"可用"，B6 应判 R1）② 大分子样例（两版都 R1）
#  ③ 用 50k 逐切断数据复算消融（多少"可用"会被收紧为 R1；多少 R1 变成确定性可算）
import json
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

tgt_ring = "CC1(C(=O)O)CCC2(C)CCC3(C)C(=CC(=O)C4C5(C)CC=CC(C)(C)C5CCC43C)C2C1"
pre_ring = "CC1(C(=O)O)C=CC2(C)CCC3(C)C(=CC(=O)C4C5(C)CC=CC(C)(C)C5CCC43C)C2C1"
ok1, why1 = rs.step_usability(tgt_ring, (pre_ring,))
ok2, why2 = rs.step_usability(tgt_ring, (pre_ring,), strict_elem_complete=True)
print("环盲区样例（33 重原子）: 现行为=%s(%s) · B6=%s(%s)" % (ok1, why1, ok2, why2))

pair = {}
for line in open(STAGE / "reports" / "_avail_demo_pair.txt", encoding="utf-8"):
    k, _, v = line.strip().partition("\t")
    pair[k] = v
ok3, why3 = rs.step_usability(pair["target"], (pair["precursor"],))
ok4, why4 = rs.step_usability(pair["target"], (pair["precursor"],),
                              strict_elem_complete=True)
print("大分子样例（115 重原子）: 现行为=%s(%s) · B6=%s(%s)" % (ok3, why3, ok4, why4))

print("USTAT:", {k: v for k, v in rs.USTAT.items() if v})

rows = [json.loads(l) for l in open(STAGE / "reports" / "paper" / "results"
                                    / "usability_per_cut.jsonl", encoding="utf-8")
        if l.strip()]
ok_rows = [r for r in rows if r["ok"]]
kill = [r for r in ok_rows if r["ratio"] >= 0.999]
r1_rows = [r for r in rows if str(r["why"]).startswith("R1")]
r1_det = [r for r in r1_rows if r["ratio"] >= 0.999]
print("50k 消融：B6 会把 %d 条'可用'收紧为 R1（占可用 %.2f%%）；"
      "R1 中 %d/%d（%.0f%%）可由确定性规则替代 MCS"
      % (len(kill), 100 * len(kill) / max(1, len(ok_rows)),
         len(r1_det), len(r1_rows), 100 * len(r1_det) / max(1, len(r1_rows))))
