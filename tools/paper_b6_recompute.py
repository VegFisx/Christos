# -*- coding: utf-8 -*-
r"""B6 翻默认（2026-10-15）后的数字重算 —— 全部可从既有逐切断记录精确推出（确定性规则）。

  * 行为验证：环盲区样例（默认调用）现在应判 R1；显式 False 仍可复现旧行为
  * 重算 50k 抽样构成：ok 且 元素覆盖比>=0.999 -> 改判 R1（其余不变）
  * 产出：reports/paper/results/usability_summary_after_b6.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
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

from rdkit import RDLogger                            # noqa: E402
import retro_search as rs                             # noqa: E402
RDLogger.DisableLog("rdApp.*")

RES = STAGE / "reports" / "paper" / "results"

tgt = "CC1(C(=O)O)CCC2(C)CCC3(C)C(=CC(=O)C4C5(C)CC=CC(C)(C)C5CCC43C)C2C1"
pre = "CC1(C(=O)O)C=CC2(C)CCC3(C)C(=CC(=O)C4C5(C)CC=CC(C)(C)C5CCC43C)C2C1"
ok_def, why_def = rs.step_usability(tgt, (pre,))
ok_old, why_old = rs.step_usability(tgt, (pre,), strict_elem_complete=False)
print("翻默认验证：默认=%s(%s) · 显式关=%s(%s)" % (ok_def, why_def, ok_old, why_old))
assert (not ok_def) and ok_old, "翻默认没有按预期生效！"

rows = [json.loads(l) for l in open(RES / "usability_per_cut.jsonl", encoding="utf-8")
        if l.strip()]
old_c = Counter("ok" if r["ok"] else r["why"] for r in rows)
new_c = Counter()
flipped = 0
for r in rows:
    if r["ok"] and r["ratio"] >= 0.999:
        new_c["R1_残基路线"] += 1
        flipped += 1
    else:
        new_c["ok" if r["ok"] else r["why"]] += 1
n = len(rows)
ok_new = new_c["ok"]
after = [r for r in rows if not r["bl"]]
ok_after = sum(1 for r in after if r["ok"] and r["ratio"] < 0.999)
out = {
    "generated": "2026-10-15（B6 翻默认后，从既有逐切断数据精确重算）",
    "n_cuts": n, "flipped_ok_to_R1": flipped,
    "before": {"usable": old_c["ok"], "usable_rate": round(old_c["ok"] / n, 4),
               "verdicts": dict(old_c)},
    "after_b6": {"usable": ok_new, "usable_rate": round(ok_new / n, 4),
                 "verdicts": dict(new_c)},
    "after_b6_and_blacklist": {"cuts": len(after),
                               "usable": ok_after,
                               "usable_rate": round(ok_after / max(1, len(after)), 4)},
    "note": "B6=元素全覆盖->确定性R1；本表为精确重算（规则确定性），非重跑估计",
}
RES.joinpath("usability_summary_after_b6.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("50k 抽样重算：可用 %d -> %d（%.2f%% -> %.2f%%）；改判 R1 的 %d 条；"
      "再叠黑名单：%.2f%%"
      % (old_c["ok"], ok_new, 100 * old_c["ok"] / n, 100 * ok_new / n, flipped,
         100 * ok_after / max(1, len(after))))
print("新构成：", dict(new_c.most_common()))
print("写出：usability_summary_after_b6.json")
