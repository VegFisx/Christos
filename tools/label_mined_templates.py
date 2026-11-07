# -*- coding: utf-8 -*-
r"""C：给 mined 模板补反应类（高置信反应中心签名匹配）。

已知类模板：`libs/smartreact/data/templates.txt`（9,770 条，带 reaction_name）
待标注：`reports/mined_forward_templates_full_lf.jsonl`（282,704 条）

签名 = 反应物侧/产物侧的映射原子（元素/电荷/重原子度）+ 映射键。
只有签名唯一对应一个 reaction_name 才标 `exact`；多类同签名标 `ambiguous`；
没有同签名标 `none`。不猜。

用法：
  python tools\label_mined_templates.py --limit 10000
  python tools\label_mined_templates.py
"""
from __future__ import annotations

import argparse
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

from rdkit import RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.*")

STAGE = Path(__file__).resolve().parent.parent
KNOWN = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
MINED = STAGE / "reports" / "mined_forward_templates_full_lf.jsonl"
OUTJ = STAGE / "data" / "mined_template_classes.jsonl"
OUTM = STAGE / "reports" / "第七十五轮-mined模板反应类标注.md"


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
    except Exception:
        return None
    if rxn is None:
        return None
    r = tuple(sorted(side_sig(rxn.GetReactantTemplate(i))
                     for i in range(rxn.GetNumReactantTemplates())))
    p = tuple(sorted(side_sig(rxn.GetProductTemplate(i))
                     for i in range(rxn.GetNumProductTemplates())))
    return (r, p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="只跑前 N 条 mined 模板（0=全量）")
    args = ap.parse_args()

    known = defaultdict(Counter)
    n_known = n_known_bad = 0
    with KNOWN.open(encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                n_known_bad += 1
                continue
            name, tpl = parts[0], parts[3]
            s = sig(tpl)
            if not s:
                n_known_bad += 1
                continue
            known[s][name] += 1
            n_known += 1
    print("known templates: %d（解析失败 %d，唯一签名 %d）"
          % (n_known, n_known_bad, len(known)))

    n = labeled = ambiguous = none = bad = 0
    support_total = support_labeled = support_ambiguous = support_none = 0
    class_support = Counter()
    t0 = time.time()
    with MINED.open(encoding="utf-8") as fi, OUTJ.open("w", encoding="utf-8") as fo:
        for line in fi:
            if args.limit and n >= args.limit:
                break
            n += 1
            try:
                d = json.loads(line)
            except Exception:
                bad += 1
                continue
            tpl = str(d.get("template") or "")
            sup = int(d.get("support") or 0)
            support_total += sup
            s = sig(tpl)
            if not s or s not in known:
                none += 1
                support_none += sup
                continue
            names = known[s]
            if len(names) == 1:
                name = next(iter(names))
                labeled += 1
                support_labeled += sup
                class_support[name] += sup
                fo.write(json.dumps({"template": tpl, "support": sup,
                                     "reaction_name": name,
                                     "status": "exact"}, ensure_ascii=False) + "\n")
            else:
                ambiguous += 1
                support_ambiguous += sup
                fo.write(json.dumps({"template": tpl, "support": sup,
                                     "reaction_name": None,
                                     "status": "ambiguous",
                                     "candidates": sorted(names)[:8]},
                                    ensure_ascii=False) + "\n")
            if n % 50000 == 0:
                print("  ... %d（%.0fs）" % (n, time.time() - t0))

    with OUTM.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · mined 模板反应类标注（C）\n\n")
        f.write("> 已知类模板：`libs/smartreact/data/templates.txt`；"
                "mined：`reports/mined_forward_templates_full_lf.jsonl`。\n")
        f.write("> 高置信 = 反应中心签名唯一对应一个 reaction_name；"
                "多类同签名不猜，标 `ambiguous`；无同签名标 `none`。\n\n")
        f.write("## 总览\n\n")
        f.write("* mined 模板：**%d** 条（解析失败 %d）\n" % (n, bad))
        f.write("* `exact`：**%d** 条（support 权重 %.1f%%）\n"
                % (labeled, 100.0 * support_labeled / max(1, support_total)))
        f.write("* `ambiguous`：%d 条（support %.1f%%）\n"
                % (ambiguous, 100.0 * support_ambiguous / max(1, support_total)))
        f.write("* `none`：%d 条（support %.1f%%）\n\n"
                % (none, 100.0 * support_none / max(1, support_total)))
        f.write("## 已标注类的 support 分布（前 30）\n\n")
        f.write("| reaction_name | support 合计 |\n|---|---:|\n")
        for k, v in class_support.most_common(30):
            f.write("| `%s` | %d |\n" % (k, v))
        f.write("\n## 机器可读\n\n`data/mined_template_classes.jsonl`\n")

    print("-> %s" % OUTJ)
    print("-> %s" % OUTM)
    print("  mined %d ｜ exact %d (support %.1f%%) ｜ ambiguous %d ｜ none %d"
          % (n, labeled,
             100.0 * support_labeled / max(1, support_total),
             ambiguous, none))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
