# -*- coding: utf-8 -*-
r"""诊断②：反转模板到底产生多少【怪前体】？

现象（用户点的名）：chan_lam 反转后给出 BC(C)=O —— 含硼的"前体"。
这类东西化学上不可能是你要买的原料（它是原位生成的试剂物种）。

本脚本只回答一个口径清楚的问题：
  9,770 条【反转】模板，跑一遍代表性分子后，有多少条会吐出【怪前体】。
怪前体的判定（三个独立信号，分开计，不合并）：
  S1 前体含"试剂元素"：B / Si / Sn / Zn / Mg / Li / Al / Ti
     （这类原子在真实逆合成里几乎总是从试剂来的，不是砌块）
  S2 前体带电荷且分子很小（<=6 重原子）—— 离子试剂碎片
  S3 前体的重原子数 >= 目标分子重原子数
     （逆合成前体不该比目标还大；发生说明模板是"加保护基/加成"方向的怪反转）
另外统计：前体里的原子映射残留、前体是否无法 sanitize

用法: python diag_retro_weird_precursors.py [每模板测的目标数]
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdChemReactions  # noqa: E402
from retro_search import load_retro_templates, canon  # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "retro_weird_precursors.json"

REAGENT_ELEMENTS = {5, 14, 50, 30, 12, 3, 13, 22}   # B Si Sn Zn Mg Li Al Ti

# 一批"典型目标"：药物化学常见骨架 + 天然产物常见骨架 + 几个简单砌块
TARGETS = [
    "CCNC(C)=O",                              # 简单酰胺
    "O=C(NCCc1ccc(O)cc1)c1ccccc1O",           # 水杨酰胺（沙洛酚）
    "c1ccc2c(c1)cc1ccccc12",                  # 萘（稠环）
    "O=C(O)c1ccccc1O",                        # 水杨酸
    "CC(=O)Oc1ccccc1C(=O)O",                  # 阿司匹林
    "OC[C@@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O",   # 葡萄糖
    "Cn1cnc2c1c(=O)n(C)c(=O)n2C",             # 咖啡因
    "COc1cc(CC=C(C)C)cc(OC)c1O",              # 丁香酚类
    "CC(C)=CCc1c(O)cc(O)c2c(=O)cc(-c3cc(O)c(O)c(CC=C(C)C)c3)oc12",  # 异戊烯基黄酮
    "C=CC1(C)CC(O)C2C(O)(C1=O)C(Br)CC1C(C)(C)C(OC(C)=O)C(O)C(OC(=O)c3ccccc3)C12C",  # 复杂萜
]


def has_reagent_element(m):
    return any(a.GetAtomicNum() in REAGENT_ELEMENTS for a in m.GetAtoms())


def main():
    per_t = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    t0 = time.time()
    tmpl = load_retro_templates()
    print("=" * 92)
    print(f"诊断②：反转模板的怪前体规模（模板 {len(tmpl):,} 条，目标 {len(TARGETS)} 个）")
    print("=" * 92)

    targets = [Chem.MolFromSmiles(s) for s in TARGETS]
    targets = [(TARGETS[i], m, m.GetNumHeavyAtoms()) for i, m in enumerate(targets) if m]
    print(f"目标重原子数: {[t[2] for t in targets]}")

    bad_templates = defaultdict(set)      # 模板索引 -> 命中的信号
    per_type_total = Counter()
    per_type_bad = Counter()
    tpl_used = 0
    tpl_any_hit = 0

    for ti, t in enumerate(tmpl):
        hit_any = False
        for name, m, hac in targets:
            try:
                results = t.rxn.RunReactants((m,))
            except Exception:
                continue
            if not results:
                continue
            hit_any = True
            for tup in results[:4]:
                pres = []
                ok = True
                for pm in tup:
                    try:
                        Chem.SanitizeMol(pm)
                    except Exception:
                        ok = False
                        break
                    cs = canon(Chem.MolToSmiles(pm))
                    if not cs:
                        ok = False
                        break
                    pres.append(cs)
                if not ok or not pres:
                    bad_templates[ti].add("S0_前体无法解析")
                    continue
                for ps in pres:
                    pm = Chem.MolFromSmiles(ps)
                    if pm is None:
                        continue
                    if has_reagent_element(pm):
                        bad_templates[ti].add("S1_含试剂元素")
                    if Chem.GetFormalCharge(pm) != 0 and pm.GetNumHeavyAtoms() <= 6:
                        bad_templates[ti].add("S2_小离子碎片")
                    if pm.GetNumHeavyAtoms() >= hac:
                        bad_templates[ti].add("S3_前体不小于目标")
        if hit_any:
            tpl_any_hit += 1
            per_type_total[t.name] += 1
            if ti in bad_templates:
                per_type_bad[t.name] += 1

    print(f"\n有命中的模板 {tpl_any_hit:,} / {len(tmpl):,}")
    print(f"其中会吐出怪前体的 {len(bad_templates):,}"
          f"  ({len(bad_templates)/max(tpl_any_hit,1)*100:.1f}% of 有命中)")

    sig = Counter()
    for ti, ss in bad_templates.items():
        for s in ss:
            sig[s] += 1
    print("\n各信号单独计数（一个模板可同时命中多个）:")
    for k, v in sig.most_common():
        print(f"   {k:<22} {v:>6,} 条模板")

    # 只有 S1（最明确的"试剂元素"信号）
    only_s1 = [ti for ti, ss in bad_templates.items() if "S1_含试剂元素" in ss]
    print(f"\n★ 含试剂元素(B/Si/Sn/Zn/Mg/Li/Al/Ti)的模板 {len(only_s1):,} 条")
    by_type = Counter(tmpl[ti].name for ti in only_s1)
    print("   按反应类型（前 15）:")
    for k, v in by_type.most_common(15):
        print(f"      {v:>5,}  {k}")

    # 举例：把 chan_lam 的实际输出原样打出来
    print("\n" + "=" * 92)
    print("举例：chan_lam 反转后的实际前体（用户点名的那类）")
    print("=" * 92)
    shown = 0
    for ti, t in enumerate(tmpl):
        if t.name != "chan_lam":
            continue
        for name, m, hac in targets[:4]:
            try:
                res = t.rxn.RunReactants((m,))
            except Exception:
                continue
            for tup in res[:3]:
                try:
                    ps = [canon(Chem.MolToSmiles(pm)) for pm in tup]
                except Exception:
                    continue
                print(f"   目标 {name[:46]:<46} -> 前体 {ps}")
                shown += 1
                if shown >= 8:
                    break
            if shown >= 8:
                break
        if shown >= 8:
            break

    OUT.write_text(json.dumps({
        "n_templates": len(tmpl),
        "n_templates_with_hits": tpl_any_hit,
        "n_weird": len(bad_templates),
        "signal_counts": dict(sig),
        "weird_by_reaction_type": dict(by_type.most_common()),
        "weird_template_indices": sorted(bad_templates),
        "per_type_total": dict(per_type_total),
        "per_type_bad": dict(per_type_bad),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT.name}   耗时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
