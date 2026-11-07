# -*- coding: utf-8 -*-
r"""规则来源体检（待办 2 · 方案 a）：**反应中心签名**比对。

* 规则与挖掘模板都抽成 signature =（反应物侧映射原子/键，产物侧映射原子/键）；
* 三档：**同款**（两侧签名全等）/ **同反应中心**（反应物侧全等）/ **无**；
* 输出 `data\rules_provenance_fp.json` + Markdown 表（含 support）。
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.*")
STAGE = Path(__file__).resolve().parent.parent
RULES = STAGE / "rules" / "rules.json"
MINE = STAGE / "reports" / "mined_forward_templates_full_lf.jsonl"
OUTJ = STAGE / "data" / "rules_provenance_fp.json"
OUTM = STAGE / "reports" / "第七十五轮-规则来源体检（结构）.md"


def side_sig(mol) -> tuple:
    if mol is None:
        return ()
    atoms = []
    idx2map = {}
    for a in mol.GetAtoms():
        am = a.GetAtomMapNum()
        if am:
            idx2map[a.GetIdx()] = am
            atoms.append((am, a.GetAtomicNum(), a.GetFormalCharge(),
                          sum(1 for b in a.GetBonds()
                              if b.GetOtherAtom(a).GetAtomicNum() > 1)))
    bonds = []
    for b in mol.GetBonds():
        m1, m2 = idx2map.get(b.GetBeginAtomIdx()), idx2map.get(b.GetEndAtomIdx())
        if m1 and m2:
            bonds.append(tuple(sorted((m1, m2))) + (str(b.GetBondType()),))
    return (tuple(sorted(atoms)), tuple(sorted(bonds)))


def sig(smarts: str):
    try:
        rxn = AllChem.ReactionFromSmarts(str(smarts))
    except Exception:                                        # noqa: BLE001
        return None
    if rxn is None:
        return None
    r = tuple(sorted(side_sig(rxn.GetReactantTemplate(i))
                     for i in range(rxn.GetNumReactantTemplates())))
    p = tuple(sorted(side_sig(rxn.GetProductTemplate(i))
                     for i in range(rxn.GetNumProductTemplates())))
    return (r, p)


def main() -> int:
    R = json.loads(RULES.read_text(encoding="utf-8"))
    rules = R if isinstance(R, list) else R.get("rules") or []
    by_full = defaultdict(list)
    by_r = defaultdict(list)
    n_t = 0
    for ln in MINE.open(encoding="utf-8"):
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except Exception:                                    # noqa: BLE001
            continue
        s = sig(d.get("template"))
        if not s:
            continue
        n_t += 1
        by_full[s].append(d.get("support"))
        by_r[s[0]].append(d.get("support"))
    print("规则 %d ｜ 可解析挖掘模板 %d（按签名去重前者 %d / 后者 %d）"
          % (len(rules), n_t, len(by_full), len(by_r)))
    rows = []
    for r in rules:
        s = sig(r.get("smarts"))
        tag, sup, n = "无", None, 0
        if s and s in by_full:
            tag, sups = "同款", by_full[s]
            sup, n = max(sups), len(sups)
        elif s and s[0] in by_r:
            tag, sups = "同反应中心", by_r[s[0]]
            sup, n = max(sups), len(sups)
        rows.append({"id": r.get("id"), "name": r.get("name"),
                     "category": r.get("category"), "status": r.get("status"),
                     "evidence": tag, "max_support": sup, "n_templates": n})
    OUTJ.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    c = Counter(x["evidence"] for x in rows)
    print("  分档：", dict(c))
    with OUTM.open("w", encoding="utf-8") as fh:
        fh.write("# 第七十五轮 · 规则来源体检（结构签名）\n\n")
        fh.write("> 口径：规则与 ORD 挖掘模板抽**反应中心签名**（映射原子的元素/电荷/度 + "
                 "映射原子间的键）后比对。\n")
        fh.write("> **同款** = 两侧签名全等；**同反应中心** = 反应物侧相同（产物写法不同）；"
                 "**无** = 未找到。\n\n")
        fh.write("| # | 规则 | 类别 | 状态 | 证据 | 最高 support | 同款模板数 |\n"
                 "|---|---|---|---|---|---|---|\n")
        for i, x in enumerate(rows, 1):
            fh.write("| %d | `%s` %s | %s | %s | **%s** | %s | %s |\n"
                     % (i, x["id"], x["name"], x["category"], x["status"],
                        x["evidence"], x["max_support"] if x["max_support"] is not None else "—",
                        x["n_templates"]))
        fh.write("\n## 分档统计\n\n")
        for k, v in c.most_common():
            fh.write("* **%s**：%d 条\n" % (k, v))
    print("  -> %s" % OUTM)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
