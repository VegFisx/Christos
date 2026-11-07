# -*- coding: utf-8 -*-
import json
from pathlib import Path

p = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\conditions_by_reaction_type.json")
d = json.load(open(p, encoding="utf-8"))
print(f"反应类型总数: {len(d)}")
zero = [k for k, v in d.items() if v["n_ord_matched"] == 0]
print(f"ORD 命中 0 条的类型 {len(zero)} 个:")
for k in zero:
    print("   ", k)
print()
for k in ["mitsunobu", "ullmann_X", "chan_lam", "snar_alcohol", "C_C_decarboxylation"]:
    e = d.get(k)
    if not e:
        print(f"【{k}】不在表里")
        continue
    print(f"【{k}】ORD命中 {e['n_ord_matched']}  温度={e['temp_C']}")
    print(f"    催化剂={e['catalysts']}")
    print(f"    溶剂={e['solvents'][:4]}")
    print(f"    试剂={e['reagents'][:4]}")
    print(f"    类别={e['template_categories'][:4]}")
