# -*- coding: utf-8 -*-
"""修复第 6 轮被推导器覆盖坏的那条规则。

美拉德简化：糖的 CH2OH 被氧化成 CHO，这是【氧化】，应当消耗 O2、产出 H2O。
被推导器改成了 by={H2:1}（产氢气）——原子数同样对得上，但化学是错的。

这正是「原子守恒可以被编一个副产物糊弄过去」的活标本，也是必须加
化学合理性检查的原因。
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))

FIX = {
    "co_reagents": {"O2": 0.5},
    "byproducts": {"H2O": 1},
}

n = 0
for r in data["rules"]:
    if r["id"] == "maillard_simplified_001":
        print(f"【{r['name']}】修复前: co={r.get('co_reagents')} by={r.get('byproducts')}")
        r["co_reagents"] = FIX["co_reagents"]
        r["byproducts"] = FIX["byproducts"]
        r["notes"] = (
            "★修复★ 还原糖的 CH2OH 被氧化成 CHO，属【氧化】："
            "消耗半个 O2、产出一个水。"
            "第 6 轮被 derive_co_reagents --apply 覆盖成了 by={H2:1}（产氢气）——"
            "原子数同样配平，所以校验器放行了，直到加上化学合理性检查才暴露。"
            "这类「靠编副产物把原子数凑平」的错误是原子守恒校验的盲区。"
        )
        print(f"       修复后: co={r['co_reagents']} by={r['byproducts']}")
        n += 1

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n修了 {n} 条")
