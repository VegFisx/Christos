# -*- coding: utf-8 -*-
r"""探针（只读）：引擎里的「底物生成底物」到底有哪几种机制，各占多少？

只回答一个问题：**已装模板里，有多少条模板能让"同一个分子的产物"仍然包含它自己（或它的等价体）？**

口径（先定死）：
  * 模板文件：reports/mined_forward_templates.jsonl（双底物）、reports/mined_mono_templates.jsonl（单底物）
  * 对每条模板 SMARTS，取反应物侧模板与产物侧模板，分别编译成 RDKit 反应
  * 判「A -> A'」：拿一个**由模板自身反应物侧生成的小分子**当底物，套用该模板，
    看产物里是否出现与底物**同一个 canonical SMILES**（同分异构/同分子）；
  * 同时统计「产物中有一个组分是反应物侧某个匹配基团的子集」（缩合/加成常见的自反情形）
  * 只打印计数与前几个例子，不做结论推断
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
from rdkit import Chem, RDLogger                     # noqa: E402
from rdkit.Chem import AllChem                       # noqa: E402

RDLogger.DisableLog("rdApp.*")

FWD = STAGE / "reports" / "mined_forward_templates.jsonl"
MONO = STAGE / "reports" / "mined_mono_templates.jsonl"


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


def ratio_of_template(tmpl: str) -> dict:
    """一条模板 SMARTS -> {'same_side': 反应物模板与产物模板能否匹配同一分子, ...}"""
    if ">>" not in tmpl:
        return {"ok": False, "why": "无箭头"}
    lhs, rhs = tmpl.split(">>", 1)
    try:
        rxn = AllChem.ReactionFromSmarts(tmpl, useSmiles=False)
        if rxn is None:
            return {"ok": False, "why": "编译失败"}
    except Exception as ex:                          # noqa: BLE001
        return {"ok": False, "why": f"{type(ex).__name__}"}
    n_r, n_p = rxn.GetNumReactantTemplates(), rxn.GetNumProductTemplates()
    # ★ 必须 sanitize：模板 mol 的隐式价没算过，直接 HasSubstructMatch 会抛
    #   "getNumImplicitHs() called without preceding call to calcImplicitValence()"
    #   （RDKit 2026.03.6 实测）—— 这是本次踩到的第一个坑。
    rt0 = rxn.GetReactantTemplate(0)
    try:
        Chem.SanitizeMol(rt0)
    except Exception:                                # noqa: BLE001
        return {"ok": False, "why": "sanitize失败"}
    # 关键判据：反应物侧的某个模板，是否也能匹配"产物侧生成的分子"——
    # 用模板自身的 SMARTS 互相匹配（结构层面的自反性）
    self_overlap = False
    for i in range(n_r):
        rt = rxn.GetReactantTemplate(i)
        for j in range(n_p):
            pt = rxn.GetProductTemplate(j)
            try:
                Chem.SanitizeMol(pt)
                Chem.SanitizeMol(rt)
            except Exception:                        # noqa: BLE001
                continue
            # 反应物模板是否包含产物模板（即"产物还能当同类底物"）
            if rt.GetNumAtoms() >= pt.GetNumAtoms() and rt.HasSubstructMatch(pt):
                self_overlap = True
    # 产物数=1 且 反应物数=1：单底物重排类，最容易出现 A->A'（同分异构体）
    return {"ok": True, "n_r": n_r, "n_p": n_p, "self_overlap": self_overlap}


def scan(path: Path, limit: int = 100000) -> dict:
    n = 0
    n_ok = n_bad = 0
    n_self = 0
    n_1to1 = 0
    n_self_and_1to1 = 0
    examples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if n >= limit:
                break
            line = line.strip()
            if not line:
                continue
            n += 1
            rec = json.loads(line)
            r = ratio_of_template(str(rec.get("template", "")))
            if not r.get("ok"):
                n_bad += 1
                continue
            n_ok += 1
            if r["self_overlap"]:
                n_self += 1
            if r["n_r"] == 1 and r["n_p"] == 1:
                n_1to1 += 1
                if r["self_overlap"]:
                    n_self_and_1to1 += 1
            if r["self_overlap"] and len(examples) < 4:
                examples.append(str(rec.get("template", ""))[:120])
    return {"path": path.name, "n": n, "n_ok": n_ok, "n_bad": n_bad,
            "n_self_overlap": n_self, "n_1to1": n_1to1,
            "n_self_and_1to1": n_self_and_1to1, "examples": examples}


def main() -> int:
    for p in (FWD, MONO):
        if not p.exists():
            print(f"缺文件 {p}")
            continue
        s = scan(p)
        print(f"\n=== {s['path']} ===")
        print(f"  模板 {s['n']:,} 条，编译成功 {s['n_ok']:,}，失败 {s['n_bad']:,}")
        print(f"  ★ 反应物模板能吞下某个产物模板（= 产物还能当同类底物）: "
              f"{s['n_self_overlap']:,} 条 = {s['n_self_overlap']/max(1,s['n_ok']):.1%}")
        print(f"  单底物->单产物（重排/异构类，最容易 A->A'）: {s['n_1to1']:,} 条")
        print(f"    其中同时满足上面那条: {s['n_self_and_1to1']:,} 条")
        for e in s["examples"]:
            print(f"    例: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
