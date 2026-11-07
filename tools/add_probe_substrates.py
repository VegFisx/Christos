# -*- coding: utf-8 -*-
r"""给规则加「人工指定底物」（probe_substrates），堵掉一个反复踩的坑。

问题回顾（本项目已踩三次）：
  · 丙二酸型脱羧   —— 校验器说"无底物匹配"，手工一测（丙二酸、乙酰乙酸）全部正确
  · 肉桂酸型脱羧   —— 同上（肉桂酸、咖啡酸、阿魏酸）
  · 分子内酰胺化   —— 同上（4-氨基丁酸）

根因：tcm.db 里没有这几类分子（β-二羰基酸、肉桂酸型、γ-氨基丁酸型）。
      校验器在真实底物上跑，样本里没有就只能报「NO_SUBSTRATE」，
      而这个结论【既不能证实也不能证伪】——很容易被误读成"规则坏了"。

解法：规则可以声明 probe_substrates —— 人工指定的、化学上必定能匹配的底物。
      校验器优先用数据库底物；数据库覆盖不到时，用手工底物补验。
      两条路都没有匹配，才算真有问题。
"""
import json
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
F = STAGE / "rules" / "rules.json"
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

# 每条规则配 2~4 个"化学上必定能匹配"的底物
PROBES = {
    "decarboxylation_malonic_001": [
        {"smiles": "OC(=O)CC(=O)O", "name": "丙二酸"},
        {"smiles": "CC(=O)CC(=O)O", "name": "乙酰乙酸"},
    ],
    "decarboxylation_cinnamic_001": [
        {"smiles": "OC(=O)/C=C/c1ccccc1", "name": "肉桂酸"},
        {"smiles": "OC(=O)/C=C/c1ccc(O)c(O)c1", "name": "咖啡酸"},
        {"smiles": "OC(=O)/C=C/c1ccc(O)c(OC)c1", "name": "阿魏酸"},
    ],
    "cyclization_lactam_001": [
        {"smiles": "NCCCC(=O)O", "name": "4-氨基丁酸"},
        {"smiles": "NCCCCC(=O)O", "name": "5-氨基戊酸"},
    ],
    "cyclization_hemiacetal_001": [
        {"smiles": "O=CCCCO", "name": "4-羟基丁醛"},
        {"smiles": "O=CCCCCO", "name": "5-羟基戊醛"},
    ],
    "hydrolysis_sulfate_001": [
        {"smiles": "COS(=O)(=O)O", "name": "硫酸单甲酯"},
    ],
    "hydrolysis_imine_001": [
        {"smiles": "CN=Cc1ccccc1", "name": "N-甲基苯甲亚胺"},
    ],
    "oxidation_amine_001": [
        {"smiles": "CCc1ccccc1N", "name": "邻乙基苯胺"},
        {"smiles": "CCN", "name": "乙胺"},
    ],
    "decarboxylation_beta_keto_001": [
        {"smiles": "CC(=O)CC(=O)O", "name": "乙酰乙酸"},
    ],
    "reduction_nitro_001": [
        {"smiles": "C[N+](=O)[O-]", "name": "硝基甲烷"},
    ],
    "addition_michael_thiol_001": [
        {"smiles": "C=CC=O", "name": "丙烯醛"},
    ],
}

n = 0
for rid, probes in PROBES.items():
    r = by_id.get(rid)
    if r is None:
        print(f"[跳过] 没有规则 {rid}")
        continue
    r["probe_substrates"] = probes
    n += 1
    print(f"[加底物] {r['name']:<22} {len(probes)} 个: "
          f"{', '.join(p['name'] for p in probes)}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n共给 {n} 条规则加了人工指定底物")
print(f"规则总数 {len(data['rules'])}")
