# -*- coding: utf-8 -*-
r"""
审计 10 个工艺模板本身的【参数化学合理性】
============================================

前面审过：规则在某个工艺下该不该激活。
**但从没审过：工艺模板自己的温度/时间/pH/溶剂合不合理。**

比如：
  · 醇提  溶剂乙醇 → 沸点 78°C ✓
  · 煎煮  水 → 100°C ✓
  · 酶催化 酶在多少度还能工作？超过 ~60°C 就变性了
  · 碱水解 pH 应该是碱性（>10），酸水解应该是酸性（<2）

本脚本把 10 个模板的参数摊开，逐条判断。
"""
import sys
from pathlib import Path

# Windows 控制台是 GBK：本脚本打印 ✓/✗/中文，必须自己重设编码（AGENTS.md 第七节）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "conditions"))
for d in ("rules", "core", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

import templates as T
from model import SOLVENTS, CATALYSTS, ATMOSPHERES

print("=" * 104)
print("① 全部工艺模板的参数")
print("=" * 104)
names = sorted(T.TEMPLATES)
print(f"  共 {len(names)} 个模板: {names}")
print()

FIELDS = ["solvent", "temperature", "time_min", "pH", "catalyst", "atmosphere"]
print(f"  {'模板':<12}" + "".join(f"{f:>13}" for f in FIELDS))
print("  " + "-" * 92)
rows = {}
for n in names:
    c = T.get_template(n)
    vals = {f: getattr(c, f, None) for f in FIELDS}
    rows[n] = vals
    print(f"  {n:<12}" + "".join(f"{str(vals[f]):>13}" for f in FIELDS))

print()
print("=" * 104)
print("② 逐条化学核查")
print("=" * 104)
PASS, FAIL = [], []

def chk(label, cond, detail=""):
    (PASS if cond else FAIL).append(label)
    print(f"  {'✓' if cond else '✗'} {label}   {detail}")

# 煎煮
c = rows.get("煎煮", {})
chk("煎煮 温度应在 95~105（水沸）",
    c.get("temperature") is not None and 95 <= c["temperature"] <= 105,
    f"实测 {c.get('temperature')}")
chk("煎煮 溶剂应为水", str(c.get("solvent")).lower() in ("water", "aqueous"),
    f"实测 {c.get('solvent')}")
chk("煎煮 pH 应接近中性",
    c.get("pH") is not None and 5.0 <= c["pH"] <= 8.0, f"实测 {c.get('pH')}")

# 醇提
c = rows.get("醇提", {})
chk("醇提 溶剂应为乙醇/醇",
    "alcohol" in str(c.get("solvent")).lower() or "ethanol" in str(c.get("solvent")).lower(),
    f"实测 {c.get('solvent')}")
chk("醇提 温度应接近乙醇沸点 78",
    c.get("temperature") is not None and 60 <= c["temperature"] <= 85,
    f"实测 {c.get('temperature')}")

# 酸水解
c = rows.get("酸水解", {})
chk("酸水解 pH 应强酸性（<3）",
    c.get("pH") is not None and c["pH"] < 3.0, f"实测 {c.get('pH')}")
chk("酸水解 温度应 ≥ 80",
    c.get("temperature") is not None and c["temperature"] >= 80,
    f"实测 {c.get('temperature')}")

# 碱水解
c = rows.get("碱水解", {})
chk("碱水解 pH 应强碱性（>10）",
    c.get("pH") is not None and c["pH"] > 10.0, f"实测 {c.get('pH')}")

# 氧化
c = rows.get("氧化", {})
chk("氧化 气氛应有氧",
    str(c.get("atmosphere")) in ("air", "O2"), f"实测 {c.get('atmosphere')}")

# 还原
c = rows.get("还原", {})
chk("还原 气氛应为氢气",
    str(c.get("atmosphere")) == "H2", f"实测 {c.get('atmosphere')}")

# 无氧煎煮
c = rows.get("无氧煎煮", {})
chk("无氧煎煮 气氛不应有氧",
    str(c.get("atmosphere")) not in ("air", "O2"), f"实测 {c.get('atmosphere')}")

# ★ 酶催化 —— 最可疑的
c = rows.get("酶催化", {})
t = c.get("temperature")
ph = c.get("pH")
chk("★酶催化 温度应在酶可存活范围（≤60）",
    t is not None and t <= 60, f"实测 {t}   ← 超过 60°C 酶会变性")
chk("★酶催化 pH 应在酶活范围（3~9）",
    ph is not None and 3.0 <= ph <= 9.0, f"实测 {ph}")
chk("★酶催化 应有催化剂（酶）",
    bool(c.get("catalyst")), f"实测 {c.get('catalyst')}")

# 水提
c = rows.get("水提", {})
chk("水提 溶剂应为水", str(c.get("solvent")).lower() in ("water", "aqueous"),
    f"实测 {c.get('solvent')}")
chk("水提 温度不应高于沸点",
    c.get("temperature") is not None and c["temperature"] <= 105,
    f"实测 {c.get('temperature')}")

print()
print("=" * 104)
print("③ 模板名 vs 目标的 8 种工艺")
print("=" * 104)
NEEDED = ["煎煮", "水提", "醇提", "酸水解", "碱水解", "氧化", "还原", "酶催化"]
for n in NEEDED:
    ok = n in T.TEMPLATES
    print(f"  {'✓' if ok else '✗'} {n}")
extra = [n for n in names if n not in NEEDED]
print(f"\n  额外的模板（目标没要求但实现了）: {extra}")

print()
print("=" * 104)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print(f"  ✗ {f}")
print("=" * 104)

print()
print("=" * 104)
print("合法取值的定义域（供参考）")
print("=" * 104)
print(f"  SOLVENTS    = {sorted(SOLVENTS)}")
print(f"  CATALYSTS   = {sorted(x for x in CATALYSTS if x)}")
print(f"  ATMOSPHERES = {sorted(ATMOSPHERES)}")
