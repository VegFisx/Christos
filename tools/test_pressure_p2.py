# -*- coding: utf-8 -*-
"""压力 P2（沸点上限）+ 浓度因子：口径检查。

跑法：D:\\TCMAI\\venv\\Scripts\\python.exe -I -X utf8 tools\\test_pressure_p2.py

三组断言：
  A 物理量：水/乙醇在若干压力下的沸点（对照 Antoine 与实测值）
  B 浴类型：溶液浴受约束，干热与辅料润湿不受约束
  C 端到端：extent 比较（150 °C 水 @1 atm 必须等于 100 °C；@2 atm 必须高于它），
    以及浓度因子（0.1 M 与 1 M 必须不同）
"""
import io
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "conditions"))

from conditions import pressure as P                     # noqa: E402
from conditions import extent as E                       # noqa: E402
from conditions.model import Conditions                   # noqa: E402

fails = []


def chk(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        fails.append(name)


def near(a, b, tol):
    return abs(float(a) - float(b)) <= tol


print("A 沸点（Clausius-Clapeyron，Tb/ΔHvap 取 CRC 97th）")
for solvent, p, want, tol in [
    ("water", 1.0, 100.0, 0.05),
    ("water", 0.5, 81.3, 0.6),      # Antoine/实测 81.3
    ("water", 2.0, 120.5, 0.8),     # Antoine 120.5；本式 120.8
    ("water", 5.0, 151.9, 2.0),
    ("ethanol", 1.0, 78.3, 0.05),
    # 低压端只有量级意义：ΔHvap 被视为常数，醇类在 0.1 atm 会低估约 3 °C
    # （实测 76 mmHg ≈ 29~30 °C，本式 26.1 °C）。这里只要求落在 20~35 °C 内。
    ("ethanol", 0.1, 27.5, 4.5),
]:
    got = P.t_sat_C(solvent, p)
    chk(f"{solvent} @ {p} atm = {want}±{tol}", got is not None and near(got, want, tol),
        f"got={got}")
chk("未知溶剂返回 None", P.t_sat_C("unobtainium", 1.0) is None)

print("B 浴类型")
bath = [
    ("煎煮", "water", 100.0, "solution"),
    ("炮制·蒸制", "water", 100.0, "steam"),
    ("炮制·炒炭", "none", 260.0, "dry"),
    ("无溶剂（炮制）", "none", 150.0, "dry"),
    ("炮制·盐炙", "water", 150.0, "wetting"),
    ("炮制·酒炙", "ethanol", 140.0, "wetting"),
]
for name, solv, T, want in bath:
    c = Conditions(solvent=solv, temperature=T, time_min=30, pH=7.0, template=name)
    chk(f"{name} → {want}", P.bath_of(c) == want, f"got={P.bath_of(c)}")

print("C 有效温度")
cases = [
    ("煎煮", "water", 100.0, 1.0, 100.0, False),
    ("煎煮", "water", 150.0, 1.0, 100.0, True),      # 常压水超 100 必截断
    ("煎煮", "water", 150.0, 2.0, 120.5, True),      # 加压后允许更高
    ("煎煮", "water", 150.0, 5.0, 150.0, False),     # 5 atm 沸点 151.9 > 150，不截断
    ("炮制·盐炙", "water", 150.0, 1.0, 150.0, False),  # 辅料润湿不截断
    ("炮制·炒炭", "none", 260.0, 1.0, 260.0, False),   # 干热不截断
]
for name, solv, T, p, want, capped in cases:
    c = Conditions(solvent=solv, temperature=T, time_min=30, pH=7.0,
                   pressure_atm=p, template=name)
    got, note = P.effective_temperature(c)
    ok = near(got, want, 1.0) and (bool(note) == capped)
    chk(f"{name} {T}°C @{p}atm → {want}°C{'（截断）' if capped else ''}", ok,
        f"got={got} note={note!r}")

print("D extent 端到端（同一个规则窗口，只改条件）")


def ext(T, p=1.0, conc=0.1, solv="water", tmpl="煎煮", tmin=60.0):
    c = Conditions(solvent=solv, temperature=T, time_min=tmin, pH=7.0,
                   pressure_atm=p, concentration_M=conc, template=tmpl)
    return E.extent_from_profile(
        {"temperature": {"min": 80, "median": 100, "max": 120},
         "time_min": {"min": 30, "median": 60, "max": 120},
         "pH_preference": "acid_base"},
        c)


e100, why100 = ext(100.0)
e150, why150 = ext(150.0, p=1.0)
e150_2, _ = ext(150.0, p=2.0)
e150_5, _ = ext(150.0, p=5.0)
print(f"  extent: 100°C@1atm={e100:.4f}  150°C@1atm={e150:.4f}  "
      f"150°C@2atm={e150_2:.4f}  150°C@5atm={e150_5:.4f}")
chk("150 °C 水 @1 atm 被截到 100 °C（extent 相同）", near(e150, e100, 1e-6),
    f"{e150} vs {e100}")
chk("截断写进说明", "沸点上限" in why150, why150)
chk("加压后 2 atm 的 extent 高于 1 atm", e150_2 > e150 + 1e-6,
    f"{e150_2} vs {e150}")
chk("5 atm 下 150 °C 不再被截断（高于 2 atm 的值）", e150_5 > e150_2 + 1e-6,
    f"{e150_5} vs {e150_2}")

e_c01, _ = ext(100.0, conc=0.1)
e_c10, why_c = ext(100.0, conc=1.0)
print(f"  extent: 0.1 M={e_c01:.4f}  1.0 M={e_c10:.4f}")
chk("浓度 1 M 的 extent 高于 0.1 M", e_c10 > e_c01 + 1e-6, f"{e_c10} vs {e_c01}")
chk("浓度因子写进说明", "浓度" in why_c, why_c)

print()
if fails:
    print(f"FAILED {len(fails)}: {fails}")
    sys.exit(1)
print("ALL PASS")
