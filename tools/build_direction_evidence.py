# -*- coding: utf-8 -*-
r"""建【文献侧方向证据】：ORD 里每个反应类型在什么溶剂/温度下出现过。

★ 它回答的问题只有一个：
   「这个反应方向在真实文献里、在这种溶剂下，有没有记录？」
★ 它**不回答**「热力学可行吗」—— 那是 `core/direction.py` 规则表 + （可选的）xTB 的事。

口径（先定死）：
  * 数据：`reports/ord_condition_dataset/shard_*.parquet`（全量 925,943 行的分片）
  * 抽样：前 `--shards` 片（分片是固定 row group 切出来的 → 可复现，不用随机）
  * 反应类型：用引擎同款 `ReactionEnumerator` 把每条记录的 `reaction` 归类成 37 类之一
  * 溶剂：分到 `water_like` / `nonwater` / `unknown` 三桶（与 runtime 判方向同一套桶）
  * 输出：`reports/direction_evidence.json`

用法:
    & $py -u tools\build_direction_evidence.py --shards 24
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

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "conditions", STAGE / "rules",
           STAGE / "tools", STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb                                          # noqa: E402

SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
OUT = STAGE / "reports" / "direction_evidence.json"

WATER_LIKE = ("water", "aqueous", "buffer", "h2o")
NONWATER = ("ethanol", "methanol", "dmso", "dmf", "thf", "dcm", "dichloromethane",
            "toluene", "acetonitrile", "meoh", "etoh", "ipa", "isopropanol",
            "chloroform", "ether", "dioxane", "acetone")


def solvent_bucket(name: str) -> str:
    s = str(name or "").strip().lower()
    if not s:
        return "unknown"
    for w in WATER_LIKE:
        if w in s:
            return "water_like"
    for w in NONWATER:
        if w in s:
            return "nonwater"
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", type=int, default=24,
                    help="用前 N 个分片（每片约 5,000 条）")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    t0 = time.time()
    con = duckdb.connect()
    con.execute("SET enable_progress_bar=false")
    print("排序列名 ...")
    cols = [c[0] for c in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{SHARDS}')").fetchall()]
    print(f"  分片列：{cols}")
    # ★ 分片里**没有** reaction 列（那是原 parquet 的列）；分片给的是 reactants / product
    #   两侧的 CXSMILES，拼成 `reactants>>product` 后与 enumerate_pairs 的输入完全一致。
    if not ("reactants" in cols and "product" in cols):
        print("  ✗ 分片里既没有 reaction，也没有 reactants+product，无法归类")
        return 2

    shards = sorted((STAGE / "reports" / "ord_condition_dataset").glob("shard_*.parquet"))
    use = shards[:args.shards]
    print(f"读 {len(use)} 个分片 ...")
    files = ", ".join(f"'{p.as_posix()}'" for p in use)
    rows = con.execute(
        f"SELECT reactants, product, solvent_names, temperature_C "
        f"FROM read_parquet([{files}])"
    ).fetchall()
    print(f"  记录 {len(rows):,} 条，用时 {time.time()-t0:.1f}s")

    from smartreact import ReactionEnumerator
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    enum = ReactionEnumerator()

    per_class: Dict[str, Dict[str, object]] = {}
    per_family_class: Dict[str, set] = defaultdict(set)
    by_solvent_class: Dict[str, Counter] = defaultdict(Counter)
    n_ok = n_fail = 0
    n_split_fail = n_no_sub = 0
    n_elem_ok = 0
    el_pat: Dict[str, Counter] = defaultdict(Counter)
    el_dH: Dict[str, list] = defaultdict(list)
    el_dO: Dict[str, list] = defaultdict(list)
    TEMP: Dict[str, list] = defaultdict(list)

    from ord_conditions import contributing_split
    from rdkit import Chem                                          # noqa: E402
    from rdkit.Chem import rdMolDescriptors                          # noqa: E402
    import re                                                        # noqa: E402
    RDLogger.DisableLog("rdApp.*")

    def elem_counts(smiles_list):
        out = {"C": 0, "H": 0, "N": 0, "O": 0}
        for s in smiles_list:
            m = Chem.MolFromSmiles(s)
            if m is None:
                continue
            f = rdMolDescriptors.CalcMolFormula(m)
            for el, k in re.findall(r"([A-Z][a-z]?)(\d*)", f):
                if el in out:
                    out[el] += int(k) if k else 1
        return out


    BATCH = 5000
    t1 = time.time()
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        # ★ 口径（第一版错了，2026-10-13 修）：不能用**含试剂的原始 reactants 串**。
        #   引擎的 `enumerate_pairs` 只吃"底物对"（和 step 里 payload 同款），
        #   而 ORD 的 reactants 侧常含 3+ 组分（底物 + 试剂/催化剂）。
        #   第一版直接丢原始串 -> 归类率只有 26%（4 片实测 3,944/15,000）。
        #   正确做法：用 ord_conditions.contributing_split()（项目既有、单一真相）
        #   拆出【映射原子真进产物的贡献组分】= 真底物，再与产物侧配对。
        meta = []
        for r in chunk:
            lhs, rhs, solv, temp = str(r[0] or ""), str(r[1] or ""), r[2], r[3]
            if not lhs or not rhs:
                continue
            try:
                subs, _reags = contributing_split(lhs, rhs)
            except Exception:                    # noqa: BLE001 —— 累计，不静默
                n_split_fail += 1
                continue
            if not subs:
                n_no_sub += 1
                continue
            # ★★ 主体证据（覆盖 100% 可用记录）：**元素收支模式**。
            #   为什么用这个而不是"模板归类"：归类依赖 37 类模板的覆盖率
            #   （实测只有 26~33%），而元素收支对每条记录都算得出来，且与
            #   `tools/_probe_ord_element_direction.py` 的实测口径完全一致。
            bucket = solvent_bucket(solv)
            prods = [x for x in str(rhs).split(".") if x.strip()]
            cs, cp = elem_counts(subs), elem_counts(prods)
            dH, dO = cp["H"] - cs["H"], cp["O"] - cs["O"]
            if dH < 0 and dO < 0:
                pat = "H_down_O_down"
            elif dH > 0 and dO > 0:
                pat = "H_up_O_up"
            elif dH == 0 and dO == 0:
                pat = "unchanged"
            else:
                pat = "mixed"
            el_pat[bucket][pat] += 1
            el_dH[bucket].append(dH)
            el_dO[bucket].append(dO)
            n_elem_ok += 1
            meta.append((subs, rhs, solv, temp))
        payload = [(subs[0], subs[1] if len(subs) > 1 else subs[0])
                   for subs, _rhs, _s, _t in meta]
        if not payload:
            n_fail += len(chunk)
            continue
        try:
            got = list(enum.enumerate_pairs(payload, parallel=True))
        except TypeError:
            got = list(enum.enumerate_pairs(payload))
        except Exception as ex:                    # noqa: BLE001 —— 累计，不静默
            n_fail += len(chunk)
            print(f"   [warn] 第 {i} 批归类异常：{type(ex).__name__}: {ex}")
            continue

        # 归组：按 (lhs, rhs) 取回这一类记录命中的反应类型
        by_pair: Dict[tuple, set] = defaultdict(set)
        for r in got:
            nm = getattr(r, "reaction_name", "")
            if not nm:
                continue
            a = getattr(r, "reactant_a", "")
            b = getattr(r, "reactant_b", "")
            by_pair[(a, b)].add(nm)
        for (subs, rhs, solv, temp) in meta:
            names = by_pair.get((subs[0], subs[1] if len(subs) > 1 else subs[0])) or set()
            if not names:
                n_fail += 1
                continue
            n_ok += 1
            bucket = solvent_bucket(solv)
            for nm in names:
                d = per_class.setdefault(nm, {"n": 0, "solvents": Counter(),
                                              "temp": []})
                d["n"] += 1                      # type: ignore[operator]
                d["solvents"][bucket] += 1       # type: ignore[index]
                if temp is not None:
                    d["temp"].append(float(temp))  # type: ignore[union-attr]
                by_solvent_class[bucket][nm] += 1
        if (i // BATCH) % 2 == 0:
            print(f"   {i+len(chunk):,}/{len(rows):,}  归类成功 {n_ok:,}  "
                  f"失败 {n_fail:,}  {time.time()-t1:.1f}s", flush=True)

    def _med(v):
        if not v:
            return None
        v = sorted(v)
        return round(v[len(v) // 2], 1)

    out_per_class = {}
    for nm, d in per_class.items():
        out_per_class[nm] = {
            "n": int(d["n"]),                       # type: ignore[arg-type]
            "by_solvent_class": dict(d["solvents"]),  # type: ignore[arg-type]
            "top_solvents": [k for k, _v in
                             (d["solvents"].most_common(3)  # type: ignore[union-attr]
                              if hasattr(d["solvents"], "most_common") else [])],
            "median_temp_C": _med(d["temp"]),        # type: ignore[arg-type]
        }

    # 家族级（用方向判据表的 class->family 映射）
    from direction import class_to_family
    c2f = class_to_family()
    per_family: Dict[str, Dict[str, object]] = {}
    for nm, row in out_per_class.items():
        fam = c2f.get(nm)
        if not fam:
            continue
        f = per_family.setdefault(fam, {"n": 0, "solvents": Counter()})
        f["n"] += row["n"]                          # type: ignore[operator]
        for k, v in (row["by_solvent_class"] or {}).items():
            f["solvents"][k] += v                   # type: ignore[index]
    per_family_out = {k: {"n": int(v["n"]),
                          "by_solvent_class": dict(v["solvents"]),
                          "top_solvents": [x for x, _c in
                                           v["solvents"].most_common(3)]}  # type: ignore[union-attr]
                      for k, v in per_family.items()}

    payload_j = {
        "what": "ORD 文献侧方向证据：① 元素收支模式（按溶剂桶）② 元素差中位数 "
                "③ 每类反应/家族在各溶剂桶下出现过多少次（模板归类，覆盖率有限）",
        "caveat": ("① 只证明『文献里有这个方向』，不证明『热力学可行』；"
                   "② ORD 是成功实验集（实测脱水缩合 41.7% vs 水解形状 0.9%），"
                   "所以水相水解在 ORD 里天然缺证据 —— 这不是反证，"
                   "而是这套数据本身的发表偏倚"),
        "source": f"reports/ord_condition_dataset/shard_0000..{len(use)-1:04d}.parquet",
        "n_records": len(rows),
        "n_element_ok": n_elem_ok,
        "n_classified": n_ok,
        "n_unclassified_by_template": n_fail,
        "classification_coverage": round(n_ok / max(1, n_elem_ok), 4),
        "n_split_failed": n_split_fail,
        "n_no_contributing_substrate": n_no_sub,
        "shards_used": len(use),
        "element_patterns_by_solvent_class": {
            b: {"n": sum(c.values()), **{k: v for k, v in c.items()}}
            for b, c in el_pat.items()},
        "element_delta_median_by_solvent_class": {
            b: {"dH": _med(el_dH[b]), "dO": _med(el_dO[b]), "n": len(el_dH[b])}
            for b in el_pat},
        "per_class": out_per_class,
        "per_family": per_family_out,
        "by_solvent_class": {k: dict(v) for k, v in by_solvent_class.items()},
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload_j, f, ensure_ascii=False, indent=1)

    print(f"\n元素收支可用 {n_elem_ok:,} 条；模板归类成功 {n_ok:,} "
          f"（覆盖率 {n_ok/max(1, n_elem_ok):.0%}）")
    print("按溶剂桶的元素收支模式：")
    for b, c in el_pat.items():
        tot = sum(c.values()) or 1
        print(f"   {b:<10} n={tot:>7,}  " +
              "  ".join(f"{k} {v/tot:.1%}" for k, v in c.most_common()))
    print(f"\n-> {args.out}  ({Path(args.out).stat().st_size/1024:.0f} KB, "
          f"{time.time()-t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
