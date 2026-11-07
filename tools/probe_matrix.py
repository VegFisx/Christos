# -*- coding: utf-8 -*-
r"""
功能团探针矩阵：用一组小分子系统性扫描全部规则
============================================

★ 为什么需要它

  前两轮的反应级测试集找到了 7 个真 bug，但那是「一条用例一条规则」地碰。
  本脚本换一种打法：**用一组覆盖常见官能团的小分子，去扫全部规则**，
  系统性地找出「该匹配却匹配不上」的规则。

  已发现的三个失败模式里，「氢数写死」和「取代基写死」都表现为
  **对最简单的底物匹配不上**——而最简单的底物恰好都在这个矩阵里。

★ 判据

  · 规则在矩阵里匹配 0 个探针 → 极度可疑（连最简单的官能团都不认）
  · 规则名声称的反应类型，在矩阵里找不到对应底物 → 覆盖缺口
  · 同一反应类型下，某规则明显比别人窄 → 值得复查
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

# ---------------------------------------------------------------- 探针矩阵
# 按官能团分组，每个基团给几个「最简单、最典型」的分子
PROBES = {
    "醇": [
        ("甲醇", "CO"), ("乙醇", "CCO"), ("异丙醇", "CC(C)O"),
        ("叔丁醇", "CC(C)(C)O"), ("苯甲醇", "OCc1ccccc1"),
        ("1,4-丁二醇", "OCCCCO"), ("烯丙醇", "OCC=C"),
        ("2-丁醇", "CCC(C)O"), ("2-丙醇", "CC(C)O"),
    ],
    "酚": [
        ("苯酚", "Oc1ccccc1"), ("邻苯二酚", "Oc1ccccc1O"),
        ("对苯二酚", "Oc1ccc(O)cc1"), ("苯甲醚", "COc1ccccc1"),
    ],
    "醛": [
        ("甲醛", "C=O"), ("乙醛", "CC=O"), ("苯甲醛", "O=Cc1ccccc1"),
        ("丙烯醛", "C=CC=O"), ("2-丁烯醛", "CC=CC=O"), ("羟乙醛", "OCC=O"),
    ],
    "酮": [
        ("丙酮", "CC(C)=O"), ("2-丁酮", "CCC(C)=O"), ("环己酮", "O=C1CCCCC1"),
        ("苯乙酮", "CC(=O)c1ccccc1"), ("乙酰乙酸", "CC(=O)CC(=O)O"),
    ],
    "羧酸": [
        ("甲酸", "OC=O"), ("乙酸", "CC(=O)O"), ("苯甲酸", "O=C(O)c1ccccc1"),
        ("丙二酸", "OC(=O)CC(=O)O"), ("肉桂酸", "OC(=O)/C=C/c1ccccc1"),
        ("5-羟基戊酸", "OCCCCC(=O)O"), ("4-羟基丁酸", "OCCCC(=O)O"),
    ],
    "酯": [
        ("乙酸甲酯", "COC(C)=O"), ("乙酸乙酯", "CCOC(C)=O"),
        ("乙酸苯酯", "CC(=O)Oc1ccccc1"), ("苯甲酸甲酯", "COC(=O)c1ccccc1"),
        ("γ-丁内酯", "O=C1CCCO1"), ("δ-戊内酯", "O=C1CCCCO1"),
    ],
    "酰胺": [
        ("乙酰胺", "CC(N)=O"), ("N-甲基乙酰胺", "CC(=O)NC"),
        ("乙酰苯胺", "CC(=O)Nc1ccccc1"), ("2-吡咯烷酮", "O=C1CCCN1"),
        ("甘氨酰胺", "NCC(N)=O"),
    ],
    "胺": [
        ("甲胺", "CN"), ("乙胺", "CCN"), ("苯胺", "Nc1ccccc1"),
        ("二甲胺", "CNC"), ("2-苯乙胺", "NCCc1ccccc1"), ("4-氨基丁酸", "NCCCC(=O)O"),
    ],
    "烯烃/炔烃": [
        ("乙烯", "C=C"), ("丙烯", "CC=C"), ("环己烯", "C1CC=CCC1"),
        ("1,3-丁二烯", "C=CC=C"),
    ],
    "芳环": [
        ("苯", "c1ccccc1"), ("甲苯", "Cc1ccccc1"),
        ("萘", "c1ccc2ccccc2c1"),
    ],
    "醚/缩醛": [
        ("乙醚", "CCOCC"), ("四氢呋喃", "C1CCOC1"), ("苯甲醛二甲缩醛", "COC(OC)c1ccccc1"),
        ("甲基葡萄糖苷", "CO[C@H]1O[C@@H](CO)[C@H](O)[C@@H](O)[C@@H]1O"),
        ("甲氧基乙醇(半缩醛)", "COC(C)O"),
        ("乙氧基乙醇(半缩醛)", "CCOC(C)O"),
    ],
    "糖苷": [
        ("水杨苷", "C1=CC=C(C(=C1)CO)O[C@H]2[C@@H]([C@H]([C@@H]([C@H](O2)CO)O)O)O"),
        ("熊果苷", "OC[C@H]1O[C@@H](Oc2ccc(O)cc2)[C@H](O)[C@@H](O)[C@@H]1O"),
        ("游离葡萄糖", "OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O"),
        ("4-羟基丁醛", "O=CCCCO"),
        ("5-羟基戊醛", "O=CCCCCO"),
        ("1,5-戊二醇", "OCCCCCO"),
    ],
    "含硫": [
        ("甲硫醇", "CS"), ("二甲硫醚", "CSC"), ("DMSO", "CS(C)=O"),
        ("半胱氨酸", "NC(CS)C(=O)O"), ("硫酸单甲酯", "COS(=O)(=O)O"),
    ],
    "含氮杂环/其它": [
        ("硝基甲烷", "C[N+](=O)[O-]"), ("吡啶", "c1ccncc1"),
        ("环氧丙烷", "CC1CO1"), ("N-甲基苯甲亚胺", "CN=Cc1ccccc1"),
        ("磷酸单甲酯", "COP(=O)(O)O"),
    ],
    "不饱和羰基": [
        ("丙烯酸甲酯", "C=CC(=O)OC"), ("丁醛", "CCCC=O"),
        ("邻苯醌", "O=C1C=CC=CC1=O"),
        ("对苯醌", "O=C1C=CC(=O)C=C1"),
        ("对苯二酚", "Oc1ccc(O)cc1"),
        ("9,10-蒽醌", "O=C1c2ccccc2C(=O)c2ccccc21"),
        ("蒽氢醌", "Oc1c2ccccc2c(O)c2ccccc12"),
    ],
}

ALL = [(g, n, s) for g, items in PROBES.items() for n, s in items]


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=str(STAGE / "rules" / "rules.json"))
    args = ap.parse_args()

    from schema import load_rules
    profiles, rules = load_rules(args.rules)

    print(f"探针矩阵：{len(PROBES)} 个官能团类，{len(ALL)} 个分子")
    print(f"规则：{len(rules)} 条\n")

    rows = []
    for r in rules:
        if r.get("status") == "disabled":
            continue
        sm = r["smarts"]
        try:
            rxn = AllChem.ReactionFromSmarts(sm)
        except Exception:
            rows.append((r, 0, [], "SMARTS 编译失败"))
            continue
        n_react = rxn.GetNumReactantTemplates()

        hits = []
        for g, n, s in ALL:
            m = Chem.MolFromSmiles(s)
            if m is None:
                continue
            if n_react == 1:
                try:
                    res = rxn.RunReactants((m,))
                except Exception:
                    res = []
            else:
                # 双反应物：用池子里的第二反应物逐个配
                res = []
                for item in (r.get("co_substrate_pool") or [])[:3]:
                    smi2 = item.get("smiles") if isinstance(item, dict) else None
                    if not smi2:
                        continue
                    m2 = Chem.MolFromSmiles(smi2)
                    if m2 is None:
                        continue
                    try:
                        res = rxn.RunReactants((m, m2))
                    except Exception:
                        res = []
                    if res:
                        break
            if res:
                hits.append((g, n))
        rows.append((r, len(hits), hits, ""))

    rows.sort(key=lambda x: x[1])
    print("=" * 100)
    print("按命中探针数升序（0 命中的最可疑）")
    print("=" * 100)
    print(f"{'命中':>4}  {'规则':<24}{'类别':<16}命中的探针")
    print("-" * 100)
    for r, n, hits, err in rows:
        if err:
            print(f"{'--':>4}  {r['name']:<24}{r.get('category',''):<16}★{err}")
            continue
        sample = "、".join(f"{n_}" for _g, n_ in hits[:5])
        print(f"{n:>4}  {r['name']:<24}{r.get('category',''):<16}{sample}")

    zero = [x for x in rows if x[1] == 0 and not x[3]]
    print()
    print("=" * 100)
    if zero:
        print(f"★ 在探针矩阵里【一个都不匹配】的规则：{len(zero)} 条 ★")
        print("=" * 100)
        for r, _n, _h, _e in zero:
            print(f"  {r['name']:<24}{r['id']:<44}{r.get('category')}")
            print(f"      {r['smarts'][:88]}")
    else:
        print("✓ 所有启用规则都至少认一个简单官能团")
        print("=" * 100)

    print()
    print(f"汇总：启用规则 {len(rows)} 条，其中 0 命中 {len(zero)} 条")
    return 1 if zero else 0


if __name__ == "__main__":
    raise SystemExit(main())
