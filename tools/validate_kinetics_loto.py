#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""对已经登记文献数据做「留一温度交叉验证」，检验 Arrhenius/Ea 能不能外推。

为什么要做：
    conditions/kinetics.json 的温度依赖现在用 Arrhenius，Ea=103.6 kJ/mol，
    来自同一篇文献的三个温度（80/94/105 °C）三点拟合。**三点拟合出来的 Ea 是否可信，
    只有做留一验证才知道**——用两个温度拟合、预测第三个，看差多少。
    如果误差是 2~3 倍，那么「按 Ea 外推到别的温度再据此过滤产物」就没有依据。

口径：
    1. 只用时间序列数据集（times_min + conversion），已报告 k 的直接用 k。
    2. 每个温度一个 k：过原点拟合 -ln(1-y)=kt。
    3. 留一：用其余温度拟合 ln k vs 1/T 的直线，预测被留下的温度，报告 预测/实测 比值。
    4. 同时给出两两 Q10，和我们配置里 Q10=2.0 对比。

用法：
    python tools/validate_kinetics_loto.py [-o reports/kinetics_loto.json]
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
T0 = 273.15
R = 8.314462618


def fit_k(times, conv):
    """过原点最小二乘：-ln(1-y) = k t。返回 (k_per_min, r2)。"""
    xs, ys = [], []
    for t, y in zip(times, conv):
        if t and 0.0 < y < 1.0:
            xs.append(float(t))
            ys.append(-math.log(1.0 - float(y)))
    if len(xs) < 2:
        return None, None
    num = sum(x * y for x, y in zip(xs, ys))
    den = sum(x * x for x in xs)
    k = num / den
    ss_res = sum((y - k * x) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - sum(ys) / len(ys)) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return k, r2


def series_k(meas):
    """按温度收集 k：list of dict(T_c, k_per_min, r2, n, id, group)。"""
    out = []
    for ds in meas.get("datasets", []):
        T = ds.get("temp_C")
        if T is None:
            continue
        grp = ds.get("reaction") or "unknown"
        if ds.get("k_per_h"):
            k = float(ds["k_per_h"]) / 60.0
            out.append({"id": ds["id"], "T_c": float(T), "k_per_min": k,
                        "r2": None, "n": 0, "from": "reported_k", "group": grp})
            continue
        times, conv = ds.get("times_min"), ds.get("conversion")
        if times and conv:
            k, r2 = fit_k(times, conv)
            if k:
                out.append({"id": ds["id"], "T_c": float(T), "k_per_min": k,
                            "r2": None if r2 is None else round(r2, 4),
                            "n": len(times), "from": "time_series", "group": grp})
    return out


def arrhenius_fit(points):
    """points: [(T_c, k)] → (Ea_kJ, ln_A)。"""
    xs = [1.0 / (p[0] + T0) for p in points]
    ys = [math.log(p[1]) for p in points]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    inter = my - slope * mx
    ea = -slope * R / 1000.0
    return ea, inter


