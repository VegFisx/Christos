# -*- coding: utf-8 -*-
r"""② 后半段（收尾）：合并分片 -> 聚类 -> 留出集评估。

用法:
  python retro_cluster_eval.py --test-n 150 --min-freq 3
"""
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

import os as _os_root          # ★ 复现演练（B10）：仓库根可被环境变量覆盖，默认不变
STAGE = Path(_os_root.environ.get("CHEMCREACT_ROOT")
             or r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", Path(r"D:\TCMAI\src")):
    sys.path.insert(0, str(_p))

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
REPORTS = STAGE / "reports"
OUT = REPORTS / "retro_cluster_eval.json"
CLUSTERED = REPORTS / "retro_templates_clustered.jsonl"


def center_fp(tpl):
    """反应中心指纹：把 SMARTS 两侧原子剥成 元素+芳香性+电荷 的集合，用于分桶。"""
    try:
        lhs, rhs = tpl.split(">>")
    except ValueError:
        return "?"
    def atoms(side):
        toks, buf, depth = [], "", 0
        for ch in side:
            if ch == "[":
                depth, buf = 1, ""
            elif ch == "]":
                depth = 0
                toks.append(buf)
            elif depth:
                buf += ch
            elif ch.isalpha() or ch == "*":
                toks.append(ch)
        out = []
        for t in toks:
            core = t.split(":")[0]
            out.append(core)
        return out
    return "R:" + ",".join(sorted(atoms(lhs))) + "|P:" + ",".join(sorted(atoms(rhs)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-n", type=int, default=150)
    ap.add_argument("--min-freq", type=int, default=3)
    ap.add_argument("--per-bucket", type=int, default=3)
    ap.add_argument("--test-frac", type=float, default=0.9,
                    help="测试集起点（占全量比例），默认 0.9 = 留出区间")
    ap.add_argument("--baseline", action="store_true",
                    help="同一测试集上再跑一遍 SmartReact 反转模板（对照）")
    # ★ 第四十四轮（论文基准）：剔除"排除表里的产物"对应的抽取记录后可重聚类出干净库
    ap.add_argument("--exclude-products", type=str, default="",
                    help="JSONL（含 product 字段）或每行一个 SMILES：凡产物命中其中的抽取记录一律删")
    ap.add_argument("--out-clustered", type=str, default="",
                    help="聚类输出路径（默认写 reports/retro_templates_clustered.jsonl）")
    ap.add_argument("--skip-eval", action="store_true",
                    help="只做合并+聚类，跳过留出集评估（评估需要 duckdb/ord_schema）")
    # ★ L1（2026-10-15）：把全量挖矿的新分片并进来（如 "reports/ord_shards_full/shard_*.jsonl"）
    ap.add_argument("--extra-shards", type=str, default="",
                    help="额外的分片 glob（相对 chemreact-staging 目录）")
    args = ap.parse_args()
    t0 = time.time()

    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdChemReactions
    RDLogger.DisableLog("rdApp.*")

    print("=" * 94)
    print("② 后半段：合并分片 -> 聚类 -> 留出集评估")
    print("=" * 94)

    # ---------------- ① 合并分片 ----------------
    def _canon_unmap(frag):
        import re
        s = re.sub(r":\d+", "", frag or "").strip()
        m2 = Chem.MolFromSmiles(s) if s else None
        return Chem.MolToSmiles(m2) if m2 is not None else None

    excl = set()
    if args.exclude_products:
        pth = Path(args.exclude_products)
        with open(pth, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                got = None
                try:
                    got = json.loads(line).get("product")
                except Exception:
                    pass
                excl.add(got if got else line.split("\t")[0])
        print(f"   排除集合：{len(excl):,} 个产物（来自 {pth.name}）")

    shards = sorted(REPORTS.glob("_shard_[0-9].jsonl"))
    if args.extra_shards:
        extra = sorted(Path(STAGE).glob(args.extra_shards))
        print(f"   追加分片：{len(extra)} 个（{args.extra_shards}）")
        shards += extra
    all_t = []
    n_excl = 0
    for p in shards:
        n = 0
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if excl:
                    rx = str(r.get("rx") or "")
                    if rx:
                        _, _, rs_ = rx.partition(">>")
                        if any(_canon_unmap(x) in excl for x in rs_.split(".") if x.strip()):
                            n_excl += 1
                            continue
                all_t.append(r["template"])
                n += 1
        print(f"   {p.name}: {n:>7,}")
    print(f"   合计模板实例 {len(all_t):,}（剔除 {n_excl:,}）")

    # ---------------- ② 聚类 ----------------
    buckets = defaultdict(list)
    for tpl in all_t:
        buckets[center_fp(tpl)].append(tpl)
    clustered = []
    for fp, lst in buckets.items():
        for tpl, n in Counter(lst).most_common(args.per_bucket):
            if n >= args.min_freq:
                clustered.append({"template": tpl, "fp": fp, "freq": n})
    print(f"\n   指纹桶 {len(buckets):,}  ->  聚类后模板 {len(clustered):,}")
    clustered_path = Path(args.out_clustered) if args.out_clustered else CLUSTERED
    with open(clustered_path, "w", encoding="utf-8") as f:
        for r in clustered:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if args.skip_eval:
        print(f"   聚类输出 -> {clustered_path}（--skip-eval：不跑留出集评估）")
        return

    # ---------------- ③ 留出集评估 ----------------
    import duckdb
    from ord_schema.proto import reaction_pb2
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    total = con.execute(
        f"SELECT num_rows FROM parquet_file_metadata('{BIG.as_posix()}')").fetchone()[0]
    off = int(total * args.test_frac)
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') "
        f"OFFSET {off} LIMIT {args.test_n * 3}").fetchall()
    tests = []
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            continue
        cx = next((i.value for i in rxn.identifiers
                   if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value),
                  None)
        if not cx:
            continue
        body = cx.split("|", 1)[0] if "|" in cx else cx
        parts = body.split(">")
        if len(parts) == 2:
            lhs, rhs = parts
        elif len(parts) == 3:
            lhs, _m, rhs = parts
        else:
            continue
        ps = [p for p in rhs.split(".") if p.strip()]
        rs = [p for p in lhs.split(".") if p.strip()]
        if len(ps) != 1 or not (1 <= len(rs) <= 3) or ":" not in ps[0]:
            continue
        tests.append({"reactants": rs, "product": ps[0]})
        if len(tests) >= args.test_n:
            break
    print(f"\n   测试反应 {len(tests):,} 条（起点 {off:,} = 全量 {args.test_frac:.0%} 处）")

    def norm(smi):
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)

    def make_matcher(templates_compiled):
        """返回 match(product_smiles, want_set) -> (是否命中, 命中模板)。"""
        def match(prod_smi, want):
            m = Chem.MolFromSmiles(prod_smi)
            if m is None:
                return False, None
            for tpl, rx, q in templates_compiled:
                try:
                    if q is not None and not m.HasSubstructMatch(q):
                        continue
                except Exception:
                    continue
                try:
                    res = rx.RunReactants((m,))
                except Exception:
                    continue
                for tup in res[:20]:
                    try:
                        got = set()
                        good = True
                        for pm in tup:
                            Chem.SanitizeMol(pm)
                            c = norm(Chem.MolToSmiles(pm))
                            if not c:
                                good = False
                                break
                            got.add(c)
                    except Exception:
                        good = False
                    if good and got == want:
                        return True, tpl
            return False, None
        return match

    compiled, bad = [], 0
    for r in clustered:
        try:
            rx = rdChemReactions.ReactionFromSmarts(r["template"])
            if rx is None or rx.GetNumReactantTemplates() != 1:
                bad += 1
                continue
            compiled.append((r["template"], rx, rx.GetReactantTemplate(0)))
        except Exception:
            bad += 1
    print(f"   可编译模板 {len(compiled):,}（失败 {bad}）")
    match_new = make_matcher(compiled)

    match_base = None
    if args.baseline:
        print("   [对照] 载入 SmartReact 反转模板...", flush=True)
        tpl_path = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
        base = []
        for line in tpl_path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            f = line.split("\t")
            if len(f) != 5 or ">>" not in f[3]:
                continue
            lhs, rhs = f[3].split(">>", 1)
            try:
                rx = rdChemReactions.ReactionFromSmarts(f"{rhs}>>{lhs}")
            except Exception:
                continue
            if rx is None or rx.GetNumReactantTemplates() != 1:
                continue
            base.append((f[0], rx, rx.GetReactantTemplate(0)))   # 同样给子结构预筛
        print(f"   [对照] SmartReact 反转模板 {len(base):,} 条")
        match_base = make_matcher(base)

    base_hit = 0
    hit = n_eval = 0
    t1 = time.time()
    hit_fp = Counter()
    for i, t in enumerate(tests):
        m = Chem.MolFromSmiles(t["product"])
        if m is None:
            continue
        want = {norm(r) for r in t["reactants"]}
        want.discard(None)
        if not want:
            continue
        n_eval += 1
        ok, _used = match_new(t["product"], want)
        if ok:
            hit += 1
        if args.baseline:
            bok, _b = match_base(t["product"], want)
            if bok:
                base_hit += 1
        if n_eval % 25 == 0:
            print(f"     {n_eval}/{len(tests)}  命中 {hit} "
                  f"({hit/max(n_eval,1)*100:.1f}%)  {time.time()-t1:.0f}s", flush=True)

    res = {
        "n_template_instances": len(all_t),
        "n_shards": len(shards),
        "n_buckets": len(buckets),
        "n_clustered": len(clustered),
        "n_compiled": len(compiled),
        "min_freq": args.min_freq, "per_bucket": args.per_bucket,
        "test_frac": args.test_frac,
        "n_test": n_eval, "hit": hit,
        "recall": round(hit / max(n_eval, 1), 4),
        "baseline": ("SmartReact_reversed" if args.baseline else None),
        "baseline_hit": (base_hit if args.baseline else None),
        "baseline_recall": (round(base_hit / max(n_eval, 1), 4) if args.baseline else None),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print("=" * 94)
    print(f"结果：模板实例 {len(all_t):,} -> 桶 {len(buckets):,} -> 聚类后 {len(clustered):,}")
    print(f"      测试集 {n_eval:,} 条，命中 {hit:,}，★ recall = {hit/max(n_eval,1)*100:.2f}%")
    if args.baseline:
        print(f"      [对照] SmartReact 反转模板：命中 {base_hit:,}，"
              f"recall = {base_hit/max(n_eval,1)*100:.2f}%")
    print("=" * 94)
    print(f"-> {OUT.name}   总耗时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
