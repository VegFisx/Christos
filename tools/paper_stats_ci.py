# -*- coding: utf-8 -*-
r"""论文统计：Wilson 95% 置信区间 + McNemar 配对检验（纯标准库）。

用法:
  python tools\paper_stats_ci.py <tag>                       # 单组：率 + Wilson 95% CI
  python tools\paper_stats_ci.py <tagA> <tagB>               # 两组：配对 McNemar（按 i 对齐）

读 reports\paper\results\forward_per_reaction__<tag>.jsonl（字段 i / hit / class）。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RES = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\results")


def load(tag):
    p = RES / ("forward_per_reaction__%s.jsonl" % tag)
    out = {}
    for line in open(p, encoding="utf-8"):
        d = json.loads(line)
        if "error" in d:
            continue
        out[d["i"]] = bool(d["hit"])
    return out


def wilson(k, n, z=1.959964):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - hw), min(1.0, c + hw)


def mcnemar_exact_p(b, c):
    """两侧精确二项检验（H0: 失衡概率 0.5），X~Bin(b+c, 0.5)。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("用法: paper_stats_ci.py <tag> [tagB]")
        return 2
    A = load(args[0])
    k, n = sum(A.values()), len(A)
    lo, hi = wilson(k, n)
    print("%s：%d/%d = %.2f%%（Wilson 95%% CI %.2f–%.2f%%）"
          % (args[0], k, n, 100 * k / n, 100 * lo, 100 * hi))
    if len(args) >= 2:
        B = load(args[1])
        ks, ns = sum(B.values()), len(B)
        lo2, hi2 = wilson(ks, ns)
        print("%s：%d/%d = %.2f%%（Wilson 95%% CI %.2f–%.2f%%）"
              % (args[1], ks, ns, 100 * ks / ns, 100 * lo2, 100 * hi2))
        common = sorted(set(A) & set(B))
        b_ = sum(1 for i in common if A[i] and not B[i])
        c_ = sum(1 for i in common if (not A[i]) and B[i])
        p = mcnemar_exact_p(b_, c_)
        print("McNemar（配对 n=%d）：A-only %d · B-only %d · p(精确) = %.3g"
              % (len(common), b_, c_, p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
