# -*- coding: utf-8 -*-
"""修 cyclization_ether_001：产物写成 O-O 键，是化学错误。

原 SMARTS 产物：[O:1]1[CX4:2][CX4:3][CX4:4][O:5]1
    → 环是 O1-C2-C3-C4-O5-O1，含 **O-O 键**，成了 1,2-二氧戊环。
    二元醇脱水成环醚，正确的环只应含【一个】氧。

正确写法（1,4-丁二醇 → 四氢呋喃）：
    反应物  [OX2H:1][CX4:2][CX4:3][CX4:4][CX4:5][OX2H:6]
    产物    [O:1]1[CX4:2][CX4:3][CX4:4][CX4:5]1 . [OH2:6]
    环      O1-C2-C3-C4-C5-O1   ← 5 元环，只有一个氧 ✓
    平衡    C4H10O2 → C4H8O + H2O ✓

★ 教训：原子守恒可以被「编一个副产物」糊弄过去。
  原写法之所以通过了自动校验，是因为推导器给它配了 byproducts={'H2':1}
  （说它产氢气）——数字对上了，化学却是错的。
  校验器是必要条件，不是充分条件。
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))

FIX = {
    "id": "cyclization_ether_001",
    "smarts": ("[OX2H:1][CX4:2][CX4:3][CX4:4][CX4:5][OX2H:6]"
               ">>[O:1]1[CX4:2][CX4:3][CX4:4][CX4:5]1.[OH2:6]"),
    "co_reagents": {},
    "byproducts": {},
    "status": "draft",
    "priority": 0.3,
    "max_products_per_molecule": 1,
    "notes": ("★已修★ 原产物 [O:1]1[CX4:2][CX4:3][CX4:4][O:5]1 会形成 O-O 键"
              "（1,2-二氧戊环），化学错误；而且它之所以通过原子守恒校验，"
              "是因为推导器给它编了个 byproducts={'H2':1}——数字对上了化学是错的。"
              "新写法：[O:1]1[...][CX4:5]1 只让【一个】氧进环，水作为副产物。"
              "待重新校验。"),
}

n = 0
for r in data["rules"]:
    if r["id"] == FIX["id"]:
        before = r["smarts"]
        r.update({k: v for k, v in FIX.items() if k != "id"})
        n += 1
        print("原 SMARTS:", before)
        print("新 SMARTS:", r["smarts"])
        print("co_reagents:", r["co_reagents"], " byproducts:", r["byproducts"])
        break

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n已修 {n} 条")

from collections import Counter
c = Counter(r.get("status") for r in data["rules"])
print(f"规则总数 {len(data['rules'])}，状态：{dict(c)}")
