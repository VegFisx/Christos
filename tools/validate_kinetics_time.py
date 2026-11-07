#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""时间维度能不能用：对每条实测时间序列做「留一时间点」验证。

为什么单独验时间：
    温度维度已经判死（第一百二十三轮，留一温度误差 2~3 倍）。
    时间维度的数据质量完全不同——同一台仪器、同一批样品、同一次实验里取的 4~8 个时间点，
    所以可以问一个更严格的问题：**用其余时间点拟合出来的 k，能不能预测被留出的那个点？**

口径（全部来自数据，不含任何手写参数）：
    - 一阶模型 y(t) = 1 - exp(-k t)，k 由其余点过原点最小二乘拟合；
    - 预测被留出的转化率，误差按**绝对转化率**计（比 log 误差更贴近"产物在不在"的用法）；
    - 数据集少于 4 个时间点的跳过（留一后只剩 2 个点，拟合没有余量）。

判定阈值（写死在脚本里，随输出一起记录）：
    max|err| ≤ 0.05 → supported；≤ 0.10 → acceptable_with_caution；否则 unreliable。

用法：
    python tools/validate_kinetics_time.py [-o reports/kinetics_time_loto.json]
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
MEAS = ROOT / "conditions" / "kinetics_measurements.json"


def fit_k(times, conv):
    xs, ys = [], []
    for t, y in zip(times, conv):
        if t and 0.0 < y < 1.0:
            xs.append(float(t))
            ys.append(-math.log(1.0 - float(y)))
    if len(xs) < 2:
        return None
    num = sum(x * y for x, y in zip(xs, ys))
    den = sum(x * x for x in xs)
    return num / den if den else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="reports/kinetics_time_loto.json")
    args = ap.parse_args()

    meas = json.loads(MEAS.read_text(encoding="utf-8"))
    rows, skipped = [], []
    for ds in meas.get("datasets", []):
        times, conv = ds.get("times_min"), ds.get("conversion")
        if not times or not conv:
            skipped.append({"id": ds["id"], "why": "no_time_series"})
            continue
        pairs = [(float(t), float(y)) for t, y in zip(times, conv)
                 if 0.0 < float(y) < 1.0]
        if len(pairs) < 4:
            skipped.append({"id": ds["id"], "why": "fewer_than_4_points",
                            "n": len(pairs)})
            continue

        errs = []
        for i in range(len(pairs)):
            rest = pairs[:i] + pairs[i + 1:]
            k = fit_k([p[0] for p in rest], [p[1] for p in rest])
            if not k:
                continue
            t_hold, y_meas = pairs[i]
            y_pred = 1.0 - math.exp(-k * t_hold)
            errs.append({"t_min": t_hold, "measured": round(y_meas, 4),
                         "predicted": round(y_pred, 4),
                         "abs_err": round(abs(y_pred - y_meas), 4)})
        if not errs:
            skipped.append({"id": ds["id"], "why": "fit_failed"})
            continue
        worst = max(e["abs_err"] for e in errs)
        mean = sum(e["abs_err"] for e in errs) / len(errs)
        verdict = ("supported" if worst <= 0.05 else
                   "acceptable_with_caution" if worst <= 0.10 else "unreliable")
        rows.append({"id": ds["id"], "reaction": ds.get("reaction"),
                     "temp_C": ds.get("temp_C"), "n_points": len(pairs),
                     "max_abs_err": round(worst, 4), "mean_abs_err": round(mean, 4),
                     "verdict": verdict, "detail": errs})
        print("%-24s %-10s %6s  n=%d  max|err|=%.3f  mean=%.3f  → %s"
              % (ds["id"], ds.get("reaction", "?")[:10],
                 ds.get("temp_C"), len(pairs), worst, mean, verdict))
        for e in errs:
            print("      t=%7.0f min  measured=%.3f predicted=%.3f err=%.3f"
                  % (e["t_min"], e["measured"], e["predicted"], e["abs_err"]))

    ok = [r for r in rows if r["verdict"] in ("supported", "acceptable_with_caution")]
    overall = ("supported" if rows and len(ok) == len(rows) else
               "partially_supported" if ok else "unreliable")
    print("\n可用数据集 %d 个，通过 %d 个 → 总体 %s"
          % (len(rows), len(ok), overall))
    if skipped:
        print("跳过：" + ", ".join("%s(%s)" % (s["id"], s["why"]) for s in skipped))

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "conditions/kinetics_measurements.json",
        "model": "first_order y = 1 - exp(-k t), k fitted on remaining points",
        "criteria": "max|err| <= 0.05 supported; <= 0.10 acceptable_with_caution; else unreliable",
        "overall": overall,
        "datasets": rows,
        "skipped": skipped,
        "note": ("误差按绝对转化率计；这些序列来自同一批实验，"
                 "所以本验证只说明'时间维度在这个体系内可预测'，"
                 "不说明跨体系、跨基质可迁移。"),
    }
    p = ROOT / args.out
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出 %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