def q10(k1, t1, k2, t2):
    return (k2 / k1) ** (10.0 / (t2 - t1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="reports/kinetics_loto.json")
    args = ap.parse_args()

    meas = json.loads(MEAS.read_text(encoding="utf-8"))
    pts = series_k(meas)
    if len(pts) < 3:
        print("有效温度点不足 3 个，无法做留一验证")
        return 2

    groups = {}
    for p in pts:
        groups.setdefault(p["group"], []).append(p)

    print("可用于温度依赖分析的数据点（按反应分组，**不同反应不能混算 Ea**）：")
    for g, ps in groups.items():
        print("  [%s] %d 个温度点" % (g, len(ps)))
        for p in sorted(ps, key=lambda x: x["T_c"]):
            print("     %-22s %6.1f °C  k=%.4g /min  r2=%s  (%s, n=%d)" % (
                p["id"], p["T_c"], p["k_per_min"], p["r2"], p["from"], p["n"]))

    rows = []
    group_summary = {}
    for g, ps in groups.items():
        if len(ps) < 3:
            # 两个温度只能给一条直线，做不了留一；只报 Ea 供参考
            if len(ps) == 2:
                ea, _ = arrhenius_fit([(p["T_c"], p["k_per_min"]) for p in ps])
                group_summary[g] = {"n_points": 2, "ea_kJ": round(ea, 1),
                                    "loto": [], "verdict": "two_points_no_loto"}
            continue
        worst = 0.0
        for held in sorted(ps, key=lambda x: x["T_c"]):
            rest = [p for p in ps if p is not held]
            if len(rest) < 2:
                continue
            ea, ln_a = arrhenius_fit([(p["T_c"], p["k_per_min"]) for p in rest])
            pred = math.exp(ln_a - ea * 1000.0 / (R * (held["T_c"] + T0)))
            ratio = pred / held["k_per_min"]
            worst = max(worst, abs(math.log10(ratio)))
            rows.append({"group": g, "held_out": held["id"], "T_c": held["T_c"],
                         "k_measured": held["k_per_min"], "k_predicted": pred,
                         "pred_over_meas": round(ratio, 3),
                         "ea_from_rest_kJ": round(ea, 1),
                         "log10_ratio": round(math.log10(ratio), 3)})
            print("     留出 %-22s %6.1f °C  预测/实测 = %.2f  (其余点 Ea=%.1f kJ/mol)"
                  % (held["id"], held["T_c"], ratio, ea))
        ea_all, _ = arrhenius_fit([(p["T_c"], p["k_per_min"]) for p in ps])
        verdict = ("extrapolation_unreliable" if worst > 0.3 else
                   "acceptable_with_caution" if worst > 0.15 else "supported")
        group_summary[g] = {"n_points": len(ps), "ea_all_kJ": round(ea_all, 1),
                            "worst_log10_error": round(worst, 3),
                            "verdict": verdict}
        print("     → 全点 Ea = %.1f kJ/mol；留一最差 %.2f 数量级 → %s"
              % (ea_all, worst, verdict))

    # 两两 Q10（只在同组内算）
    qs = []
    for g, ps in groups.items():
        srt = sorted(ps, key=lambda x: x["T_c"])
        for a in range(len(srt)):
            for b in range(a + 1, len(srt)):
                if srt[b]["T_c"] == srt[a]["T_c"]:
                    continue
                v = q10(srt[a]["k_per_min"], srt[a]["T_c"],
                        srt[b]["k_per_min"], srt[b]["T_c"])
                qs.append({"group": g, "from": srt[a]["id"], "to": srt[b]["id"],
                           "dT_c": srt[b]["T_c"] - srt[a]["T_c"], "q10": round(v, 2)})

    rb = group_summary.get("hydrolysis_glycoside_rb1", {})
    worst_all = max((s.get("worst_log10_error", 0) for s in group_summary.values()),
                    default=0.0)
    verdict_all = ("extrapolation_unreliable" if worst_all > 0.3 else
                   "acceptable_with_caution" if worst_all > 0.15 else "supported")
    print("\n汇总：")
    for g, s in group_summary.items():
        print("  %-34s %s" % (g, json.dumps(s, ensure_ascii=False)))
    print("总体判定：%s（最差 %.2f 数量级 = %.1f×）"
          % (verdict_all, worst_all, 10 ** worst_all))

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "conditions/kinetics_measurements.json",
        "points": pts,
        "loto": rows,
        "q10_pairs": qs,
        "groups": group_summary,
        "ea_configured_kJ": 103.6,
        "worst_log10_error": round(worst_all, 3),
        "verdict": verdict_all,
        "criteria": "worst |log10(pred/meas)| > 0.3 → extrapolation_unreliable；"
                    "0.15~0.3 → acceptable_with_caution；< 0.15 → supported",
        "note": ("留一验证只检验『温度依赖能否外推』，不检验绝对转化率；"
                 "不同温度的 rb1_*_2020 数据集来自不同年份/批次的人参"
                 "（105 °C 用 2018 年根，94/80 °C 用 2014 年根），批次差异会混进 Ea；"
                 "不同反应之间绝不能合并拟合 Ea。"),
    }
    p = ROOT / args.out
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出 %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
