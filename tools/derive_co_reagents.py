# -*- coding: utf-8 -*-
"""自动推导陪跑试剂（co_reagents / byproducts）。

动机：手写 36 条新规则时，每条都要判断"缺了什么分子"，人肉推极易出错。
      但校验器其实已经能测出差值——差值就是缺的东西。

原理：
    配平要求   底物 + co_reagents == 产物 + byproducts
    所以       co_reagents - byproducts == 产物原子 - 底物原子 == diff

    如果 diff = {O:1, H:2}  → 补一个 H2O 即可（co_reagents={H2O:1}）
    如果 diff = {H:-2}      → 有两种解释：
        (a) byproducts={H2:1}                       —— 脱氢
        (b) co_reagents={O2:0.5}, byproducts={H2O:1} —— 氧化
        按规则的 category 选：oxidation 走 (b)，其余走 (a)

用法：
    python derive_co_reagents.py                  # 分析 rules.json 里所有 co_reagents 为空的规则
    python derive_co_reagents.py --rules xxx.json
    python derive_co_reagents.py --apply          # 把推导结果写回文件
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STAGE = Path(__file__).resolve().parent.parent
for _p in (STAGE / "rules", STAGE / "libs"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem
from rdkit.Chem import AllChem
from schema import (atom_counts, atom_diff, add_atoms, format_atoms,
                    formula_atoms, load_rules, _load_substrates)


def sum_atoms(mol_list) -> Dict[str, float]:
    total: Dict[str, float] = {}
    for m in mol_list:
        total = add_atoms(total, atom_counts(m))
    return total


def measure_diffs(rule: Dict[str, Any], substrates, max_sub: int = 300,
                  max_sets: int = 5) -> Tuple[List[Dict[str, float]], int, int]:
    """返回 (差值列表, 匹配底物数, 价态非法数)。

    差值 = 产物原子 − 底物原子（此时 co_reagents/byproducts 视为空）

    ★ 必须用 rdchiral，不能用 rdkit 原生 RunReactants：
      两者在"环内断键"时结果不同（rdkit 会复制原子），
      用错引擎会得出错误的差值，进而推出错误的陪跑试剂。
      校验器的默认引擎也是 rdchiral，这里必须一致。
    """
    from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants
    rxn = rdchiralReaction(rule["smarts"])

    diffs: List[Dict[str, float]] = []
    matched = 0
    bad = 0

    for name, smiles, mol in substrates:
        if len(Chem.GetMolFrags(mol)) > 1:
            continue
        try:
            outcomes = rdchiralRun(rxn, rdchiralReactants(smiles)) or []
        except Exception:
            continue
        if not outcomes:
            continue
        matched += 1
        left = atom_counts(mol)
        for out in outcomes[:max_sets]:
            prods = []
            ok = True
            for part in out.split("."):
                pm = Chem.MolFromSmiles(part)
                if pm is None:
                    ok = False
                    break
                try:
                    Chem.SanitizeMol(pm)
                except Exception:
                    ok = False
                    break
                prods.append(pm)
            if not ok:
                bad += 1
                continue
            right = sum_atoms(prods)
            diffs.append(atom_diff(left, right))
        if matched >= max_sub:
            break
    return diffs, matched, bad


def diff_key(d: Dict[str, float]) -> str:
    return "".join(f"{el}{d[el]:+g}" for el in sorted(d)) or "(配平)"


def suggest(diff: Dict[str, float], category: str) -> Optional[Dict[str, Any]]:
    """把原子差值翻译成 co_reagents / byproducts。

    只处理几种最常见的模式；其余交给人工判断，不硬猜。
    """
    if not diff:
        return {"co_reagents": {}, "byproducts": {}, "why": "本来就配平"}

    # ★ 不做归一化。
    # 踩过的坑：我一开始用 GCD 把系数缩小，结果 {H:-2} 被压成 {H:-1}，
    # 模式全部匹配不上，四条规则被误判为"模式不认识"。
    # 原始差值本身就是一次反应所需的化学计量数（多位点反应就该是 H:-4），
    # 归一化反而是错的。
    key = frozenset(diff.items())

    # {O:1, H:2} = 一个水分子
    if diff == {"O": 1, "H": 2}:
        return {"co_reagents": {"H2O": 1}, "byproducts": {},
                "why": "缺 1 个水分子（水解类）"}

    # {O:1} = 半个氧气
    if diff == {"O": 1}:
        return {"co_reagents": {"O2": 0.5}, "byproducts": {},
                "why": "缺 1 个氧原子（氧化）"}

    # {H:-2} = 脱两个氢
    if diff == {"H": -2}:
        if category == "oxidation":
            return {"co_reagents": {"O2": 0.5}, "byproducts": {"H2O": 1},
                    "why": "氧化脱氢：补半个 O2，产一个水"}
        return {"co_reagents": {}, "byproducts": {"H2": 1},
                "why": "脱氢：产一个氢气"}

    # {H:2} = 加两个氢
    if diff == {"H": 2}:
        return {"co_reagents": {"H2": 1}, "byproducts": {},
                "why": "加氢（还原）"}

    # {H:4}
    if diff == {"H": 4}:
        return {"co_reagents": {"H2": 2}, "byproducts": {},
                "why": "双位点加氢（还原）"}

    # {C:1, O:2} = 丢了一个 CO2
    if diff == {"C": -1, "O": -2}:
        return {"co_reagents": {}, "byproducts": {},
                "why": "★产物漏写 CO2★，应在产物侧补 [C](=[O])=[O]"}

    # {O:1, H:2, C:1} 等其它
    return None


def _gcd_float(a: float, b: float, tol: float = 1e-9) -> float:
    while b > tol:
        a, b = b, a % b
    return a


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="自动推导规则缺的陪跑试剂")
    ap.add_argument("--rules", default=str(STAGE / "rules" / "rules.json"))
    ap.add_argument("--db", default=r"D:\TCMAI\tcm.db")
    ap.add_argument("--limit", type=int, default=1500)
    ap.add_argument("--apply", action="store_true", help="把推导结果写回规则文件")
    ap.add_argument("--overwrite", action="store_true",
                    help="★危险★ 允许覆盖已有的配平值。"
                         "默认【不覆盖】——实测教训：第 6 轮那次 --apply 把"
                         "「美拉德简化」原本正确的 co={O2:0.5}/by={H2O:1} "
                         "覆盖成了 by={H2:1}，而配平校验照样通过，"
                         "直到后来加了化学合理性检查才发现。")
    args = ap.parse_args(argv)

    profiles, rules = load_rules(args.rules)
    substrates = _load_substrates(args.db, args.limit)
    print(f"规则 {len(rules)} 条 | 底物 {len(substrates)} 个\n")

    changes = []
    skipped_nonempty = []
    print(f"{'规则':<20}{'匹配':>6}{'主差值':>18}{'占比':>7}  建议")
    print("-" * 100)

    for r in rules:
        # ★ 默认不碰已经有配平值的规则。
        #   推导器给出的只是"最省事的那种配平"，不等于化学上正确；
        #   盲目覆盖会把人工确认过的正确值改坏（实测发生过一次）。
        if (r.get("co_reagents") or r.get("byproducts")) and not args.overwrite:
            skipped_nonempty.append(r["name"])
            continue

        diffs, matched, bad = measure_diffs(r, substrates)
        if not diffs:
            print(f"{r['name']:<20}{matched:>6}{'(无产物)':>18}{'':>7}  —")
            continue

        keys = Counter(diff_key(d) for d in diffs)
        top_key, top_n = keys.most_common(1)[0]
        ratio = top_n / len(diffs)

        # 找一条代表差值
        top_diff = next(d for d in diffs if diff_key(d) == top_key)
        suggestion = suggest(top_diff, r.get("category", ""))

        if suggestion is None:
            verdict = "★人工判断★（模式不认识）"
        elif not suggestion["co_reagents"] and not suggestion["byproducts"]:
            verdict = suggestion["why"]
        else:
            verdict = (f"{suggestion['why']}  →  co={suggestion['co_reagents']} "
                       f"by={suggestion['byproducts']}")
            changes.append((r["id"], suggestion))

        print(f"{r['name']:<20}{matched:>6}{top_key:>18}{ratio:>7.0%}  {verdict}")

    print()
    print("=" * 100)
    print(f"可自动推导的: {len(changes)} 条")
    for rid, s in changes:
        print(f"  {rid:<42} co={s['co_reagents']}  by={s['byproducts']}")

    if skipped_nonempty:
        print(f"\n已跳过 {len(skipped_nonempty)} 条【已有配平值】的规则（默认不覆盖）：")
        print(f"   {', '.join(skipped_nonempty[:12])}"
              f"{' …' if len(skipped_nonempty) > 12 else ''}")
        print("   如需强制覆盖，加 --overwrite（★先想清楚：推导值不一定比现值正确★）")

    if args.apply and changes:
        data = json.loads(Path(args.rules).read_text(encoding="utf-8"))
        by_id = {c[0]: c[1] for c in changes}
        n = 0
        for r in data["rules"]:
            if r["id"] in by_id:
                r["co_reagents"] = by_id[r["id"]]["co_reagents"]
                r["byproducts"] = by_id[r["id"]]["byproducts"]
                n += 1
        Path(args.rules).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n已写回 {n} 条到 {args.rules}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
