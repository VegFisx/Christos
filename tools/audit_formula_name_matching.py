# -*- coding: utf-8 -*-
"""方剂名匹配审计（只读）：

1) 随机抽 100 个方名，截掉最后一个字后查询 —— 不允许静默返回另一个方名。
2) 药典 overlay 独有方名（不在用户方剂库里的）—— 必须仍能取到版本。

只用于验收，不改任何库。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sources"))
import formula as F  # noqa: E402


def main() -> int:
    names = list(F._load().keys())
    random.seed(20261017)
    sample = random.sample(names, min(100, len(names)))
    bad = []
    zero = []
    tests = 0
    for n in sample:
        q = n[:-1]
        if len(q) < 2:
            continue
        tests += 1
        vs = F.formula_versions(q)
        if vs and any(v.get("name") != q for v in vs):
            bad.append((q, [v.get("name") for v in vs][:3]))
        if not vs and F.is_formula_name(q):
            zero.append(q)

    ov = sorted(set(F._overlay()) - set(F._load()))
    ov_bad = [n for n in ov if not F.formula_versions(n)]

    print("truncated_tests=%d silent_substitutions=%d" % (tests, len(bad)))
    if bad:
        print("bad=", bad[:5])
    print("exact_truncated_name_with_zero_versions=%d" % len(zero))
    if zero:
        print("zero=", zero[:8])
    print("overlay_only=%d no_versions=%d" % (len(ov), len(ov_bad)))
    if ov_bad:
        print("overlay_bad=", ov_bad[:8])
    return 1 if (bad or ov_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
