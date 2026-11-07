# -*- coding: utf-8 -*-
r"""第 3 件：把【互为逆反应】的模板配对找出来。

## 口径（先定死）
* 模板来源（都在 `reports/`）：
    - `mined_forward_templates.jsonl`（双底物，用 `template` 字段）
    - `mined_mono_templates.jsonl`（单底物）
    - `rules/rules.json` 里的 37 类命名反应（用其 SMARTS 集合，若可读）
* 一条模板 `LHS >> RHS`，把它两侧的**分子骨架**（去掉原子映射号）取成**多重集**
  （点号分隔的组分，各自 canonical SMILES）。
* 若模板 P 的 `RHS` 多重集 == 模板 Q 的 `LHS` 多重集，且 P 的 `LHS` == Q 的 `RHS`
  （允许一侧是另一侧的子集 + 小分子补偿，见 `--loose`），则称 P 与 Q **互为逆模板**。
* 输出：`reports/reverse_template_pairs.jsonl`（每行一对）+ `..._summary.json`

## 为什么这样判
模板库里只有 1.4%（双底物）/0.3%（单底物）是"产物还能当同一条模板底物"的自反模板；
其余逆对**长在两条不同模板上**（缩合模板 vs 水解模板）。所以必须两两配对，而不是逐条自检。

用法:
    & $py -u tools\find_reverse_template_pairs.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "tools", STAGE / "rules"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                      # noqa: E402

RDLogger.DisableLog("rdApp.*")

FWD = STAGE / "reports" / "mined_forward_templates.jsonl"
MONO = STAGE / "reports" / "mined_mono_templates.jsonl"
OUT = STAGE / "reports" / "reverse_template_pairs.jsonl"
OUT_SUM = STAGE / "reports" / "reverse_template_pairs_summary.json"

# 常见小分子补偿（缩合放掉的水/醇等）：宽松匹配时允许差这些
SMALL = {"O": "water", "CO": "methanol", "CCO": "ethanol", "[H][H]": "H2",
         "O=C=O": "CO2", "N": "ammonia"}


def _mol_of(smi: str):
    """模板组分是 **SMARTS**（含 `;D1;+0:1` 这类查询原子），不能按 SMILES 解析。

    ★ 本次踩到：第一版用 MolFromSmiles 解析模板 -> 8,926 条"全部编译失败"。
      模板字符串里带 `-` 的连接与查询原子，只有 SMARTS 解析器认。
    """
    m = Chem.MolFromSmiles(smi)
    if m is not None:
        return m
    return Chem.MolFromSmarts(smi)


def side_key(side: str):
    """一侧（点号分隔的映射 SMARTS）-> (多重集键, 原始组分列表, 失败数)。"""
    parts = [p.strip() for p in str(side or "").split(".") if p.strip()]
    out = []
    n_fail = 0
    for p in parts:
        m = _mol_of(p)
        if m is None:
            n_fail += 1
            continue
        try:
            ks = Chem.MolToSmiles(m)                 # 去映射号
        except Exception:                            # noqa: BLE001
            n_fail += 1
            continue
        if not ks:
            n_fail += 1
            continue
        out.append(ks)
    return tuple(sorted(out)), parts, n_fail


def split_arrow(tmpl: str):
    t = str(tmpl or "")
    if ">>" not in t:
        return None
    lhs, rhs = t.split(">>", 1)
    return lhs, rhs


def load_templates(path: Path, source: str, limit: int = 0):
    recs = []
    n_bad = 0
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            sp = split_arrow(r.get("template", ""))
            if sp is None:
                n_bad += 1
                continue
            lk, lparts, lf = side_key(sp[0])
            rk, rparts, rf = side_key(sp[1])
            if lf or rf or not lk or not rk:
                n_bad += 1
                continue
            recs.append({"template": r["template"], "source": source,
                         "support": r.get("support"), "lhs": lk, "rhs": rk,
                         "n_lhs": len(lk), "n_rhs": len(rk)})
    return recs, n_bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--loose", action="store_true",
                    help="宽松模式：允许两侧相差一个已知小分子（水/醇/CO2 等）")
    a = ap.parse_args()

    t0 = time.time()
    all_recs = []
    bad_total = 0
    for path, src in ((FWD, "mined_forward"), (MONO, "mined_mono")):
        if not path.exists():
            print(f"[warn] 缺 {path}")
            continue
        recs, n_bad = load_templates(path, src)
        print(f"{path.name}: 载入 {len(recs):,} 条可配对模板（跳过 {n_bad:,} 条编译失败）")
        for r in recs[:2]:                       # ★ 先打印原始数据，再谈解析对不对
            print(f"   例: {r['template'][:70]}")
            print(f"       LHS骨架 {r['lhs']}")
            print(f"       RHS骨架 {r['rhs']}")
        all_recs += recs
        bad_total += n_bad

    # index: LHS 多重集 -> 模板下标
    by_lhs = defaultdict(list)
    for i, r in enumerate(all_recs):
        by_lhs[r["lhs"]].append(i)

    pairs = []
    seen = set()
    for i, r in enumerate(all_recs):
        # ① 精确逆向：找 LHS == 我的 RHS 的模板
        for j in by_lhs.get(r["rhs"], []):
            if all_recs[j]["rhs"] == r["lhs"]:
                key = (min(i, j), max(i, j))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append({"kind": "exact",
                              "a_template": r["template"], "a_source": r["source"],
                              "a_support": r["support"],
                              "b_template": all_recs[j]["template"],
                              "b_source": all_recs[j]["source"],
                              "b_support": all_recs[j]["support"],
                              "a_lhs": list(r["lhs"]), "a_rhs": list(r["rhs"]),
                              "b_lhs": list(all_recs[j]["lhs"]),
                              "b_rhs": list(all_recs[j]["rhs"])})
        if not a.loose:
            continue
        # ② 宽松：我这一侧去掉一个组分（水/醇等）后，等于另一条模板的 LHS，
        #    且那条模板的 RHS 加上同一个组分正好等于我的 LHS
        for idx in range(len(r["rhs"])):
            rest = list(r["rhs"])
            dropped = rest.pop(idx)
            if dropped not in SMALL:
                continue
            restk = tuple(sorted(rest))
            for j in by_lhs.get(restk, []):
                jkey = tuple(sorted(list(all_recs[j]["rhs"]) + [dropped]))
                if jkey == tuple(sorted(r["lhs"])):
                    key = (min(i, j), max(i, j), dropped)
                    if key in seen:
                        continue
                    seen.add(key)
                    pairs.append({"kind": f"loose-{SMALL[dropped]}",
                                  "a_template": r["template"], "a_source": r["source"],
                                  "a_support": r["support"],
                                  "b_template": all_recs[j]["template"],
                                  "b_source": all_recs[j]["source"],
                                  "b_support": all_recs[j]["support"],
                                  "a_lhs": list(r["lhs"]), "a_rhs": list(r["rhs"]),
                                  "b_lhs": list(all_recs[j]["lhs"]),
                                  "b_rhs": list(all_recs[j]["rhs"]),
                                  "compensation": dropped})

    print(f"互为逆模板的对数：{len(pairs):,}（{time.time()-t0:.1f}s）")
    with open(a.out, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    summary = {
        "what": "互为逆反应的模板对（LHS/RHS 骨架多重集互换）",
        "caveat": ("只证明「两条模板在结构上是彼此的逆」；不代表两条都在本条件下可激活，"
                   "也不代表方向偏好 —— 方向偏好见 core/direction.py"),
        "loose": bool(a.loose),
        "templates_loaded": len(all_recs),
        "templates_skipped": bad_total,
        "n_pairs": len(pairs),
        "by_kind": {k: sum(1 for p in pairs if p["kind"] == k)
                    for k in sorted({p["kind"] for p in pairs})},
        "seconds": round(time.time() - t0, 1),
        "output": str(a.out),
    }
    Path(OUT_SUM).write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    print(f"-> {a.out}  ({len(pairs)} 对)   -> {OUT_SUM}")
    for p in pairs[:6]:
        print(f"\n  [{p['kind']}] A={p['a_source']}(支持{p.get('a_support')}) "
              f"{p['a_lhs']} -> {p['a_rhs']}")
        print(f"        B={p['b_source']}(支持{p.get('b_support')}) "
              f"{p['b_lhs']} -> {p['b_rhs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
