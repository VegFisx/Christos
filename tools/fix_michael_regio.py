# -*- coding: utf-8 -*-
r"""修 Michael 加成的区域选择性错误。

★★ 这是反应级测试集抓到的第一个【真】化学错误 ★★

问题：
    Michael 加成的定义是「亲核试剂加到 α,β-不饱和羰基的 β 碳上」。
    但原来的 SMARTS 把硫/氮加到了 α 碳上：

    旧: [C:1]=[C:2][C:3]=[OX1:4].[SX2H:5]>>[CX4:1][CX4:2]([S:5])[C:3]=[OX1:4]
                                                       ^^^^^^^^ 加在 C2（α碳）
    新: ...>>[CX4:1]([S:5])[CX4:2][C:3]=[OX1:4]
                ^^^^^^^^ 加在 C1（β碳）

    其中 C1 是末端碳、C2 是 α 碳、C3 是羰基碳。

实证（丙烯醛 CH2=CH-CHO + 甲硫醇 CH3SH）：
    旧 → CSC(C)C=O     （3-甲硫基-2-甲基... 即 α-加成，错）
    新 → CSCCC=O       （3-甲硫基丙醛，β-加成，对）

    丙烯酸甲酯 + 甲硫醇：
    旧 → COC(=O)C(C)SC  错
    新 → COC(=O)CCSC    对

★ 为什么原子守恒校验发现不了 ★
    两个产物分子式完全相同（都是 C4H8OS）——只是连接方式不同。
    所以原子守恒、价态、立体化学三道闸门全都放行。
    **只有"用已知化学答案去卡"的测试集才能发现这类错误。**

同样的问题也存在于 Michael加成(胺)：SMARTS 结构一模一样。
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

FIX = {
    "addition_michael_thiol_001": (
        "[C:1]=[C:2][C:3]=[OX1:4].[SX2H:5]>>[CX4:1]([S:5])[CX4:2][C:3]=[OX1:4]",
        "★已修★ 硫必须加在【β碳】(C1) 上，原来错加在 α碳(C2) 上。"
        "实证：丙烯醛+甲硫醇 → CSCCC=O（3-甲硫基丙醛，正确），"
        "原写法给 CSC(C)C=O（α-加成，错误）。"
        "两个产物分子式相同，原子守恒校验发现不了，是反应级测试集抓出来的。"
    ),
    "addition_michael_amine_001": (
        "[C:1]=[C:2][C:3]=[OX1:4].[NX3H2:5][#6:6]"
        ">>[CX4:1]([N:5][#6:6])[CX4:2][C:3]=[OX1:4]",
        "★已修★ 与 Michael加成(硫醇) 同源的区域选择性错误："
        "氮必须加在【β碳】(C1) 上，原来错加在 α碳(C2) 上。"
    ),
}

for rid, (new_smarts, note) in FIX.items():
    r = by_id.get(rid)
    if r is None:
        print(f"[跳过] {rid} 不存在")
        continue
    print(f"[修] {r['name']}")
    print(f"     旧: {r['smarts']}")
    print(f"     新: {new_smarts}")
    r["smarts"] = new_smarts
    r["notes"] = note
    r["co_reagents"] = {}
    r["byproducts"] = {}

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n规则总数 {len(data['rules'])}")
