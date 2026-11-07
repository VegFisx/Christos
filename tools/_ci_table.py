# -*- coding: utf-8 -*-
r"""一次性：从结果文件读数，生成论文用"关键比例 + Wilson 95% CI"Markdown 表。"""
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

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
RES = STAGE / "reports" / "paper" / "results"


def wil(k, n):
    z = 1.959964
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * p, 100 * (c - hw), 100 * (c + hw)


def from_fwd(fn):
    d = json.loads((RES / fn).read_text(encoding="utf-8"))
    n = d.get("n_reactions") or d.get("n_targets")
    r = d.get("recall_1step")
    k = d.get("any_hit") or (round(r * n) if (r is not None and n) else None)
    return k, n


def from_cov(fn):
    d = json.loads((RES / fn).read_text(encoding="utf-8"))
    return round(d["any_hit_rate"] * d["n_targets"]), d["n_targets"]


def main() -> int:
    rows = [
        ("正向·旧默认（600+903）· 50k 全量",) + from_fwd("forward_50k.json") + ("forward_50k.json",),
        ("正向·全量库 cap8 · 50k 全量",) + from_fwd("forward_50k__full_s10_full50k.json") + ("forward_50k__full_s10_full50k.json",),
        ("正向·全量库 cap32 泄漏版 · 50k",) + from_fwd("forward_50k__cap32_20k_full50k.json") + ("…cap32_20k_full50k.json",),
        ("正向·全量库 cap32 **剔除版** · 50k",) + from_fwd("forward_50k__lf_cap32_20k_full50k.json") + ("…lf_cap32_20k_full50k.json",),
        ("逆向·覆盖率 · s10 全量库(剔除版)",) + from_cov("coverage_summary__lib_uspto50k_excl_v2_s10.json") + ("coverage_…_s10.json",),
        ("逆向·覆盖率 · s10 freq10(剔除版)",) + from_cov("coverage_summary__lib_uspto50k_excl_v2_freq10_s10.json") + ("…freq10_s10.json",),
    ]
    print("| 指标 | 命中/总数 | 比例 | Wilson 95% CI | 来源 |")
    print("|---|---|---|---|---|")
    for name, k, n, src in rows:
        if k is None or not n:
            print("| %s | （缺） | | | %s |" % (name, src))
            continue
        p, lo, hi = wil(k, n)
        print("| %s | %s/%s | **%.2f%%** | %.2f–%.2f%% | %s |" % (name, k, n, p, lo, hi, src))
    # 多步（从 bench_multistep json）
    for tag, name in (("lfreq10_d2b4_n300", "逆向·多步 depth≤2 · n=300"),
                      ("lfreq10_d3b4_n300", "逆向·多步 depth≤3 · n=300"),
                      ("lfreq10_d2b4_n100", "逆向·多步 depth≤2 · n=100")):
        fp = STAGE / "reports" / ("bench_multistep__%s.json" % tag)
        if fp.exists():
            d = json.loads(fp.read_text(encoding="utf-8"))
            k, n = d["success"], d["n_targets"]
            p, lo, hi = wil(k, n)
            print("| %s | %d/%d | **%.2f%%** | %.2f–%.2f%% | bench_multistep__%s.json |"
                  % (name, k, n, p, lo, hi, tag))
    # 可用性（从 usability summary）
    for fn, name in (("usability_summary__lib_uspto50k_excl_v2_c100.json", "逆向·可用率(v2 全量, B6 默认)"),
                     ("usability_summary__lib_uspto50k_excl_v2_freq10_c100.json", "逆向·可用率(freq10, B6 默认)")):
        fp = RES / fn
        if fp.exists():
            d = json.loads(fp.read_text(encoding="utf-8"))
            k, n = d.get("usable") or round(d["usable_rate"] * d["n_cuts"]), d["n_cuts"]
            p, lo, hi = wil(k, n)
            print("| %s | %d/%d | **%.2f%%** | %.2f–%.2f%% | %s |" % (name, k, n, p, lo, hi, fn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
