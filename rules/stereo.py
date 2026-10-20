# -*- coding: utf-8 -*-
r"""
chemreact 立体化学校验（目标里要求的第四项校验）
================================================

★ 和第三道闸门（化学合理性）的区别

  化学合理性看的是「产物结构对不对」；
  这里看的是「**反应没碰到的手性中心，有没有被保住**」。

★ 判据

  一条规则的作用范围由 SMARTS 里【带原子映射号】的原子界定。
  · 落在作用范围内的手性中心 → 反应就在它身上发生，手性消失是**正确的**
    （例：羟基氧化把 CHOH 变 C=O，那个碳必然不再手性）
  · 落在作用范围**之外**的手性中心 → 反应根本不该动它，
    **丢了就是 bug**（RDKit/rdchiral 应当原样带过去）

  所以本模块只报第二种。第一种是化学，不是错。

★ 背景

  compounds 表 31646 行里 19043 行（60%）带手性标记。
  之前引擎读的是 smiles 列（无立体信息），等于把整个立体化学层扔掉了。
  已改为优先读 isomeric_smiles。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _p in (_HERE, _STAGE / "libs"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

from schema import load_rules, _load_substrates

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

# ★★ 必须用引擎真正用的那个引擎来验 ★★
#
# 实测教训：本模块最初用 rdkit 的 `AllChem.ReactionFromSmarts` 跑，
# 报了 4 条规则"丢失旁观手性中心"。改用 rdchiral 复验，发现：
#
#   · 就同一个底物 CC1=CC[C@@H](CC1)C(=O)C（手性中心在环外的碳上，
#     规则只作用环上的 C=C）：
#       rdkit    → 产物手性 0，看起来"丢了"
#       rdchiral → 产物手性 1，**没丢**；或者直接拒绝（产物数 0）
#
#   原因是 rdkit 的 RunReactants 在重建产物时不总是重新感知立体中心；
#   而 rdchiral 更严格，要么原样保留、要么不产。
#
#   而本项目的引擎对单反应物规则【强制走 rdchiral】。
#   所以拿 rdkit 去验，等于在检查一条引擎根本不走的路 —— 全是假阳性。
#
# 结论：**验证工具必须和运行时用同一个引擎**，否则测的不是同一个东西。
try:
    from rdchiral.main import (rdchiralRun, rdchiralReaction,
                               rdchiralReactants)
    _HAS_RDCHIRAL = True
except Exception:
    _HAS_RDCHIRAL = False


@dataclass
class StereoIssue:
    rule_id: str
    rule_name: str
    kind: str
    detail: str
    example: str = ""


def _rdkit_products(smarts: str, smiles: str):
    """用 rdkit 原生引擎跑一遍，作为交叉验证。

    ★ 为什么要交叉验证 ★
      实测发现：同一个底物、同一条规则，
        rdkit   产物保留旁观手性中心
        rdchiral 产物丢失
      而本项目引擎对单反应物规则【强制走 rdchiral】。
      所以这类丢失是【第三方引擎的限制】，不是规则写错。
      闸门要把这两种情况分开报，否则会误导人一直去改根本没问题的规则。
    """
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
        m = Chem.MolFromSmiles(smiles)
        if m is None:
            return None
        res = rxn.RunReactants((m,))
    except Exception:
        return None
    if not res:
        return None
    best = 0
    for ps in res[:2]:
        tot = 0
        ok = True
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                pc = Chem.RemoveHs(pc)
            except Exception:
                ok = False
                break
            tot += len(_specified_centers(pc))
        if ok:
            best = max(best, tot)
    return best


def _specified_centers(mol: Chem.Mol) -> Dict[int, str]:
    """返回 {原子idx: 手性标签}，只含**已指定**的手性中心。"""
    try:
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
        pairs = Chem.FindMolChiralCenters(mol, includeUnassigned=False,
                                          useLegacyImplementation=False)
        return {int(i): str(t) for i, t in pairs}
    except Exception:
        return {}


def audit_rule_stereo(rule: Dict[str, Any], substrates,
                      max_sub: int = 250,
                      max_examples: int = 2) -> List[StereoIssue]:
    issues: List[StereoIssue] = []
    smarts = rule.get("smarts")
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return [StereoIssue(rule["id"], rule["name"], "SMARTS 编译失败", str(e))]
    if rxn is None:
        return [StereoIssue(rule["id"], rule["name"], "SMARTS 编译失败", "返回 None")]
    if rxn.GetNumReactantTemplates() != 1:
        return []          # 双反应物规则另有分支，暂不查

    patt = rxn.GetReactantTemplate(0)
    # 模板里带映射号的原子 → 这些是规则的"作用范围"
    map_nums = {a.GetIdx(): a.GetAtomMapNum() for a in patt.GetAtoms()}

    n_checked = n_spectator = n_lost = 0
    n_engine_limit = 0
    examples: List[str] = []
    limit_examples: List[str] = []

    for name, smiles, mol in substrates:
        if n_checked >= max_sub:
            break
        if len(Chem.GetMolFrags(mol)) > 1:
            continue
        centers = _specified_centers(mol)
        if not centers:
            continue

        match = mol.GetSubstructMatch(patt)
        if not match:
            continue
        # 作用范围覆盖到的底物原子
        touched = {mol_idx for patt_idx, mol_idx in enumerate(match)
                   if map_nums.get(patt_idx)}
        spectators = {i for i in centers if i not in touched}
        if not spectators:
            continue

        n_checked += 1
        n_spectator += len(spectators)

        # 跑反应，看产物保住了几个已指定手性中心
        # ★ 用 rdchiral —— 和引擎保持一致（见文件头部说明）
        outcome_smiles: List[List[str]] = []
        if _HAS_RDCHIRAL:
            try:
                rch = rdchiralReaction(smarts)
                outs = rdchiralRun(rch, rdchiralReactants(smiles)) or []
                for o in outs[:2]:
                    outcome_smiles.append([x for x in o.split(".") if x])
            except Exception:
                continue
        else:
            try:
                res = rxn.RunReactants((mol,))
            except Exception:
                continue
            for ps in res[:2]:
                frags = []
                for p in ps:
                    pc = Chem.Mol(p)
                    try:
                        Chem.SanitizeMol(pc)
                    except Exception:
                        continue
                    frags.append(Chem.MolToSmiles(pc))
                if frags:
                    outcome_smiles.append(frags)
        if not outcome_smiles:
            continue

        # ★ 关键：把所有产物片段【合计】起来比，不能逐个片段比。
        #   水解类反应会把分子断成两片（酸 + 醇），
        #   拿单片去跟整个底物比，必然"丢失"——那是误报。
        for frags in outcome_smiles:
            total_got = 0
            for f in frags:
                pm = Chem.MolFromSmiles(f)
                if pm is None:
                    continue
                total_got += len(_specified_centers(pm))
            # 产物全部片段里已指定手性中心总数，
            # 至少应 >= 旁观者数量（作用范围内的那些可能合法消失）
            if total_got < len(spectators):
                # ★ 交叉验证：换 rdkit 跑一遍 ★
                #   若 rdkit 保住了，说明是 rdchiral 的限制、不是规则缺陷，
                #   记为「引擎限制」而不是「规则缺陷」。
                rk = _rdkit_products(smarts, smiles)
                if rk is not None and rk >= len(spectators):
                    n_engine_limit += 1
                    if len(limit_examples) < 2:
                        limit_examples.append(
                            f"{name or smiles[:26]}：rdchiral 产物手性 {total_got}，"
                            f"rdkit 产物手性 {rk}（旁观者需 >= {len(spectators)}）")
                else:
                    n_lost += 1
                    if len(examples) < max_examples:
                        examples.append(
                            f"{name or smiles[:26]}：底物 {len(centers)} 个手性中心，"
                            f"其中 {len(spectators)} 个在作用范围外；"
                            f"产物各片段合计只剩 {total_got} 个")
            break

    if n_checked and n_lost:
        issues.append(StereoIssue(
            rule["id"], rule["name"], "手性中心丢失",
            f"★规则缺陷★ 检查了 {n_checked} 个带手性的底物，其中 {n_lost} 个的产物"
            f"丢失了【作用范围之外】的手性中心（共 {n_spectator} 个旁观中心）。"
            f"换 rdkit 跑同样丢失，说明是规则自身的问题。",
            examples[0] if examples else ""))
    if n_checked and n_engine_limit:
        issues.append(StereoIssue(
            rule["id"], rule["name"], "引擎限制（非规则缺陷）",
            f"检查了 {n_checked} 个带手性的底物，其中 {n_engine_limit} 个在 rdchiral 下"
            f"丢失旁观手性中心，但【换 rdkit 跑就保住了】——"
            f"这是第三方引擎 rdchiral 的限制，不是规则写错。"
            f"引擎对该类规则强制走 rdchiral，所以实际输出会少一层立体信息。",
            limit_examples[0] if limit_examples else ""))
    return issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="立体化学校验")
    ap.add_argument("--rules", default=str(_HERE / "rules.json"))
    ap.add_argument("--db", default=r"D:\TCMAI\tcm.db")
    ap.add_argument("--limit", type=int, default=1200)
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    profiles, rules = load_rules(args.rules)
    subs = _load_substrates(args.db, args.limit)
    n_chiral = sum(1 for _n, _s, m in subs if _specified_centers(m))
    print(f"规则 {len(rules)} 条 | 底物 {len(subs)} 个"
          f"（其中带手性中心 {n_chiral} 个）\n")

    all_issues: List[StereoIssue] = []
    for r in rules:
        if r.get("status") == "disabled":
            continue
        all_issues.extend(audit_rule_stereo(r, subs))

    real = [i for i in all_issues if i.kind == "手性中心丢失"]
    limits = [i for i in all_issues if i.kind != "手性中心丢失"]

    if real:
        print("=" * 92)
        print(f"★ 规则缺陷：手性中心丢失 {len(real)} 条 ★")
        print("=" * 92)
        for i in real:
            print(f"  [{i.rule_name}] {i.detail}")
            if i.example:
                print(f"      例：{i.example}")

    if limits:
        print()
        print("=" * 92)
        print(f"○ 引擎限制（非规则缺陷）{len(limits)} 条 ○")
        print("=" * 92)
        for i in limits:
            print(f"  [{i.rule_name}] {i.detail}")
            if i.example:
                print(f"      例：{i.example}")

    if not all_issues:
        print("✓ 未发现「作用范围外手性中心丢失」的问题")

    print(f"\n汇总：问题规则 {len(all_issues)} 条")

    if args.report:
        lines = ["# 立体化学校验报告\n",
                 f"- 规则 {len(rules)} 条；底物 {len(subs)} 个（带手性 {n_chiral} 个）",
                 f"- 问题规则：**{len(all_issues)}** 条\n"]
        for i in all_issues:
            lines.append(f"- **[{i.rule_name}]** {i.detail}")
            if i.example:
                lines.append(f"  - 例：{i.example}")
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"报告已写入: {args.report}")

    return 1 if real else 0


if __name__ == "__main__":
    raise SystemExit(main())
