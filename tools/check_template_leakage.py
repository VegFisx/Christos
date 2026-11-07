#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模板库 ↔ 测试集的泄漏检查（B）。

问题：92.01% 的召回里，有多少是「模板库记得这道题」而不是「推出来了」？

做法（只用两个文件，不需要 1 GB 的 ORD 原始数据）：
  1. `libs/smartreact/data/templates.txt` 的 `example` 列存着**每条 mined 模板的出处反应**
     （mapping 已抹掉的 `底物>>产物`）。这等价于「模板库见过这个反应」。
  2. `reports/paper/data/uspto50k_canon.jsonl` 是测试集的 50,016 条反应。
  3. 两边都做 RDKit 规范 SMILES，按 (底物集合, 产物) 比对。

三种命中口径（从严格到宽松）：
  A. exact      —— 底物集合 + 产物都相同：模板的出处反应就是这道题本身；
  B. substrates —— 底物集合相同、产物不同：同一批底物在模板库里做过别的反应（同专利空间）；
  C. template   —— 有任意一条模板的**底物侧**能匹配这道题的底物（说明「有相关模板可用」，
                  这不是泄漏，只是覆盖率上限，用作对照）。

用法：
    python -I tools\\check_template_leakage.py [--limit 50016]
输出：reports/template_leakage_20261104.json
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "libs" / "smartreact" / "data" / "templates.txt"
TESTSET = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
OUT = ROOT / "reports" / "template_leakage_20261104.json"

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")


def canon(smi: str) -> str:
    m = Chem.MolFromSmiles(smi)
    return Chem.MolToSmiles(m) if m is not None else ""


def load_template_examples():
    """templates.txt 的 example 列 → (底物 frozenset, 产物) → [template_id]。"""
    exact, substrates = {}, {}
    n_bad = 0
    with TEMPLATES.open(encoding="utf-8") as f:
        head = f.readline()
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            name, tid, example = parts[0], parts[1], parts[2]
            if ">>" not in example:
                n_bad += 1
                continue
            lhs, rhs = example.split(">>", 1)
            subs = [canon(x) for x in lhs.split(".") if x]
            prods = [canon(x) for x in rhs.split(".") if x]
            if not subs or not prods or any(not x for x in subs + prods):
                n_bad += 1
                continue
            key = (frozenset(subs), prods[0])
            exact.setdefault(key, []).append(tid)
            substrates.setdefault(frozenset(subs), []).append(tid)
    return exact, substrates, n_bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    t0 = time.time()
    exact, substrates, n_bad = load_template_examples()
    print("模板出处反应：%d 条（严格键 %d，底物键 %d，坏行 %d）"
          % (sum(len(v) for v in substrates.values()), len(exact), len(substrates), n_bad))

    n = 0
    hit_a = hit_b = hit_c = 0
    samples = {"exact": [], "substrates": []}
    with TESTSET.open(encoding="utf-8") as f:
        for line in f:
            if a.limit and n >= a.limit:
                break
            d = json.loads(line)
            n += 1
            try:
                rl = d["reactants"]
                rl = ast.literal_eval(rl) if isinstance(rl, str) else rl
            except Exception:
                continue
            subs = frozenset(canon(x) for x in rl if x)
            prod = canon(d.get("product") or "")
            if not subs or not prod:
                continue
            if (subs, prod) in exact:
                hit_a += 1
                if len(samples["exact"]) < 8:
                    samples["exact"].append({"id": d.get("id"), "product": prod,
                                             "templates": exact[(subs, prod)][:3]})
            elif subs in substrates:
                hit_b += 1
                if len(samples["substrates"]) < 8:
                    samples["substrates"].append({"id": d.get("id"), "product": prod,
                                                  "templates": substrates[subs][:3]})
            if subs in substrates:
                hit_c += 1

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "templates_with_example": sum(len(v) for v in substrates.values()),
        "n_test": n,
        "exact_reaction_in_templates": hit_a,
        "exact_share": round(hit_a / max(1, n), 4),
        "same_substrates_other_product": hit_b,
        "same_substrates_share": round(hit_b / max(1, n), 4),
        "any_substrate_overlap": hit_c,
        "any_substrate_share": round(hit_c / max(1, n), 4),
        "seconds": round(time.time() - t0, 1),
        "samples": samples,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("测试集 %d 条" % n)
    print("A 出处反应就是这道题：%d 条（%.2f%%）" % (hit_a, 100.0 * hit_a / max(1, n)))
    print("B 底物相同、产物不同：%d 条（%.2f%%）" % (hit_b, 100.0 * hit_b / max(1, n)))
    print("C 底物侧有任意模板可用：%d 条（%.2f%%）" % (hit_c, 100.0 * hit_c / max(1, n)))
    print("耗时 %.1f s，写出 %s" % (time.time() - t0, OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
