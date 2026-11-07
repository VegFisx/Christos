# -*- coding: utf-8 -*-
r"""给「气相 ΔG 已知不可靠」的规则加上 thermo_unreliable 标记。

依据：tools/refine_hydrolysis_boundary.py 的实测
  符号【错】：酯水解 +13.2 / 糖苷水解 +11.0 / 酰胺水解 +34.6 /
              亚胺水解 +13.0 / 内酰胺开环 +88.3
  符号【对】：环氧化物开环 -28.5 / 烯烃水合 -69.3 / 烯酮水合 -15.4

所以：
  · 水解类里除「环氧化物开环成二醇」外，全部标记
  · 「环氧化物开环」是加成开环（张力释放驱动），气相算得准，不标
"""
import json
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
F = STAGE / "rules" / "rules.json"

UNRELIABLE = {
    "hydrolysis_ester_001",
    "hydrolysis_glycoside_001",
    "hydrolysis_amide_001",
    "hydrolysis_sulfate_001",
    "hydrolysis_phosphate_001",
    "hydrolysis_acetal_001",
    "hydrolysis_hemiacetal_001",
    "hydrolysis_imine_001",
    "hydrolysis_lactam_001",
}
# 明确【不】标记的：
#   hydrolysis_epoxide_001  加成开环，实测 ΔG = -28.5（符号正确）

NOTE = ("气相 xTB 的 ΔG 对本规则【符号系统性错误】（水解由溶剂化熵驱动，气相算不出），"
        "已在 scorer.assign_thermo 里跳过 —— 不让已知错误的信号影响排序。"
        "实测见 tools/refine_hydrolysis_boundary.py")

d = json.loads(F.read_text(encoding="utf-8"))
rules = d["rules"]
marked, unmarked = [], []
for r in rules:
    if r["id"] in UNRELIABLE:
        r["thermo_unreliable"] = True
        if NOTE not in (r.get("notes") or ""):
            r["notes"] = ((r.get("notes") or "").rstrip() + " 【" + NOTE + "】").strip()
        marked.append(r["name"])
    elif r.get("thermo_unreliable"):
        r.pop("thermo_unreliable", None)
        unmarked.append(r["name"])

F.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"已标记 {len(marked)} 条为 thermo_unreliable：")
for n in marked:
    print(f"   · {n}")
print()
print("未标记（保留 ΔG 信号）：")
for r in rules:
    if r.get("status") == "disabled":
        continue
    if r["id"] in ("hydrolysis_epoxide_001", "hydration_alkene_001",
                   "hydration_enone_001"):
        print(f"   · {r['name']}")
print()
print(f"规则总数 {len(rules)}，"
      f"标记数 {sum(1 for r in rules if r.get('thermo_unreliable'))}")
