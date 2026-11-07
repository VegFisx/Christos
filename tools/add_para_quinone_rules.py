# -*- coding: utf-8 -*-
r"""补上「对位醌 / 对位二酚」两条规则，把论文承诺过却没实现的缺口补掉。

★ 背景
  论文 TableS1 里「酚氧化成醌」的说明写着「邻苯二酚氧化为邻苯醌（多酚聚合起始）」
  另一处写「醌还原：邻醌还原为邻苯二酚（丹参酮、大黄蒽醌等）」。
  但两条规则的 SMARTS 都只认【邻位】（两个官能团的碳直接相连）：
      酚氧化成醌  [OH:1][c:2][c:3][OH:4]
      醌还原     [O:1]=[C:2][C:3]=[O:4]
  而蒽醌的两个 C=O 在 9、10 位，中间隔着环碳，相距 3 个键 → 匹配不上。

  实测确认：9,10-蒽醌、大黄素，两个版本都匹配不上。
  → 论文说明承诺了蒽醌，实现里从来没有。

★ 新增两条

  对位二酚氧化   [OH:1][c:2][c:5][c:6][c:3][OH:4]>>[O:1]=[C:2][c:5][c:6][C:3]=[O:4]

  对醌还原      [O:1]=[C:2]~[#6:5]~[#6:6]~[C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]
                ★ 反应物侧的键必须写 ~（任意键）★
                  对苯醌的环是 单-双-单 交替，SMARTS 默认键只认单键/芳香键，
                  不写 ~ 的话路径跨过双键就匹配失败。
                  而产物侧【不能】写 ~ —— 写了 RDKit 不敢判定芳香性，
                  会给碳补氢，产物分子式多 2 个氢。

  实测（各 6 个底物）：
      只改反应物键   → 命中 0/6（分子式全错）
      只改产物键     → 命中 3/6（对苯醌、辅酶Q0型匹配不上）
      反应物 ~ + 产物默认 → ★ 命中 6/6 ★
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
existing = {r["id"] for r in data["rules"]}

NEW = [
    {
        "id": "oxidation_diphenol_para_001",
        "name": "对二酚氧化成醌",
        "category": "oxidation",
        "smarts": ("[OH:1][c:2][c:5][c:6][c:3][OH:4]"
                   ">>[O:1]=[C:2][c:5][c:6][C:3]=[O:4]"),
        "reversible": True,
        "co_reagents": {},
        "byproducts": {"H2": 1},
        "condition_profile": "oxidation",
        "priority": 0.5,
        "max_products_per_molecule": 1,
        "status": "draft",
        "probe_substrates": [
            {"smiles": "Oc1ccc(O)cc1", "name": "对苯二酚"},
            {"smiles": "Oc1ccc(O)c2ccccc12", "name": "1,4-二羟基萘"},
            {"smiles": "Oc1c2ccccc2c(O)c2ccccc12", "name": "蒽氢醌"},
        ],
        "notes": ("★新增★ 补上论文里承诺却从未实现的【对位】醌/二酚这一类。"
                  "论文「醌还原」的说明写着「丹参酮、大黄蒽醌等」，"
                  "但原 SMARTS 只认两个官能团【直接相连】的邻位——"
                  "蒽醌的两个 C=O 在 9、10 位、相距 3 个键，从来匹配不上。"
                  "本规则处理对位（1,4-）：对苯二酚→对苯醌、"
                  "1,4-萘二酚→1,4-萘醌、蒽氢醌→9,10-蒽醌、大黄素。"
                  "实测不误匹配邻苯二酚（那是「酚氧化成醌」的活）。"),
    },
    {
        "id": "reduction_quinone_para_001",
        "name": "对醌还原成二酚",
        "category": "reduction",
        "smarts": ("[O:1]=[C:2]~[#6:5]~[#6:6]~[C:3]=[O:4]"
                   ">>[OH:1][c:2][c:5][c:6][c:3][OH:4]"),
        "reversible": True,
        "co_reagents": {"H2": 1},
        "byproducts": {},
        "condition_profile": "reduction",
        "priority": 0.5,
        "max_products_per_molecule": 1,
        "status": "draft",
        "probe_substrates": [
            {"smiles": "O=C1C=CC(=O)C=C1", "name": "对苯醌"},
            {"smiles": "O=C1C=CC(=O)c2ccccc21", "name": "1,4-萘醌"},
            {"smiles": "O=C1c2ccccc2C(=O)c2ccccc21", "name": "9,10-蒽醌"},
        ],
        "notes": ("★新增★ 与「对二酚氧化成醌」配对，补上对位（1,4-）醌这一类。"
                  "★★键类型陷阱★★ SMARTS 里不写键符号时默认是【单键或芳香键】。"
                  "对苯醌的环是 单-双-单 交替，所以 [C:2][#6:5][#6:6][C:3] 里的"
                  "中间键匹配不上 → 对苯醌一条都产不出。"
                  "改成 ~（任意键）才能匹配。"
                  "但产物侧【不能】写 ~：写了 RDKit 不敢判定芳香性、会给碳补氢，"
                  "产物分子式多 2 个氢。实测「反应物 ~ + 产物默认键」命中 6/6。"),
    },
]

added = []
for r in NEW:
    if r["id"] in existing:
        print(f"[跳过] {r['id']} 已存在")
        continue
    data["rules"].append(r)
    added.append(r["name"])

# 相互设为配对关系（写进备注即可，引擎不依赖）
F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"新增 {len(added)} 条：{added}")
print(f"规则总数 {len(data['rules'])}")
