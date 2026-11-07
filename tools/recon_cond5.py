# -*- coding: utf-8 -*-
r"""量门控的"松紧"：① 手工 profile 的条件窗口有多宽 ② 64 条规则用了哪个 profile
   ③ ORD 真实条件分布（温度/溶剂/催化剂）长什么样。
不评分、不预测，只报事实。
"""
import json
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")

d = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))
rules, profiles = d["rules"], d["profiles"]

print("=" * 92)
print("① 手工 profile 的窗口宽度（越宽 = 门控越松）")
print("=" * 92)
for name, p in profiles.items():
    t = p.get("temperature") or {}
    ph = p.get("pH") or {}
    print(f"  {name:<12} 温度 {t.get('min')}~{t.get('max')}   "
          f"pH {ph.get('min')}~{ph.get('max')}   "
          f"溶剂 {p.get('solvent')}  催化剂 {p.get('catalyst')}  气氛 {p.get('atmosphere')}")

print()
print("=" * 92)
print("② 64 条规则用的 profile 分布")
print("=" * 92)
use = {}
for r in rules:
    use[r.get("condition_profile")] = use.get(r.get("condition_profile"), 0) + 1
for k, v in sorted(use.items(), key=lambda x: -x[1]):
    print(f"  {str(k):<16} {v} 条")

print()
print("=" * 92)
print("③ ORD 条件表：温度/溶剂/催化剂的真实分布")
print("=" * 92)
cond = json.loads((STAGE / "reports" / "conditions_by_reaction_type.json").read_text(encoding="utf-8"))
print(f"{'反应类型':<34}{'温度':>22}{'溶剂(前2)':<34}")
for k, v in sorted(cond.items(), key=lambda x: -x[1].get("n_ord_matched", 0))[:16]:
    t = v.get("temp_C")
    ts = "无" if t is None else (f"{t.get('min')}~{t.get('max')} 默认{t.get('default')}"
                                 if isinstance(t, dict) else str(t))
    sol = ",".join(str(s)[:14] for s in (v.get("solvents") or [])[:2])
    print(f"{k[:33]:<34}{ts:>22}  {sol[:32]:<34}")
print()
# 温度统计
temps = []
for v in cond.values():
    t = v.get("temp_C")
    if isinstance(t, dict) and t.get("default") is not None:
        temps.append((t["default"], v.get("n_ord_matched", 0)))
temps.sort()
print("37 类里有默认温度的:", len(temps), "/ 37")
if temps:
    print("  温度默认值分布（升序，前 12）:", [f"{t}°C(n={n})" for t, n in temps[:12]])
    print("  温度默认值分布（升序，后 6） :", [f"{t}°C(n={n})" for t, n in temps[-6:]])
