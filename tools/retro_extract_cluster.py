# -*- coding: utf-8 -*-
r"""② 后半段：从 ORD 按逆方向抽模板 + 聚类 + 留出集评估。

口径（先说清再测）
--------------------------------------------------------------------
训练集 : ORD 前 90%（默认只取前 N 条，N 可调）
测试集 : ORD 后 10% 区域里抽的干净反应（单产物、1~3 个反应物、产物带映射）
         —— 只用于评估，绝不参与抽模板
抽模板 : rdchiral.template_extractor，retro=True（逆方向）
聚类   : 按【反应中心指纹】分桶，桶内保留出现频次最高的代表模板
         ★ 上次失败就是漏了这一步（交接单：test 召回仅 1.4%）
评估   : 对测试反应的【产物】套模板，看能否生成出【真实反应物组合】
         - 用产物子结构做浅层预筛，避免对每条测试跑全部模板
         - recall = 命中数 / 可评估数

用法:
  python retro_extract_cluster.py --train-n 100000 --test-n 400
  python retro_extract_cluster.py --train-n 0            # 全量训练集
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
for _p in (STAGE / "libs", STAGE / "tools", Path(r"D:\TCMAI\src")):
    sys.path.insert(0, str(_p))

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
REPORTS = STAGE / "reports"
TPL_RAW = REPORTS / "retro_templates_raw.jsonl"
TPL_CLUSTERED = REPORTS / "retro_templates_clustered.jsonl"
OUT = REPORTS / "retro_extract_cluster_eval.json"


# ------------------------------------------------------------------ 抽模板（子进程）
def extract_batch(rows):
    """rows = [(reaction_blob,)] -> [(template_smarts, rxn_smiles, center_fp), ...]"""
    import contextlib
    import io
    import os
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    import rdchiral.template_extractor as te
    from rdchiral.template_extractor import extract_from_reaction
    from ord_schema.proto import reaction_pb2
    # ★ rdchiral 在失败路径上会无条件 print（实测 4 万条刷出 6000+ 行），
    #   必须在【函数体内部】把 stdout 堵住（放在模块顶层没用：spawn 的子进程
    #   是在 import 之后才跑的，第一次就是这样漏出去了）。
    te.VERBOSE = False
    _sink = open(os.devnull, "w")
    _old = os.dup(1)
    os.dup2(_sink.fileno(), 1)

    out = []
    stat = Counter()
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            stat["protobuf失败"] += 1
            continue
        cx = next((i.value for i in rxn.identifiers
                   if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value),
                  None)
        if not cx:
            stat["无CXSMILES"] += 1
            continue
        body = cx.split("|", 1)[0] if "|" in cx else cx
        parts = body.split(">")
        if len(parts) == 2:
            lhs, rhs = parts
        elif len(parts) == 3:
            lhs, _mid, rhs = parts
        else:
            stat["段数异常"] += 1
            continue
        # rdchiral 需要 "*>>*" 形式且两侧都带映射
        rs = [p for p in lhs.split(".") if p.strip()]
        ps = [p for p in rhs.split(".") if p.strip()]
        if not rs or not ps:
            stat["空侧"] += 1
            continue
        if not any(":" in p for p in ps):
            stat["产物无映射"] += 1
            continue
        rxn_smi = ".".join(rs) + ">>" + ".".join(ps)
        # ★ rdchiral 的键名是 reactants / products（复数，都要）★
        #   实测：传 product（单数）或 reaction_smiles 一律 KeyError ->
        #   上次"抽模板全失败"就死在这里，跟聚类没关系。
        try:
            t = extract_from_reaction({"reactants": ".".join(rs),
                                       "products": ".".join(ps),
                                       "_id": "x"})
        except Exception as e:
            stat[f"抽取异常:{type(e).__name__}"] += 1
            continue
        if not t or not t.get("reaction_smarts"):
            stat["抽取空(rdchiral拒绝)"] += 1
            continue
        tpl = t["reaction_smarts"]
        if ">>" not in tpl:
            stat["无SMARTS"] += 1
            continue
        # 反应中心指纹：形成的键 / 断裂的键
        try:
            lhs_s, rhs_s = tpl.split(">>")
            fp = _center_fp(lhs_s, rhs_s)
        except Exception:
            fp = "?"
        out.append((tpl, rxn_smi, fp))
        stat["成功"] += 1
    try:
        sys.stdout.flush()
        os.dup2(_old, 1)          # 恢复 stdout，否则返回值/异常都跟着被吞
        _sink.close()
    except Exception:
        pass
    return out, stat


def _center_fp(lhs, rhs):
    """把 SMARTS 两侧的原子环境简化成指纹字符串（用于聚类分桶）。"""
    def atoms(side):
        toks = []
        for part in side.split("."):
            buf = ""
            depth = 0
            for ch in part:
                if ch == "[":
                    depth += 1
                    buf = ""
                elif ch == "]":
                    depth -= 1
                    toks.append(buf)
                elif depth > 0:
                    buf += ch
                elif ch.isalpha() or ch == "*":
                    toks.append(ch)
            return toks
    a = [x.split(":")[0] for x in atoms(lhs)]
    b = [x.split(":")[0] for x in atoms(rhs)]
    return "R:" + ",".join(sorted(a)) + "|P:" + ",".join(sorted(b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-n", type=int, default=100000)
    ap.add_argument("--test-n", type=int, default=400)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--min-freq", type=int, default=3, help="聚类后保留的最低频次")
    args = ap.parse_args()
    t0 = time.time()

    import duckdb
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdChemReactions
    RDLogger.DisableLog("rdApp.*")

    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    total = con.execute(
        f"SELECT num_rows FROM parquet_file_metadata('{BIG.as_posix()}')").fetchone()[0]
    n_train = args.train_n if args.train_n > 0 else int(total * 0.9)

    print("=" * 94)
    print("② 后半段：ORD 逆方向抽模板 + 聚类 + 留出集评估")
    print("=" * 94)
    print(f"总行数 {total:,}；训练集 {n_train:,}（前 90% 区间内）；"
          f"测试集 {args.test_n:,}（后 10% 区间）")

    # ---------------- ① 抽模板（并行） ----------------
    print(f"\n① 抽模板（rdchiral retro=True，{args.workers} 进程）...", flush=True)
    cur = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') LIMIT {n_train}")
    all_t, stat = [], Counter()
    pending = []
    n_done = 0
    chunk = 2000
    # ★ 用线程池（RDKit/rdchiral 都会释放 GIL）+ 每块超时：
    #   进程池在个别分子上会整池挂死（实测两次），线程池卡住一块不影响全局。
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FTimeout
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while True:
            rows = cur.fetchmany(chunk)
            if not rows:
                break
            n_done += len(rows)
            pending.append(pool.submit(extract_batch, rows))
            if len(pending) >= args.workers * 2:
                fu = pending.pop(0)
                try:
                    ts, st = fu.result(timeout=300)
                except FTimeout:
                    ts, st = [], Counter({"块超时": 1})
                    print(f"   [warn] 有一块抽模板超时 300s，跳过", flush=True)
                except Exception as e:
                    ts, st = [], Counter({f"块异常:{type(e).__name__}": 1})
                all_t.extend(ts)
                stat.update(st)
                el = time.time() - t0
                if n_done % 20000 < chunk:
                    print(f"   {n_done:>8,}/{n_train:,}  模板 {len(all_t):>8,}  "
                          f"{el:.0f}s  ({n_done/max(el,1):.0f} 条/s)", flush=True)
        for fu in pending:
            try:
                ts, st = fu.result(timeout=300)
            except Exception:
                ts, st = [], Counter({"块超时/异常": 1})
            all_t.extend(ts)
            stat.update(st)
    print(f"   抽取完成：模板实例 {len(all_t):,}   统计 {dict(stat)}")

    # ---------------- ② 聚类 ----------------
    print("\n② 按反应中心指纹聚类...", flush=True)
    buckets = defaultdict(list)
    for tpl, rxn_smi, fp in all_t:
        buckets[fp].append(tpl)
    print(f"   指纹桶 {len(buckets):,} 个")
    clustered = []
    for fp, lst in buckets.items():
        c = Counter(lst)
        for tpl, n in c.most_common(3):        # 每桶最多留 3 个代表（避多样性丢失）
            if n >= args.min_freq:
                clustered.append({"template": tpl, "fp": fp, "freq": n})
    print(f"   实例 {len(all_t):,} -> 桶 {len(buckets):,} -> 代表模板 {len(clustered):,}")
    with open(TPL_CLUSTERED, "w", encoding="utf-8") as f:
        for r in clustered:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"   -> {TPL_CLUSTERED.name}")
    with open(TPL_RAW, "w", encoding="utf-8") as f:
        for tpl, rxn_smi, fp in all_t:
            f.write(json.dumps({"template": tpl, "rxn": rxn_smi, "fp": fp},
                               ensure_ascii=False) + "\n")

    # ---------------- ③ 留出集评估 ----------------
    print("\n③ 留出集评估...", flush=True)
    off = int(total * 0.9)
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') "
        f"OFFSET {off} LIMIT {args.test_n * 3}").fetchall()
    tests = []
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction() if False else None
        from ord_schema.proto import reaction_pb2 as rp
        rxn = rp.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            continue
        cx = next((i.value for i in rxn.identifiers
                   if i.type == rp.ReactionIdentifier.REACTION_CXSMILES and i.value), None)
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
    print(f"   测试反应 {len(tests):,} 条")

    # 编译模板 + 浅层预筛（产物子结构）
    compiled, bad = [], 0
    for r in clustered:
        try:
            rx = rdChemReactions.ReactionFromSmarts(r["template"])
            if rx is None or rx.GetNumReactantTemplates() != 1:
                bad += 1
                continue
            q = rx.GetReactantTemplate(0)
            compiled.append((r["template"], rx, q, r["freq"]))
        except Exception:
            bad += 1
    print(f"   可编译模板 {len(compiled):,}（失败 {bad}）")

    def norm(smi):
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)

    hit = n_eval = 0
    t1 = time.time()
    for i, t in enumerate(tests):
        m = Chem.MolFromSmiles(t["product"])
        if m is None:
            continue
        n_eval += 1
        want = set()
        for r in t["reactants"]:
            c = norm(r)
            if c:
                want.add(c)
        if not want:
            continue
        ok = False
        for tpl, rx, q, freq in compiled:
            try:
                if not m.HasSubstructMatch(q):
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
                    if not good:
                        continue
                except Exception:
                    continue
                if got == want:
                    ok = True
                    break
            if ok:
                break
        if ok:
            hit += 1
        if n_eval % 50 == 0:
            print(f"     {n_eval}/{len(tests)}  命中 {hit} "
                  f"({hit/max(n_eval,1)*100:.1f}%)  {time.time()-t1:.0f}s", flush=True)

    res = {
        "n_train": n_train, "n_test": n_eval,
        "n_template_instances": len(all_t),
        "n_buckets": len(buckets),
        "n_clustered": len(clustered),
        "n_compiled": len(compiled),
        "min_freq": args.min_freq,
        "hit": hit,
        "recall": round(hit / max(n_eval, 1), 4),
        "extract_stat": dict(stat),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print("=" * 94)
    print(f"结果：训练 {n_train:,} 条 -> 聚类后模板 {len(clustered):,} 条")
    print(f"      留出集 {n_eval:,} 条，命中 {hit:,}，"
          f"★ recall = {hit/max(n_eval,1)*100:.2f}%")
    print("=" * 94)
    print(f"-> {OUT.name}   总耗时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
