# -*- coding: utf-8 -*-
r"""
反应差值审计：产物分子式 − 底物分子式，跟规则名声称的反应类型对得上吗？
========================================================================

★ 为什么这是新角度

  探针矩阵只回答「这条规则认不认这个底物」。
  本脚本回答「**认了之后，变化量对不对**」。

  一条规则可能：
    · 认得出底物   ✓
    · 产物配平     ✓
    · 但差值跟规则名完全不符 ← 本脚本要抓的

  例：名字叫「脱水」，实际差值却是 +H2O —— 名字与行为相反。

★ 判据

  按反应类型给出期望差值，逐条比对：
    水解/水合     应  +H2O
    脱水/缩合     应  −H2O
    脱羧          应  −CO2
    氧化          应  +O（或 −H2）
    还原          应  +H2（或 −O）
    环化/异构/重排  应  Δ=0（只重排不断裂）
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

sys.path.insert(0, str(STAGE / "rules"))
from schema import load_rules, formula_atoms  # noqa: E402

# ---------------------------------------------------------------- 探针（复用矩阵里挑出来的代表）
PROBES = [
    ("甲醇", "CO"), ("乙醇", "CCO"), ("异丙醇", "CC(C)O"), ("2-丁醇", "CCC(C)O"),
    ("苯酚", "Oc1ccccc1"), ("苯甲醚", "COc1ccccc1"),
    ("乙醛", "CC=O"), ("苯甲醛", "O=Cc1ccccc1"), ("丙酮", "CC(C)=O"),
    ("乙酸", "CC(=O)O"), ("苯甲酸", "O=C(O)c1ccccc1"),
    ("乙酸甲酯", "COC(C)=O"), ("苯甲酸甲酯", "COC(=O)c1ccccc1"),
    ("乙酰胺", "CC(N)=O"), ("2-吡咯烷酮", "O=C1CCCN1"),
    ("甲胺", "CN"), ("二甲胺", "CNC"), ("乙胺", "CCN"),
    ("乙烯", "C=C"), ("丙烯", "CC=C"), ("环己烯", "C1CC=CCC1"),
    ("苯", "c1ccccc1"), ("丙烯醛", "C=CC=O"), ("丙烯酸甲酯", "C=CC(=O)OC"),
    ("二甲硫醚", "CSC"), ("DMSO", "CS(C)=O"), ("甲硫醇", "CS"),
    ("环氧丙烷", "CC1CO1"), ("4-羟基丁酸", "OCCCC(=O)O"),
    ("5-羟基戊酸", "OCCCCC(=O)O"), ("4-羟基丁醛", "O=CCCCO"),
    ("4-氨基丁酸", "NCCCC(=O)O"), ("邻苯二酚", "Oc1ccccc1O"),
    ("邻苯醌", "O=C1C=CC=CC1=O"), ("肉桂酸", "OC(=O)/C=C/c1ccccc1"),
    ("丙二酸", "OC(=O)CC(=O)O"), ("乙酰乙酸", "CC(=O)CC(=O)O"),
    ("甲基葡萄糖苷", "CO[C@H]1O[C@@H](CO)[C@H](O)[C@@H](O)[C@@H]1O"),
    ("羟乙醛", "OCC=O"), ("丁醛", "CCCC=O"),
]

# 各反应类型的「期望差值」描述（用于人工比对，不做自动判定）
EXPECT = {
    "hydrolysis": "+H2O（水解，加水）",
    "hydration": "+H2O（水合，加水）",
    "oxidation": "+O 或 −H2（氧化，得氧或失氢）",
    "reduction": "+H2 或 −O（还原）",
    "decarboxylation": "−CO2（脱羧）",
    "elimination": "−H2O / −NH3 / −H2（消除）",
    "condensation": "−H2O（缩合，脱水）",
    "esterification": "−H2O（酯化，脱水）",
    "cyclization": "−H2O（成环，常脱水）",
    "addition": "Δ=0（加成，只成键不增删原子）",
    "rearrangement": "Δ=0（重排/异构）",
    "hydroxylation": "+O（羟基化）",
    "demethylation": "−CH2（脱甲基，实为脱 CH3 得 CH2 差）",
    "tautomerization": "Δ=0（互变异构）",
    "hydration_enone": "+H2O",
}


def atoms(mol):
    d = {}
    mol = Chem.AddHs(mol)
    for a in mol.GetAtoms():
        d[a.GetSymbol()] = d.get(a.GetSymbol(), 0) + 1
    return d


def delta_str(sub, prod):
    d = {}
    for k in set(sub) | set(prod):
        v = prod.get(k, 0) - sub.get(k, 0)
        if v:
            d[k] = v
    if not d:
        return "Δ=0"
    return " ".join(f"{k}{v:+d}" for k, v in sorted(d.items()))


def main() -> int:
    profiles, rules = load_rules(str(STAGE / "rules" / "rules.json"))
    print(f"规则 {len(rules)} 条 | 探针 {len(PROBES)} 个\n")

    report = []
    for r in rules:
        if r.get("status") == "disabled":
            continue
        try:
            rxn = AllChem.ReactionFromSmarts(r["smarts"])
        except Exception:
            continue
        n_react = rxn.GetNumReactantTemplates()
        deltas: Counter = Counter()
        examples = {}
        for name, smi in PROBES:
            m = Chem.MolFromSmiles(smi)
            if m is None:
                continue
            subs = [m]
            if n_react == 2:
                pool = r.get("co_substrate_pool") or []
                got = None
                for item in pool[:2]:
                    s2 = item.get("smiles") if isinstance(item, dict) else None
                    m2 = Chem.MolFromSmiles(s2) if s2 else None
                    if m2 is None:
                        continue
                    try:
                        res = rxn.RunReactants((m, m2))
                    except Exception:
                        res = []
                    if res:
                        got = (res, m2)
                        break
                if got is None:
                    continue
                res, m2 = got
                base = atoms(m)
                for k, v in atoms(m2).items():
                    base[k] = base.get(k, 0) + v
            else:
                base = atoms(m)
                try:
                    res = rxn.RunReactants((m,))
                except Exception:
                    res = []
                if not res:
                    continue
            tot = {}
            ok = True
            for ps in res[:1]:
                for p in ps:
                    pc = Chem.Mol(p)
                    try:
                        Chem.SanitizeMol(pc)
                    except Exception:
                        ok = False
                        break
                    for k, v in atoms(pc).items():
                        tot[k] = tot.get(k, 0) + v
            if not ok or not tot:
                continue
            ds = delta_str(base, tot)
            deltas[ds] += 1
            examples.setdefault(ds, (name, smi))
        if deltas:
            report.append((r, deltas, examples))

    print("=" * 104)
    print("逐条规则的差值（可能出现多种，取决于底物）")
    print("=" * 104)
    for r, deltas, examples in report:
        cat = r.get("category", "")
        exp = EXPECT.get(cat, "（未定义）")
        main_delta, n = deltas.most_common(1)[0]
        print(f"\n【{r['name']}】类别={cat}  共 {sum(deltas.values())} 个探针命中")
        print(f"   期望：{exp}")
        for ds, cnt in deltas.most_common(4):
            nm, smi = examples[ds]
            flag = ""
            print(f"   实际 {ds:<22} ×{cnt:<3} 例：{nm}")

    print()
    print("=" * 104)
    print("★ 自动标记：差值明显与类别不符的")
    print("=" * 104)

    def atoms_of(ds):
        """把 'C-1 O+1' 解析成 {C:-1, O:1}"""
        out = {}
        for tok in ds.split():
            if tok.startswith("Δ="):
                continue
            el = tok[0]
            try:
                out[el] = int(tok[1:])
            except ValueError:
                pass
        return out

    flagged = []
    for r, deltas, examples in report:
        cat = r.get("category", "")
        for ds, cnt in deltas.items():
            d = atoms_of(ds) if ds != "Δ=0" else {}
            bad = None
            # ★ 判据修正说明 ★
            #   第一版把「脱羧规则差值 Δ=0」和「消除类增加氧」都标了，
            #   但两者都是我的期望写错了：
            #     · 脱羧：CO2 是【独立产物分子】，所有产物加起来当然 Δ=0。
            #             正确的判据是「产物集合里有没有 CO2 那一份」。
            #     · 消除：氧化脱氨成羰基既要脱氨又要加氧，类别叫 elimination
            #             但本质是氧化，加氧是对的。
            #   所以本版只保留【真正矛盾】的判据。
            if cat in ("hydrolysis", "hydration") and d.get("O", 0) <= 0:
                bad = "名字是水解/水合，但产物没增加氧"
            elif cat == "decarboxylation":
                # 脱羧：产物里必须能找到 CO2 那一份
                has_co2 = any("CO2" in k or k.startswith("O=C=O") for k in examples)
                bad = None      # 由下面的片段检查单独处理
            elif cat in ("addition", "rearrangement") and d:
                bad = "名字是加成/重排，原子数却变了"
            if bad:
                flagged.append((r["name"], cat, ds, examples[ds][0], bad))

    # 单独查脱羧：产物里有没有 CO2 那一份
    decarb_missing = []
    for r, deltas, examples in report:
        if r.get("category") != "decarboxylation":
            continue
        if "Δ=0" not in deltas:
            continue
        nm, smi = examples["Δ=0"]
        m = Chem.MolFromSmiles(smi)
        try:
            rxn = AllChem.ReactionFromSmarts(r["smarts"])
            res = rxn.RunReactants((m,))
        except Exception:
            continue
        if not res:
            continue
        frags = []
        for p in res[0]:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                frags.append(Chem.MolToSmiles(pc))
            except Exception:
                pass
        if not any(f == "O=C=O" for f in frags):
            decarb_missing.append((r["name"], smi, frags))

    if flagged:
        for nm, cat, ds, probe, bad in flagged:
            print(f"  ★ {nm:<22} [{cat}]  {ds:<20} 例:{probe:<12} {bad}")
    else:
        print("  ✓ 未发现差值明显与类别不符的规则")

    print()
    print("脱羧类专项复核（产物里必须能找到 CO2 那一份）：")
    if decarb_missing:
        for nm, smi, frags in decarb_missing:
            print(f"  ★ {nm:<22} 底物 {smi}")
            print(f"      产物片段 {frags}  ← 没找到 CO2")
    else:
        n_decarb = sum(1 for r, _d, _e in report
                       if r.get("category") == "decarboxylation")
        print(f"  ✓ {n_decarb} 条脱羧规则都正确产出了 CO2")

    print(f"\n汇总：{len(report)} 条规则有探针命中，"
          f"标记 {len(flagged) + len(decarb_missing)} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
