# -*- coding: utf-8 -*-
r"""条件门控的分辨力测试：换工艺条件，产物清单和激活的反应类型会不会变？

三件事：
  ① 静态扫描：37 类反应 × 若干典型工艺条件 -> 哪些被判零（不可能发生）
  ② 动态测试：同一批甘草成分，在不同条件下跑引擎 -> 产物数/反应类型数是否变化
  ③ 误杀检查：温和条件（室温水）下有多少反应类型被判零（判多了就是误杀）

用法: python test_condition_gate.py
输出 reports/condition_gate_test.json + .txt
"""
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "tools", Path(r"D:\TCMAI\src")):
    sys.path.insert(0, str(_p))

from model import Conditions  # noqa: E402
from smartreact_engine import SmartReactEngine  # noqa: E402

OUT = STAGE / "reports" / "condition_gate_test.json"

# 典型工艺条件
CONDS = [
    ("室温水浸", Conditions(solvent="water", temperature=25, time_min=60)),
    ("煎煮 100°C", Conditions(solvent="water", temperature=100, time_min=60)),
    ("乙醇回流", Conditions(solvent="ethanol", temperature=78, time_min=120)),
    ("高温久煎", Conditions(solvent="water", temperature=180, time_min=180)),
    ("低温冷浸", Conditions(solvent="water", temperature=4, time_min=1440)),
]


def main():
    t0 = time.time()
    eng = SmartReactEngine(verbose=False, gate_conditions=True)
    print("=" * 96)
    print("① 静态扫描：37 类反应在各条件下的门控判定")
    print("=" * 96)
    print(f"条件表条目数: {len(eng.cond_table)}")
    names = sorted(eng.cond_table)
    print(f"\n{'反应类型':<36}" + "".join(f"{c[0]:>12}" for c in CONDS))
    zero_by_cond = {c[0]: [] for c in CONDS}
    for nm in names:
        row = []
        for label, c in CONDS:
            a, _why = eng.cond_activation(nm, c)
            row.append(a)
            if a <= 0:
                zero_by_cond[label].append(nm)
        print(f"{nm[:35]:<36}" + "".join(
            f"{('判零' if a <= 0 else f'{a:.2f}'):>12}" for a in row))

    print()
    print("=" * 96)
    print("② 各条件下【被判零】的反应类型")
    print("=" * 96)
    for label, _c in CONDS:
        z = zero_by_cond[label]
        print(f"\n  【{label}】判零 {len(z)}/{len(names)} 类:")
        print(f"     {z if z else '（无 —— 该条件下所有反应类型都放行）'}")

    print()
    print("=" * 96)
    print("③ 误杀检查：温和条件（室温水）不该大面积判零")
    print("=" * 96)
    z_rt = len(zero_by_cond["室温水浸"])
    print(f"  室温水浸判零 {z_rt}/{len(names)} = {z_rt/len(names)*100:.1f}%")
    print(f"  煎煮100°C 判零 {len(zero_by_cond['煎煮 100°C'])}"
          f"  乙醇回流判零 {len(zero_by_cond['乙醇回流'])}")
    print(f"  高温久煎判零 {len(zero_by_cond['高温久煎'])}"
          f"  低温冷浸判零 {len(zero_by_cond['低温冷浸'])}")

    print()
    print("=" * 96)
    print("④ 动态：同一批底物换条件，产物是否不同")
    print("=" * 96)
    # 用几个中药里常见的分子做底物（不写死数据：从 tcm.db 取）
    subs = []
    try:
        from tcm_ro import open_db  # ★ 只读（AGENTS.md 四）
        from rdkit import Chem
        with open_db() as conn:
            cur = conn.cursor()
            # ★ 用中等大小分子（150~400 Da）：大分子在 SmartReact 里枚举极慢
            #   （实测 12 个最大成分跑了 4 分钟还没完），而且中药主成分本来就集中在这个区间
            cur.execute("SELECT name_en, smiles FROM compounds "
                        "WHERE smiles IS NOT NULL AND smiles != '' "
                        "AND mol_weight BETWEEN 150 AND 400 "
                        "ORDER BY mol_weight DESC LIMIT 12")
            for nm, smi in cur.fetchall():
                m = Chem.MolFromSmiles(smi)
                if m is not None:
                    subs.append((nm or "?", Chem.MolToSmiles(m)))
    except Exception as ex:
        print(f"   [warn] tcm.db 读取失败: {ex}")
    print(f"  底物 {len(subs)} 个（tcm.db 里 150~400 Da 的 12 个）", flush=True)
    from engine import Compound  # noqa: E402
    dyn = {}
    for label, c in CONDS:
        comps = [Compound(smiles=s, name=n, herb="test") for n, s in subs]
        eng.gate_stats = {}
        prods = eng.step(comps, c, round_no=1)
        types = {}
        for p in prods:
            types[p.rule_name] = types.get(p.rule_name, 0) + 1
        dyn[label] = {"products": len(prods), "types": len(types),
                      "gated_zero": eng.stats.get("gated_zero_total", 0),
                      "gated_by_type": eng.stats.get("gated_zero_by_type", {}),
                      "type_list": sorted(types)}
        print(f"  【{label}】产物 {len(prods):>5}  反应类型 {len(types):>3}  "
              f"门控拦掉枚举结果 {eng.stats.get('gated_zero_total', 0):>6} 条", flush=True)

    print()
    print("  各条件的反应类型集合（看是否真的不同）:")
    for label, _c in CONDS:
        print(f"     {label:<12} {dyn[label]['type_list'][:8]}")

    OUT.write_text(json.dumps({
        "n_cond_types": len(names),
        "zero_by_cond": zero_by_cond,
        "dynamic": dyn,
        "elapsed_sec": round(time.time() - t0, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT.name}  {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
