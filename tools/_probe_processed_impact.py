# -*- coding: utf-8 -*-
"""一次性探针：炮制品闸对药典方剂组成解析的影响。"""
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\sources")


def main() -> None:
    import formula as F
    import processed as PR
    t0 = time.time()
    ov = F._overlay()
    names, alias = F._names_alias()
    tot = ok = 0
    bad = {}
    for _nm, e in ov.items():
        for c in (e.get("组成") or []):
            tot += 1
            h = F._clean_chp_herb(c.get("herb"))
            if F._resolve_one(h, names, alias):
                ok += 1
            else:
                bad[h] = bad.get(h, 0) + 1
    print("药典组成 token = %d，解析成功 = %d（%.1f%%）  用时 %.1fs"
          % (tot, ok, 100.0 * ok / tot, time.time() - t0))
    proc_bad = {k: v for k, v in bad.items() if PR.is_processed(k)}
    print("其中因【炮制品闸】而不替换的 =", proc_bad)
    print("仍对不上 Top 10：", sorted(bad.items(), key=lambda t: -t[1])[:10])


if __name__ == "__main__":
    main()
