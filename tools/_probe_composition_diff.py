# -*- coding: utf-8 -*-
"""一次性探针（只读）：同一方名，用户库的组成 vs 药典扒出来的组成，差在哪。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CHP = Path(r"D:\ProgramData\DSHNS\chemreact-staging\data\chp_formulas.json")
USER = Path(r"D:\TCMAI\data\formula_db.json")
SAMPLE = ["一捻金", "藿香正气水", "桂枝茯苓丸", "复方丹参滴丸",
          "银翘解毒片", "安宫牛黄丸", "气滞胃痛颗粒", "六味地黄丸"]


def main() -> None:
    chp = json.loads(CHP.read_text(encoding="utf-8"))
    user = json.loads(USER.read_text(encoding="utf-8"))
    n_same = n_diff = n_missing = 0
    for name in SAMPLE:
        c = chp.get(name)
        urecs = user.get(name)
        print("=" * 96)
        print("【%s】" % name)
        if not c:
            print("   药典：没扒到")
            continue
        if not urecs:
            print("   用户库：没有这个名字")
            n_missing += 1
            continue
        best = max(urecs, key=lambda r: len(str(r.get("peifang") or "")))
        print("   药典  ：%d 味 → %s"
              % (len(c["组成"]),
                 " ".join("%s%s%s" % (x["prep"], x["herb"], x["dose"])
                          for x in c["组成"][:8])))
        print("   用户库：%s" % str(best.get("peifang"))[:150])
        chp_names = {x["herb"] for x in c["组成"]}
        u_txt = re.sub(r"\d+(?:\.\d+)?\s*\w*", "", str(best.get("peifang") or ""))
        u_names = {t.strip() for t in re.split(r"[，,、;；]", u_txt) if t.strip()}
        same = chp_names == u_names
        n_same += 1 if same else 0
        n_diff += 0 if same else 1
        print("   组成药材集合：%s（药典 %d 味 / 用户 %d 味；交集 %d）"
              % ("一致" if same else "**不一致**", len(chp_names), len(u_names),
                 len(chp_names & u_names)))
        if not same:
            print("      药典多出：", sorted(chp_names - u_names)[:8])
            print("      用户多出：", sorted(u_names - chp_names)[:8])
        print("      用户库该名记录数 = %d，出处 = %s"
              % (len(urecs), [str(r.get("chuchu"))[:20] for r in urecs[:3]]))
    print("=" * 96)
    print("抽样 %d 个：组成一致 %d ／ 不一致 %d ／ 用户库没有 %d"
          % (len(SAMPLE), n_same, n_diff, n_missing))


if __name__ == "__main__":
    main()
