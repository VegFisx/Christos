# -*- coding: utf-8 -*-
r"""论文基准准备（第一块）：USPTO-50k 标准化 + 与模板来源（抽取分片）的重叠测量。

目的：评估"泄漏风险"。我们的 3,228 条逆模板是从 ord uspto-grants parquet 的**前 6 万行**
抽取的（分片日志：offset 0~54000, n=6000×10）；USPTO-50k 同源专利数据。
这里逐条测：50k 的产物/完整反应，有多少直接出现在我们的抽取记录里。

输出：
  reports/paper/data/uspto50k_canon.jsonl  （id, class, product, reactants[]，供后续基准脚本复用）
  屏幕摘要：重叠条数 / 分类分布 / 示例
用法: python tools/paper_50k_prep.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os as _os_root          # ★ 复现演练（B10）：仓库根可被环境变量覆盖，默认不变
STAGE = Path(_os_root.environ.get("CHEMCREACT_ROOT")
             or r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                        # noqa: E402

RDLogger.DisableLog("rdApp.*")

CSV50K = STAGE / "reports" / "paper" / "data" / "uspto_processed.csv"
OUT = STAGE / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"


def canon(frag: str):
    s = re.sub(r":\d+", "", frag or "").strip()
    if not s:
        return None
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m) if m is not None else None


def split_mapped(side: str):
    return [x for x in side.split(".") if x.strip()]


def main() -> int:
    # ---- 0) 原始格式验证（先打印原始数据，再写解析）----
    with open(CSV50K, encoding="utf-8", newline="") as f:
        first = next(csv.DictReader(f))
    rxn = first["rxn_smiles"]
    groups = rxn.split(">")
    print("rxn_smiles 的 '>' 分段数 = %d（前 120 字：%s…）" % (len(groups), rxn[:120]))
    print("第 1 段片段数 =", len(split_mapped(groups[0])))
    print("末段片段数   =", len(split_mapped(groups[-1])))

    # ---- 1) 标准化 50k ----
    rows = []
    n_fail = 0
    with open(CSV50K, encoding="utf-8", newline="") as f:
        for i, r in enumerate(csv.DictReader(f)):
            g = r["rxn_smiles"].split(">")
            rs = [c for c in (canon(x) for x in split_mapped(g[0])) if c]
            ps = [c for c in (canon(x) for x in split_mapped(g[-1])) if c]
            prod = canon(r["prod_smiles"])
            if prod is None or not rs:
                n_fail += 1
                continue
            rows.append({"i": i, "id": r["id"], "class": r["class"],
                         "product": prod, "reactants": rs, "products_full": ps})
    print("50k 标准化完成：%d 条（失败 %d）" % (len(rows), n_fail))
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- 2) 读分片（模板来源），取产物集合与完整反应签名 ----
    shard_products = set()
    shard_sigs = set()
    n_shard = 0
    for sp in sorted((STAGE / "reports").glob("_shard_[0-9].jsonl")):
        with open(sp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rx = json.loads(line).get("rx") or ""
                if ">>" not in rx:
                    continue
                n_shard += 1
                ls, rs_ = rx.split(">>", 1)
                rc = frozenset(c for c in (canon(x) for x in split_mapped(ls)) if c)
                pc = frozenset(c for c in (canon(x) for x in split_mapped(rs_)) if c)
                shard_products |= pc
                shard_sigs.add((rc, pc))
    print("分片记录 %d 条 · 产物字面 %d 个 · 反应签名 %d 个" % (n_shard, len(shard_products), len(shard_sigs)))

    # ---- 3) 重叠 ----
    hit_prod = 0
    hit_rxn = 0
    hit_cls = Counter()
    examples = []
    for r in rows:
        p_hit = r["product"] in shard_products
        r_hit = (frozenset(r["reactants"]), frozenset(r["products_full"])) in shard_sigs \
            or (frozenset(r["reactants"]), frozenset([r["product"]])) in shard_sigs
        if p_hit:
            hit_prod += 1
            hit_cls[r["class"]] += 1
            if len(examples) < 5:
                examples.append(r["product"][:80])
        if r_hit:
            hit_rxn += 1
    print("=" * 74)
    print("产物级重叠：%d / %d = %.2f%%（50k 产物出现在我们抽取记录里）"
          % (hit_prod, len(rows), 100.0 * hit_prod / max(1, len(rows))))
    print("反应级重叠：%d / %d = %.2f%%（完整反应签名一致）"
          % (hit_rxn, len(rows), 100.0 * hit_rxn / max(1, len(rows))))
    if hit_cls:
        print("产物级重叠按类别：", dict(sorted(hit_cls.items())))
    for x in examples:
        print("   e.g.", x)
    print("标准化 50k -> %s" % OUT.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
