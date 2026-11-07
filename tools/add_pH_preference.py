# -*- coding: utf-8 -*-
"""给规则库的条件窗口补两个字段，让条件层真正能区分不同工艺。

1. solvent 列表的**顺序**现在是有意义的：第一个 = 首选溶剂，越靠后越不利。
   实测发现，只把 solvent 当黑名单用的话，"煎煮 vs 醇提"几乎没有差别
   （两者都允许 water 和 alcohol），条件层就成了摆设。

2. 新增 pH_preference：pH 不是"越酸越好"或"越碱越好"，
   而是要看反应类型。酯水解酸碱都能催化（相对中性水都快），
   脱水/脱羧对 pH 不敏感，酶催化要近中性。
   原来把 pH 写成 [1,14] 的宽窗口，等于没约束——实测酸水解和煎煮对酯水解打分完全一样。
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))

# 溶剂列表顺序 = 偏好排序（水优先）。pH_preference 见 activator.py 的取值说明。
UPDATES = {
    "hydrolysis": {
        "solvent": ["water", "aqueous", "alcohol"],
        "pH_preference": "acid_base",   # 酸、碱都能催化水解，中性水最慢
    },
    "oxidation": {
        "solvent": ["water", "aqueous", "alcohol"],
        "pH_preference": "any",
    },
    "reduction": {
        "solvent": ["water", "aqueous", "alcohol"],
        "pH_preference": "any",
    },
    "thermal": {
        # 脱水/脱羧是热驱动，水不是必需的（干热也能发生），醇里也行
        "solvent": ["water", "aqueous", "alcohol", "none"],
        "pH_preference": "any",
    },
    "ambient": {
        "solvent": ["water", "aqueous"],
        "pH_preference": "neutral",     # 酶要近中性
    },
}

for name, patch in UPDATES.items():
    if name not in data["profiles"]:
        print(f"[跳过] 没有条件窗口 {name}")
        continue
    prof = data["profiles"][name]
    before = {k: prof.get(k) for k in patch}
    prof.update(patch)
    print(f"[{name}]")
    for k, v in patch.items():
        old = before.get(k)
        arrow = "" if old == v else f"   （原: {old}）"
        print(f"    {k} = {v}{arrow}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n已写回 {F}")
print(f"条件窗口数: {len(data['profiles'])}")
