# -*- coding: utf-8 -*-
"""按目标是否带手性拆分正向结果，并给出 Wilson 95% CI。

用法：python tools/analyze_forward_stereo_split.py [tag ...]
默认分析冻结运行、stereo_cmp_off、stereo_cmp_on 三个结果。
"""
import json
import math
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path("D:/ProgramData/DSHNS/chemreact-staging")
RES = STAGE / "reports/paper/results"
TARGETS = STAGE / "reports/paper/data/uspto50k_canon.jsonl"

targets = {}
for line in open(TARGETS, encoding="utf-8"):
    r = json.loads(line)
    targets[r["i"]] = r["product"]


def wilson(h, n, z=1.96):
    if n <= 0:
        return 0.0, 0.0
    p = h / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return 100.0 * (centre - half), 100.0 * (centre + half)


def report(tag):
    path = RES / ("forward_per_reaction__%s.jsonl" % tag)
    if not path.exists():
        print("%s: missing %s" % (tag, path.name))
        return
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    groups = {
        "overall": rows,
        "chiral": [r for r in rows if "@" in targets.get(r["i"], "")],
        "achiral": [r for r in rows if "@" not in targets.get(r["i"], "")],
    }
    parts = []
    for name, lst in groups.items():
        ok = [r for r in lst if "error" not in r]
        h = sum(1 for r in ok if r.get("hit"))
        n = len(ok)
        lo, hi = wilson(h, n)
        parts.append("%s=%d/%d=%.2f%% (%.2f-%.2f)" % (
            name, h, n, 100.0 * h / max(1, n), lo, hi))
    vals = [r.get("n_products", 0) for r in rows if "error" not in r]
    mean_cand = sum(vals) / max(1, len(vals))
    print("%s: %s mean_cand=%.1f" % (tag, " | ".join(parts), mean_cand))


def main():
    tags = sys.argv[1:] or ["lf_cap32_20k_full50k", "stereo_cmp_off", "stereo_cmp_on"]
    for t in tags:
        report(t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
