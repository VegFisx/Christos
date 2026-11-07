# -*- coding: utf-8 -*-
r"""D5（2026-10-13）：从 ORD 抽【3 组分】正向模板。

为什么单独写一个：现有的 `forward_template_mining.py` 口径写死「恰好 2 个组分的原子进入产物」，
整条下游（基准覆盖率/去重键/md5 划分）都假设 r1+r2，改一个常数改不动 —— 所以这里只做
「3 组分 -> 正向模板」这一件事，复用它的 `generalize_smarts()` 和 rdchiral，不重写解析。

口径（写死）：
  1. 抽样：BIG parquet `USING SAMPLE N ROWS (reservoir, seed)`，seed 固定 -> 可复现。
  2. 可用反应：CXSMILES 拆三段；产物有映射；**恰好 3 个组分的原子进入产物**。
  3. 抽模板：rdchiral `extract_from_reaction({"reactants": 三个 raw 点号连, "products": rhs})`，
     结果交换成正向；再用 `generalize_smarts()` 泛化。
  4. **只保留反应物模板数 == 3 的**（用 RDKit 复验；否则说明泛化把某侧并掉了）。
  5. 按 support 计数落 `reports/mined_forward_templates_3c.jsonl`（字段与既有 jsonl 一致：smarts/support）。

用法: python tools/mine_3c_templates.py [SAMPLE] [SEED] [SECONDS_BUDGET]
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core", STAGE / "rules",
           STAGE / "conditions", STAGE / "sources"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb                                                    # noqa: E402
from rdkit import Chem, RDLogger                                 # noqa: E402
from rdkit.Chem import rdChemReactions                           # noqa: E402
from ord_schema.proto import reaction_pb2                        # noqa: E402
from rdchiral.template_extractor import extract_from_reaction    # noqa: E402

import mapped_chem as mc                                         # noqa: E402
from forward_template_mining import generalize_smarts            # noqa: E402

RDLogger.DisableLog("rdApp.*")

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
OUT = STAGE / "reports" / "mined_forward_templates_3c.jsonl"
SUMMARY = STAGE / "reports" / "mined_forward_templates_3c_summary.json"


def main() -> int:
    n_sample = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20261013
    budget_s = float(sys.argv[3]) if len(sys.argv) > 3 else 300.0
    min_support = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    t0 = time.time()
    print("[参数] 抽样=%d seed=%d 抽取预算=%.0fs min_support=%d" % (n_sample, seed, budget_s, min_support),
          flush=True)

    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    rows = con.execute(
        "SELECT reaction FROM read_parquet('%s') USING SAMPLE %d ROWS (reservoir, %d)"
        % (BIG.as_posix(), n_sample, seed)).fetchall()
    print("抽样 %d 条" % len(rows), flush=True)

    skip = Counter()
    recs = []
    seen = set()
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            skip["protobuf失败"] += 1
            continue
        cx = next((i.value for i in rxn.identifiers
                   if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value), None)
        if not cx:
            skip["无CXSMILES"] += 1
            continue
        parts = mc.split_rxn(cx)
        if not parts or len(parts) != 3:
            skip["拆段失败"] += 1
            continue
        lhs, agents, rhs = parts
        if not lhs or not rhs:
            skip["拆段失败"] += 1
            continue
        pm = mc.parse_plain(rhs)
        if pm is None:
            skip["产物SMILES非法"] += 1
            continue
        pmaps = mc.map_nums(pm)
        if not pmaps:
            skip["产物无映射"] += 1
            continue
        raws, plains = mc.contributing_components(lhs, pmaps)
        skip["贡献组分=%d" % len(plains)] += 1
        if len(plains) != 3:
            continue
        key = tuple(sorted(plains)) + (mc.canon_plain(rhs),)
        if key in seen:
            skip["重复"] += 1
            continue
        seen.add(key)
        recs.append({"raws": ".".join(raws), "rhs": rhs, "agents": agents or ""})

    print("可用（恰好 3 组分、去重后）%d 条" % len(recs), flush=True)
    print("  跳过原因: %s" % dict(skip.most_common(10)), flush=True)

    tmpl_support = Counter()
    n_extract_fail = 0
    n_arity_bad = 0
    n_tried = 0
    for r in recs:
        if time.time() - t0 > budget_s:
            print("  [预算到] 抽取在 %d 条处停止" % n_tried, flush=True)
            break
        n_tried += 1
        try:
            out = extract_from_reaction({"reactants": r["raws"],
                                         "reagents": r["agents"],
                                         "products": r["rhs"], "_id": "x"})
        except Exception:
            n_extract_fail += 1
            continue
        rs = (out or {}).get("reaction_smarts")
        if not rs or ">>" not in rs:
            n_extract_fail += 1
            continue
        a, b = rs.split(">>", 1)
        fwd = generalize_smarts(b + ">>" + a)
        try:
            rx = rdChemReactions.ReactionFromSmarts(fwd)
        except Exception:
            n_extract_fail += 1
            continue
        if rx is None or rx.GetNumReactantTemplates() != 3:
            n_arity_bad += 1
            continue
        tmpl_support[fwd] += 1

    kept = {s: c for s, c in tmpl_support.items() if c >= min_support}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for s, c in sorted(kept.items(), key=lambda kv: (-kv[1], kv[0])):
            # ★ 键名与既有模板库一致（rdkit_template_lib.load_mined_templates 读 `template`）
            f.write(json.dumps({"template": s, "smarts": s, "support": int(c)},
                               ensure_ascii=False) + chr(10))
    summ = {"n_sample": n_sample, "seed": seed, "budget_s": budget_s,
            "min_support": min_support, "n_records_3c": len(recs),
            "n_tried": n_tried, "n_extract_fail": n_extract_fail,
            "n_arity_not_3": n_arity_bad, "n_unique_templates": len(tmpl_support),
            "n_kept": len(kept), "skip": dict(skip.most_common(12)),
            "seconds": round(time.time() - t0, 1), "out": str(OUT)}
    SUMMARY.write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
