# -*- coding: utf-8 -*-
r"""新规则的收尾修正。

三件事：
  1. 「对二酚氧化成醌」的副产物从 H2 改成 O2/H2O —— 与库内其它氧化规则一致
     （扫描抓到的：oxidation 类写 H2 不合理）
  2. 「对醌还原成二酚」加一条说明，并把酸酐的过度匹配记为已知局限
  3. 探针矩阵补上「对苯醌」——否则新规则在矩阵里 0 命中

★ 关于酸酐的过度匹配
   [O:1]=[C:2]~[#6:5]~[#6:6]~[C:3]=[O:4] 会匹配四氢邻苯二甲酸酐——
   因为酸酐的两个 C=O 碳之间除了「C-O-C」这条近路，
   还有一条绕环走碳的远路。
   试了 5 种约束（环内键 @、环成员 R、组合）都排除不掉。
   酸酐在中药里罕见，暂记为已知局限，不为此牺牲 5 个真醌的命中。
"""
import json
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
F = STAGE / "rules" / "rules.json"
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

# ---- 1. 对二酚氧化成醌：副产物改 O2/H2O ----
r = by_id.get("oxidation_diphenol_para_001")
if r:
    old = (r.get("co_reagents"), r.get("byproducts"))
    r["co_reagents"] = {"O2": 0.5}
    r["byproducts"] = {"H2O": 1}
    r["notes"] = (r.get("notes", "") +
                  " 【一致性修正】副产物原写成 H2（脱氢式），"
                  "但库内其它氧化规则统一用 O2/H2O（有氧煎煮的现实路径）。"
                  "已改为 co={O2:0.5}, by={H2O:1}。")
    print(f"[修] 对二酚氧化成醌  co/by {old} → "
          f"({r['co_reagents']}, {r['byproducts']})")

# ---- 2. 对醌还原成二酚：记已知局限 ----
r = by_id.get("reduction_quinone_para_001")
if r:
    r["notes"] = (r.get("notes", "") +
                  " 【已知局限】~（任意键）会顺带匹配四氢邻苯二甲酸酐这类体系——"
                  "酸酐的两个 C=O 碳之间除了 C-O-C 近路，还有一条绕环走碳的远路。"
                  "试过 5 种约束（环内键 @、环成员 R、两者组合）都排除不掉。"
                  "酸酐在中药里罕见，不为此牺牲 5 个真醌（对苯醌/1,4-萘醌/"
                  "9,10-蒽醌/大黄素/辅酶Q0型）的命中。")
    print("[记] 对醌还原成二酚：已知局限（酸酐过度匹配）")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ---- 3. 探针矩阵补对苯醌 ----
PF = STAGE / "tools" / "probe_matrix.py"
t = PF.read_text(encoding="utf-8")
old = '    "不饱和羰基": [\n        ("丙烯酸甲酯", "C=CC(=O)OC"), ("丁醛", "CCCC=O"), ("邻苯醌", "O=C1C=CC=CC1=O"),\n    ],'
new = ('    "不饱和羰基": [\n        ("丙烯酸甲酯", "C=CC(=O)OC"), ("丁醛", "CCCC=O"),\n'
       '        ("邻苯醌", "O=C1C=CC=CC1=O"),\n'
       '        ("对苯醌", "O=C1C=CC(=O)C=C1"),\n'
       '        ("对苯二酚", "Oc1ccc(O)cc1"),\n'
       '        ("9,10-蒽醌", "O=C1c2ccccc2C(=O)c2ccccc21"),\n'
       '        ("蒽氢醌", "Oc1c2ccccc2c(O)c2ccccc12"),\n    ],')
if old in t:
    t = t.replace(old, new, 1)
    PF.write_text(t, encoding="utf-8")
    print("[补] 探针矩阵：新增 对苯醌 / 对苯二酚 / 9,10-蒽醌 / 蒽氢醌")
else:
    print("★ 探针矩阵未找到插入点")

print(f"\n规则总数 {len(data['rules'])}")
