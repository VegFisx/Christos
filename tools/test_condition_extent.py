# -*- coding: utf-8 -*-
"""单测：反应进程层（conditions/extent.py）+ kinetics.json 参数形状。

跑法（Windows GBK 控制台也能直接跑）：
    D:\\TCMAI\\venv\\Scripts\\python.exe tools\\test_condition_extent.py
退出码 0 = 全过；非 0 = 有失败（会打印每一条）。
"""
from __future__ import annotations

import sys
import traceback
from dataclasses import replace
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_STAGE = Path(__file__).resolve().parent.parent
for _p in (_STAGE / "core", _STAGE / "conditions", _STAGE / "rules", _STAGE / "libs"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import extent as ex                     # noqa: E402
import templates as T                   # noqa: E402
from schema import load_rules, resolve_conditions  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        FAILED.append(name)


def approx(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol


def main():
    params = ex.load_params()
    profs, rules = load_rules(_STAGE / "rules" / "rules.json")
    hyd = next(r for r in rules if r.get("condition_profile") == "hydrolysis"
               and r.get("status") != "disabled")
    resolved, _ = resolve_conditions(hyd, profs)
    base = T.get_template("煎煮")

    print("== 1. 参数形状（kinetics.json）==")
    check("q10 在 1.5~4 之间", 1.5 <= float(params["q10"]["value"]) <= 4.0,
          params["q10"])
    check("extent_min < extent_major",
          float(params["gates"]["extent_min"]) < float(params["gates"]["extent_major"]))
    check("extent_min 已改为 0.0 且标记 removed_no_source",
          float(params["gates"]["extent_min"]) == 0.0
          and str((params.get("gates_provenance") or {})
                  .get("extent_min", {}).get("status")) == "removed_no_source")
    check("痕量阈值 trace_below 来自数据集（0.05）",
          approx(float(params["gates"]["trace_below"]), 0.05, 1e-9)
          and str((params.get("gates_provenance") or {})
                  .get("trace_below", {}).get("status")) == "derived_from_dataset")
    _mdc = ex.min_documented_conversion()
    check("痕量阈值不高于文献最小可观测转化率（0.059）",
          _mdc is not None and float(params["gates"]["trace_below"]) <= _mdc + 1e-12,
          f"min_documented={_mdc}")
    check("即使打开门控也不会删除文献可报告的产物（extent_min <= 0.059）",
          float(params["gates"]["extent_min"]) <= (_mdc or 0.0))
    check("催化剂倍数 none = 1.0",
          approx((params["catalyst_speedup"].get("none") or 1.0), 1.0))

    print("== 2. 参照点：profile 默认条件 -> e≈1-1/e =0.632 ==")
    e0, _ = ex.extent_from_profile(resolved, base)
    check("煎煮 hydrolysis ≈ 0.632", approx(e0, 0.632, 0.02), f"得 {e0:.4f}")

    print("== 3. 单调性 ==")
    ts = [5, 60, 240, 1440]
    es = [ex.extent_from_profile(resolved, replace(base, time_min=t))[0] for t in ts]
    check("时间越长 extent 不减", all(b >= a - 1e-9 for a, b in zip(es, es[1:])), es)
    check("5min 明显小于 1440min", es[0] < es[-1] / 4, es)
    Ts = [25, 60, 100, 150]
    et = [ex.extent_from_profile(resolved, replace(base, temperature=t))[0] for t in Ts]
    check("温度越高 extent 不减", all(b >= a - 1e-9 for a, b in zip(et, et[1:])), et)
    ea = ex.extent_from_profile(resolved, replace(base, catalyst="acid"))[0]
    check("加酸催化剂 extent 上升", ea >= e0, f"{e0:.3f} -> {ea:.3f}")

    print("== 4. pH：两侧最优（acid_base），中性最低 ==")
    ph = {p: ex.extent_from_profile(resolved, replace(base, pH=p))[0] for p in (2, 7, 12)}
    check("pH2 与 pH12 都高于 pH7", ph[2] > ph[7] and ph[12] > ph[7], ph)
    check("pH 对称性（2 与 12 差 < 0.2）", approx(ph[2], ph[12], 0.2), ph)

    print("== 5. 档位 ==")
    g = params["gates"]
    check("band 0 -> none（痕量）", ex.band_of(0.0) == "none", ex.band_of(0.0))
    check("band trace_below 处 -> minor", ex.band_of(float(g["trace_below"])) == "minor")
    check("band extent_major -> major", ex.band_of(float(g["extent_major"])) == "major")
    check("band 1.0 -> major", ex.band_of(1.0) == "major")

    print("== 6. 缺数据策略 ==")
    e1, w1 = ex.extent_from_table(None, base)
    check("无 ORD 数据 -> 1.0 放行", approx(e1, 1.0), w1)
    e2, _ = ex.extent_from_table({"temp_C": None, "time_min": None}, base)
    check("缺温度/时间参照 -> 1.0 放行", approx(e2, 1.0))

    print("== 7. 极端值不炸 ==")
    for t in (0.0, 1e-6, 1e6):
        e = ex.extent_from_profile(resolved, replace(base, time_min=t))[0]
        check(f"time_min={t} 在 [0,1]", 0.0 <= e <= 1.0, e)
    for T_ in (-20.0, 500.0):
        e = ex.extent_from_profile(resolved, replace(base, temperature=T_))[0]
        check(f"T={T_} 在 [0,1]", 0.0 <= e <= 1.0, e)
    e = ex.extent_from_profile(resolved, replace(base, pH=0.0))[0]
    check("pH=0 在 [0,1]", 0.0 <= e <= 1.0, e)

    print("== 8. 解释文本 ==")
    _e, why = ex.extent_from_profile(resolved, replace(base, time_min=5))
    check("why 非空", bool(why.strip()), repr(why))
    check("explains 返回字符串", isinstance(ex.explains(0.3, why, params), str))

    print("== 9. 温度判据（第 85 轮 A 案）==")
    tp = params.get("temperature") or {}
    tol = float(tp.get("gate_low_tolerance_C", 30.0))
    ceil = float(tp.get("hot_ceiling_C", 400.0))
    print(f"   容差 {tol:g}°C / 上限 {ceil:g}°C")
    lo, hi = 20.0, 150.0                     # hydrolysis 档的窗口
    s, _w, dead = ex.temperature_gate(lo, hi, 100.0, params)
    check("窗口内 -> 1.0 且不死", s == 1.0 and not dead, f"{s} dead={dead}")
    s, _w, dead = ex.temperature_gate(lo, hi, 250.0, params)
    check("高温（>上限）不判死、不降权", s == 1.0 and not dead, f"{s} dead={dead}")
    s, _w, dead = ex.temperature_gate(lo, hi, 10.0, params)
    check("略低于下限 -> 降权但不死", 0.0 < s < 1.0 and not dead, f"{s} dead={dead}")
    s, _w, dead = ex.temperature_gate(lo, hi, lo - tol - 1.0, params)
    check("低于下限-容差 -> 判死", dead and s == 0.0, f"{s} dead={dead}")
    s, _w, dead = ex.temperature_gate(lo, hi, ceil + 1.0, params)
    check("超过 hot_ceiling -> 判死", dead and s == 0.0, f"{s} dead={dead}")
    s, _w, dead = ex.temperature_gate(None, None, 100.0, params)
    check("没有窗口 -> 放行", s == 1.0 and not dead, f"{s} dead={dead}")
    # 单调性：只要不判死，温度越高分数不减
    seq = [ex.temperature_gate(lo, hi, T_, params)[0]
           for T_ in (-10, 0, 10, 20, 60, 100, 150, 250, 380)]
    check("温度单调不减", all(b >= a - 1e-9 for a, b in zip(seq, seq[1:])), seq)

    # ==== 10. 温度模型：Arrhenius（第一百一十四轮）====
    import math as _m
    p2 = ex.load_params()
    ea = ex._arrhenius_ea(p2)
    check("默认启用 Arrhenius 且 Ea>0", ea is not None and ea > 0, f"Ea={ea}")
    R = float((p2.get("arrhenius") or {}).get("R", 8.314462618))
    for T_ in (60.0, 80.0, 120.0, 200.0):
        want = _m.exp(-(ea * 1000.0) / R * (1.0 / (T_ + 273.15) - 1.0 / (100.0 + 273.15)))
        got = ex.temperature_factor(T_, 100.0, p2)
        check(f"Arrhenius 手算吻合 T={T_:g}°C", abs(got - want) / want < 1e-9,
              f"got={got:.6f} want={want:.6f}")
    check("参照温度处因子=1", abs(ex.temperature_factor(100.0, 100.0, p2) - 1.0) < 1e-12)
    seq2 = [ex.temperature_factor(T_, 100.0, p2) for T_ in (25, 60, 80, 100, 150, 250)]
    check("因子随温度单调递增", all(b > a for a, b in zip(seq2, seq2[1:])),
          [f"{x:.4f}" for x in seq2])
    check("极端低温不炸（下限截断）", 0.0 < ex.temperature_factor(-100.0, 100.0, p2) <= 1.0)
    check("极端高温不炸（上限截断）", ex.temperature_factor(2000.0, 100.0, p2) <= 1e6)
    p_q10 = __import__("copy").deepcopy(ex.load_params())
    p_q10["arrhenius"] = dict(p_q10.get("arrhenius") or {})
    p_q10["arrhenius"]["enabled"] = False
    f_arr = ex.temperature_factor(80.0, 100.0, p2)
    f_q10 = ex.temperature_factor(80.0, 100.0, p_q10)
    check("关闭 Arrhenius 回退 Q10 且低温更宽", abs(f_q10 - 0.25) < 1e-9 and f_arr < f_q10,
          f"arr={f_arr:.4f} q10={f_q10:.4f}")
    e_ref = ex._extent_core(60, 60, 100, 100, 1.0, 1.0, p2)
    check("参照点 extent 仍为 0.632", abs(e_ref - 0.632) < 5e-4, f"{e_ref:.4f}")
    check("低温（25°C/1h）extent < 0.01", ex._extent_core(60, 60, 25, 100, 1.0, 1.0, p2) < 0.01)

    class _C:                                  # 最小 run 对象（只要四个字段）
        temperature = 100.0
        time_min = 60.0
        pH = 6.5
        catalyst = None

    _e, why = ex.extent_from_profile(
        {"temperature": {"default": 100}, "time_min": {"default": 60},
         "pH": {"default": 6.5}, "catalyst": [], "pH_preference": "acid_base"},
        _C(), p2)
    check("why 里写明 Arrhenius 与 Ea", "Arrhenius" in why, why[:70])

    # ==== 11. 按反应族取 Ea（第一百一十五轮）====
    p3 = __import__("copy").deepcopy(ex.load_params())
    ea_hyd = ex._arrhenius_ea(p3, "hydrolysis")
    ea_thm = ex._arrhenius_ea(p3, "thermal")
    ea_unk = ex._arrhenius_ea(p3, "no_such_profile")
    ea_none = ex._arrhenius_ea(p3, None)
    check("hydrolysis 用自己的 Ea=103.6", ea_hyd is not None and abs(ea_hyd - 103.6) < 1e-9,
          f"Ea={ea_hyd}")
    check("thermal 用自己的 Ea=215.7", ea_thm is not None and abs(ea_thm - 215.7) < 1e-9,
          f"Ea={ea_thm}")
    check("未知 profile 回退全局 Ea", ea_unk == ex._arrhenius_ea(p3) == ea_none,
          f"unk={ea_unk} none={ea_none}")
    f_hyd = ex.temperature_factor(160.0, 100.0, p3, "hydrolysis")
    f_thm = ex.temperature_factor(160.0, 100.0, p3, "thermal")
    check("Ea 越大，同温下的加速倍数越大", f_thm > f_hyd > 1.0,
          f"thermal={f_thm:.3f} hydrolysis={f_hyd:.3f}")
    e_hyd = ex._extent_core(1, 60, 110, 100, 1.0, 1.0, p3, "hydrolysis")
    e_thm = ex._extent_core(1, 60, 110, 100, 1.0, 1.0, p3, "thermal")
    check("同条件（110°C/1min）热档 extent 高于水解族（Ea 更大）",
          e_thm > e_hyd > 0 and e_thm < 1.0,
          f"thermal={e_thm:.4f} hydrolysis={e_hyd:.4f}")
    _e2, why2 = ex.extent_from_table(
        {"condition_profile": "thermal",
         "temp_C": {"min": 140, "median": 165, "max": 220},
         "time_min": {"min": 5, "median": 10, "max": 35},
         "ph_preference": "any"},
        type("C2", (), {"temperature": 195.0, "time_min": 10.0, "pH": 7.0,
                        "catalyst": None})(), p3)
    check("extent_from_table 认得 entry 里的 condition_profile", "profile=thermal" in why2,
          why2[:80])
    p_off = __import__("copy").deepcopy(p3)
    p_off["arrhenius"] = dict(p_off.get("arrhenius") or {})
    p_off["arrhenius"]["enabled"] = False
    check("关闭后 profile 也回退全局（_arrhenius_ea -> None）",
          ex._arrhenius_ea(p_off, "thermal") is None)

    # == 12. 标定区间与外推标注（第 123 轮）==
    rng_hyd = ex.calibrated_range(p3, "hydrolysis")
    rng_thm = ex.calibrated_range(p3, "thermal")
    check("hydrolysis 标定区间 = 80~105°C",
          rng_hyd is not None and abs(rng_hyd[0] - 80.0) < 1e-9
          and abs(rng_hyd[1] - 105.0) < 1e-9, f"{rng_hyd}")
    check("thermal 标定区间 = 140~160°C",
          rng_thm is not None and abs(rng_thm[0] - 140.0) < 1e-9
          and abs(rng_thm[1] - 160.0) < 1e-9, f"{rng_thm}")
    check("未登记的 profile 返回 None", ex.calibrated_range(p3, "no_such_profile") is None)
    policy = ((p3.get("arrhenius") or {}).get("extrapolation") or {}).get("policy")
    check("kinetics.json 明确禁止外推（policy=forbidden）", policy == "forbidden", f"{policy}")
    _res = {"temperature": {"min": 20, "max": 150, "default": 100},
            "time_min": {"min": 5, "max": 240, "default": 60},
            "pH": {"min": 0, "max": 14, "default": 7},
            "pH_preference": "any"}
    _run_in = type("C3", (), {"temperature": 100.0, "time_min": 60.0, "pH": 7.0,
                              "catalyst": None})()
    _run_out = type("C4", (), {"temperature": 300.0, "time_min": 60.0, "pH": 7.0,
                               "catalyst": None})()
    _e_in, why_in = ex.extent_from_profile(_res, _run_in, p3, profile="hydrolysis")
    _e_out, why_out = ex.extent_from_profile(_res, _run_out, p3, profile="hydrolysis")
    check("区间内不出现外推标注", "属外推" not in why_in, why_in[:100])
    check("区间外（300°C）标注「属外推」", "属外推" in why_out, why_out[:120])
    check("外推标注不改变数值口径（300°C 的 extent 仍按公式给出）",
          isinstance(_e_out, float) and 0.0 <= _e_out <= 1.0, f"{_e_out:.4f}")

    print()
    if FAILED:
        print(f"FAILED {len(FAILED)}: {FAILED}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
