# -*- coding: utf-8 -*-
r"""
真实底物用例：底物取自 tcm.db，期望产物来自化学计量。
========================================================

用户原则：不要手写数据。

本模块的设计：
  1. 底物按【名字】从 tcm.db 取 —— 找不到就报错，无法悄悄替换成手写值
  2. 期望产物用【分子式】写 —— 手写复杂天然产物 SMILES 已经错过三次；
     而且内嵌字典给出【化学计量推导】，期望值不是我"照抄引擎输出"
  3. 每条用例都写明"为什么是这个分子式"

复现：python tools\db_cases.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")
from engine import Compound, load_engine
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds
import templates as T

engine, rules, profs = load_engine()
by_id = {r["id"]: r for r in rules}

# ---------------------------------------------------------------------------
# 用例：底物按名字取(数据库) + 期望分子式(化学计量推导)
# ---------------------------------------------------------------------------
CASES = [
    {
        "id": "db_licorice_aglycone",
        "herb": "甘草", "pick": ["Glycyrrhizic acid", "Glycyrrhizin",
                                 "Ammo-nium glycyrrhizinate"],
        "rule": "hydrolysis_glycoside_001", "condition": "煎煮",
        "expect_formula": ["C30H46O4"],
        "why": "甘草酸 C42H62O16 是甘草次酸(C30H46O4)的二葡萄糖醛酸苷。"
               "切掉 2×C6H10O7 并补 2×H2O：C42H62O16 - C12H20O14 + H4O2 = C30H46O4",
    },
    {
        "id": "db_licorice_monoglucuronide",
        "herb": "甘草", "pick": ["Glycyrrhizic acid", "Glycyrrhizin"],
        "rule": "hydrolysis_glycoside_001", "condition": "煎煮",
        "expect_formula": ["C36H54O10"],
        "why": "只切掉 1 个葡萄糖醛酸的中间体：C42H62O16 - C6H10O7 + H2O = C36H54O10",
    },
    {
        "id": "db_rutin_to_quercetin",
        "herb": "甘草", "pick": ["Rutin"],
        "rule": "hydrolysis_glycoside_001", "condition": "煎煮",
        "expect_formula": ["C15H10O7"],
        "why": "芦丁 C27H30O16 是槲皮素-3-O-芸香糖苷。"
               "C27H30O16 + H2O - C12H22O10(芸香糖) = C15H10O7（槲皮素）",
    },
    {
        "id": "db_baicalin_to_baicalein",
        "herb": "黄芩", "pick": ["Baicalin", "Dihydrobaicalin"],
        "rule": "hydrolysis_glycoside_001", "condition": "煎煮",
        "expect_formula": ["C15H10O5"],
        "why": "黄芩苷 C21H18O11 是黄芩素-7-O-葡萄糖醛酸苷。"
               "C21H18O11 + H2O - C6H10O7 = C15H10O5（黄芩素）",
    },
    {
        "id": "db_lipoaconitine_ester",
        "herb": "附子", "pick": ["Lipoaconitine", "Lipodeoxyaconitine"],
        "rule": "hydrolysis_ester_001", "condition": "煎煮",
        "expect_formula": ["C32H45NO10", "C32H45NO9"],
        "why": "脂乌头碱 C50H75NO11 脱掉长链脂肪酸(C18H30O2)并补 1 个水，"
               "得到苯甲酰乌头原碱型 C32H45NO10 —— 附子减毒的第一步",
    },
]


def pick_compound(herb: str, names):
    """按名字从 tcm.db 取。取不到就返回 None（绝不退回手写值）。"""
    rows = find_compounds(herb, limit=400)
    for want in names:
        for rr in rows:
            if (rr.get("name") or "").strip().lower() == want.strip().lower():
                m = Chem.MolFromSmiles(rr.get("smiles") or "")
                if m:
                    return rr, m
    # 退一步：包含匹配
    for want in names:
        for rr in rows:
            if want.strip().lower() in (rr.get("name") or "").lower():
                m = Chem.MolFromSmiles(rr.get("smiles") or "")
                if m:
                    return rr, m
    return None, None


def main() -> int:
    from rdkit.Chem.rdMolDescriptors import CalcMolFormula

    print("=" * 104)
    print("真实底物用例（底物来自 tcm.db，期望来自化学计量）")
    print("=" * 104)

    PASS, FAIL = [], []
    for c in CASES:
        row, mol = pick_compound(c["herb"], c["pick"])
        if row is None:
            print(f"\n  ✗ {c['id']}: 数据库里找不到 {c['pick']}（{c['herb']}）")
            FAIL.append((c["id"], "底物取不到"))
            continue
        sub_formula = CalcMolFormula(mol)
        r = by_id.get(c["rule"])
        cond = T.get_template(c["condition"])
        sub = Compound(smiles=row["smiles"], name=row["name"], herb=c["herb"])
        prods = engine.apply_rule(r, sub, 0.8, 1, cond)
        got = sorted({p.formula for p in prods})
        ok = any(f in got for f in c["expect_formula"])

        print(f"\n  【{c['id']}】")
        print(f"      底物（数据库）: {row['name']}  {sub_formula}  [{c['herb']}]")
        print(f"      规则          : {r['name']}   工艺 {c['condition']}")
        print(f"      期望产物       : {c['expect_formula']}")
        print(f"      实际产物       : {got}")
        print(f"      依据          : {c['why']}")
        print(f"      {'✓ 通过' if ok else '✗ 失败'}")
        (PASS if ok else FAIL).append((c["id"], "" if ok else f"期望 {c['expect_formula']}，实得 {got}"))

    print()
    print("=" * 104)
    print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
    for cid, why in FAIL:
        print(f"  ✗ {cid}  {why}")
    print("=" * 104)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
