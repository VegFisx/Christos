# -*- coding: utf-8 -*-
"""收尾：手工补两条规则的配平系数，并把状态定档。

推导器的缺口：它只走 rdchiral，而 rdchiral 不支持双反应物，
所以 6 条双反应物规则在它眼里都是"(无产物)"。
这些规则的配平由【校验器】负责（校验器有双反应物分支），不是推导器。
"""
import json
from pathlib import Path
from collections import Counter

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

# 手工补配平（推导器「模式不认识」，但化学很清楚）
MANUAL = {
    "elimination_amide_to_nitrile_001": {
        "co_reagents": {}, "byproducts": {"H2O": 1},
        "why": "酰胺 → 腈 + 水。差值 {H:-2, O:-1} 正是脱去一个水分子。",
    },
    "reduction_sulfoxide_001": {
        # ★注意★ 这里一度写成 {"H2: 1"}——冒号在引号【里面】，
        #   那在 Python 里是「含一个字符串的集合」而不是字典，
        #   JSON 序列化会直接失败。已改正。
        "co_reagents": {"H2": 1}, "byproducts": {"H2O": 1},
        "why": "亚砜 + H2 → 硫醚 + 水。差值 {O:-1}，两边补氢与水即配平。",
    },
}

for rid, patch in MANUAL.items():
    if rid not in by_id:
        continue
    by_id[rid]["co_reagents"] = patch["co_reagents"]
    by_id[rid]["byproducts"] = patch["byproducts"]
    by_id[rid]["notes"] = by_id[rid].get("notes", "") + f" 【手工配平】{patch['why']}"
    print(f"[配平] {by_id[rid]['name']:<16} co={patch['co_reagents']} by={patch['byproducts']}")

# 状态定档
TO_VERIFY = ["cyclization_hemiacetal_001", "cyclization_lactam_001",
             "decarboxylation_cinnamic_001"]
TO_ACTIVE = ["elimination_amide_to_nitrile_001", "oxidation_sulfoxide_to_sulfone_001",
             "reduction_sulfoxide_001",
             "condensation_glycosylation_001", "condensation_hemiacetal_001",
             "addition_michael_thiol_001", "addition_michael_amine_001",
             "condensation_aldol_001", "addition_thiohemiacetal_001"]

for rid in TO_VERIFY:
    if rid in by_id and by_id[rid].get("status") == "draft":
        by_id[rid]["status"] = "verify"
        by_id[rid]["priority"] = min(float(by_id[rid].get("priority", 0.3)), 0.1)
        by_id[rid]["notes"] = by_id[rid].get("notes", "") + \
            " 【自动校验：rdchiral 产不出产物，标记待复核】"
        print(f"[复核] {by_id[rid]['name']}")

for rid in TO_ACTIVE:
    if rid in by_id and by_id[rid].get("status") == "draft":
        by_id[rid]["status"] = "active"
        print(f"[转正] {by_id[rid]['name']}")

def _find_bad(o, path="root"):
    bad = []
    if isinstance(o, set):
        bad.append((path, "set", sorted(map(str, o))[:3]))
    elif isinstance(o, dict):
        for k, v in o.items():
            bad += _find_bad(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            bad += _find_bad(v, f"{path}[{i}]")
    elif not isinstance(o, (str, int, float, bool, type(None))):
        bad.append((path, type(o).__name__, repr(o)[:50]))
    return bad


_bad = _find_bad(data)
if _bad:
    print("★写文件前发现不可序列化的值★")
    for p, t, v in _bad:
        print(f"    {p}  ->  {t}  {v}")
else:
    print("写文件前检查：干净")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
c = Counter(r.get("status") for r in data["rules"])
print(f"\n规则总数 {len(data['rules'])}")
for k, v in c.most_common():
    print(f"   {str(k):<10}{v}")
