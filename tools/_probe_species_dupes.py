# -*- coding: utf-8 -*-
"""一次性探针（只读）：COCONUT 物种名的脏数据有多少。

看四件事：
  Q1 fold 归一后**撞车**的物种（异写/拼错，如 glycyrrhiza vs glycyrrhizae）
  Q2 带 sp./spp./aff./cf. 这类**非确定物种**标记的条目
  Q3 名字里带数字 / 杂交符号（x / ×）的条目
  Q4 名字超过两个词的条目
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "sources"))

import coconut as CC  # noqa: E402


def main() -> None:
    species = CC._species_list()
    print("物种总数 =", len(species))

    groups = defaultdict(list)
    for sp in species:
        groups[CC._fold(sp)].append(sp)
    dup = {k: v for k, v in groups.items() if len(v) > 1}
    n_sp_in_dup = sum(len(v) for v in dup.values())
    print("[Q1] fold 撞车组 = %d 组，涉及 %d 个物种条目（占 %.2f%%）"
          % (len(dup), n_sp_in_dup, 100.0 * n_sp_in_dup / max(1, len(species))))
    print("     样例（前 12 组）：")
    for k, v in sorted(dup.items(), key=lambda kv: -len(kv[1]))[:12]:
        print("       ", " | ".join(v))

    def count(pred, label):
        hit = [sp for sp in species if pred(sp)]
        print("     %s：%d 个   样例 %s" % (label, len(hit), hit[:6]))

    print("[Q2] 非确定物种标记")
    count(lambda s: re.search(r"\b(spp?|aff|cf|indet)\b", s), "sp./spp./aff./cf.")
    print("[Q3] 名字含数字或杂交号")
    count(lambda s: re.search(r"[0-9×]", s) or " x " in s, "数字/×/x")
    print("[Q4] 超过两个词")
    count(lambda s: len(s.split()) > 2, ">2 词")

    # 撞车组里的成分总量：合并后会省下多少次重复查询机会
    print("[补充] 撞车组涉及的物种-成分记录数（合并后不再重复）")
    conn = CC._connect()
    try:
        tot = 0
        for v in list(dup.values())[:200]:
            ph = ",".join("?" * len(v))
            n = conn.execute(
                f"SELECT COUNT(*) FROM species_compound WHERE LOWER(TRIM(species)) IN ({ph})",
                v).fetchone()[0]
            tot += n
        print("     前 200 组共 %d 条物种-成分记录" % tot)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
