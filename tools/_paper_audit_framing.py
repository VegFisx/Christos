# -*- coding: utf-8 -*-
# One-shot: lead the abstract with the audit-method framing.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

EN = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
          r"\manuscript-humanized.md")
ZH = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
          r"\Christos-system-paper-draft-20261019-zh-humanized.md")

EN_OLD = ("**Results.** Christos is a reaction prediction system that runs entirely on the "
          "local machine.")
EN_NEW = ("**Results.** We present a method for auditing provenance-aware reaction-prediction "
          "systems and apply it to build one, Christos, which runs entirely on the local "
          "machine.")

ZH_OLD = "**结果。** Christos 是一个完全在本机运行的反应预测系统。"
ZH_NEW = ("**结果。** 本文提出一套审计可溯源反应预测系统的方法，并用它建成了一个实例 Christos，"
          "完全在本机运行。")


def main() -> int:
    for path, old, new in ((EN, EN_OLD, EN_NEW), (ZH, ZH_OLD, ZH_NEW)):
        s = path.read_text(encoding="utf-8")
        n = s.count(old)
        print("%s hits=%d" % (path.name, n))
        if n:
            s = s.replace(old, new, 1)
            path.write_text(s, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
