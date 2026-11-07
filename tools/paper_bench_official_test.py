# -*- coding: utf-8 -*-
"""外部 baseline（B 档）：在 USPTO-50k 官方 test split 上跑我们的正向模型。

为什么单独写：
- 论文里的 92.01% / 94.25% 都跑在 reports/paper/data/uspto50k_canon.jsonl
  （= 50,016 条全集，我们自己从 USPTO_50K 整理）。
- 文献里常报的 top-1 一般在官方 5,001 条 test split 上（RetroXpert / GLAD 那一套切分）。
- 两个分母不能混，所以这里直接吃官方 raw_test.csv。

用法：
  python -I tools/paper_bench_official_test.py [workers]
  CHEMCREACT_BENCH_OUT=... TAG=... 与 50k 工具保持一致。
  CHEMCREACT_BENCH_LIMIT=N   只跑前 N 条（调试）。
  CHEMCREACT_BENCH_SHARD=i/n 分片。

输入：reports/paper/data/uspto50k_official/raw_test.csv
      列 = id,class,reactants>reagents>productions（带原子映射）
输出：<OUT>/forward_official_test__<TAG>.json
"""
from __future__ import annotations

import csv
import json
import multiprocessing as mp
import os as _os
import re
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
for _p in (_ROOT / "core", _ROOT / "conditions", _ROOT / "rules", _HERE):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SRC = _ROOT / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"
MIT_SRC = _ROOT / "reports" / "paper" / "data" / "uspto_mit" / "USPTO_MIT.csv"
SRC_KIND = (_os.environ.get("CHEMCREACT_BENCH_SRC") or "official").strip().lower()
MIT_SAMPLE_PCT = float(_os.environ.get("CHEMCREACT_BENCH_SAMPLE_PCT") or 8.36)
HASH_SEED = _os.environ.get("CHEMCREACT_BENCH_HASH_SEED") or "20261106"
OUT_DIR = Path(_os.environ.get("CHEMCREACT_BENCH_OUT")
               or (_ROOT / "reports" / "paper" / "results"))
TAG = _os.environ.get("CHEMCREACT_BENCH_TAG") or "official_test"

_MAP = re.compile(r"\[([A-Za-z@+\-0-9]*?):(\d+)\]")


def strip_map(smi: str) -> str:
    """去掉原子映射号：'[CH2:18]' -> '[CH2]'。只做映射剥离，不做化学改写。"""
    return _MAP.sub(r"[\1]", smi)


def _heavy(smi: str) -> int:
    """重原子数（解析失败记 0，避免排序炸）。"""
    from rdkit import Chem
    m = Chem.MolFromSmiles(smi)
    return m.GetNumHeavyAtoms() if m else 0


def load_records() -> list[dict]:
    if SRC_KIND == "mit":
        return _load_mit()
    recs = []
    with open(SRC, encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            rxn = row.get("reactants>reagents>production") or ""
            parts = rxn.split(">")
            if len(parts) != 3:
                continue
            lhs, _reagents, rhs = parts
            reactants = [strip_map(s) for s in lhs.split(".") if s.strip()]
            products = [strip_map(s) for s in rhs.split(".") if s.strip()]
            # 官方切分里有 1 底物反应、以及多产物（主产物+盐/小分子）的情形。
            # 口径：底物取 1~2 个；产物取重原子数最多的那个（主产物）。
            if not (1 <= len(reactants) <= 2) or not products:
                continue
            products.sort(key=_heavy, reverse=True)
            n_prod_all = len(products)
            if _os.environ.get("CHEMCREACT_BENCH_STRICT_SINGLE") == "1" and n_prod_all != 1:
                continue
            products = products[:1]
            recs.append({
                "i": i,
                "id": row.get("id", ""),
                "class": row.get("class", ""),
                "reactants": reactants,
                "product": products[0],
                "n_products_total": n_prod_all,
                "n_reactants": len(reactants),
            })
    return recs


def _load_mit() -> list[dict]:
    """USPTO-MIT 480K（DeepChem 镜像，单列 `reactions`）。

    没有官方切分文件可用（Jin 2017 的 40k test 在我们的可访问渠道里下不到），
    所以用**确定性哈希抽样**：md5(seed+反应串) 取模百分比，稳定可复现。
    抽样比例默认 8.36%（≈40,000/479,035）。
    """
    import hashlib

    recs = []
    with open(MIT_SRC, encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            rxn = row.get("reactions") or ""
            parts = rxn.split(">")
            if len(parts) != 3:
                continue
            h = hashlib.md5((HASH_SEED + rxn).encode("utf-8")).hexdigest()
            if (int(h[:8], 16) % 10000) >= MIT_SAMPLE_PCT * 100:
                continue
            reactants = [strip_map(s) for s in parts[0].split(".") if s.strip()]
            products = [strip_map(s) for s in parts[2].split(".") if s.strip()]
            if not (1 <= len(reactants) <= 2) or not products:
                continue
            products.sort(key=_heavy, reverse=True)
            recs.append({
                "i": i,
                "id": str(i),
                "class": "mit",
                "reactants": reactants,
                "product": products[0],
                "n_products_total": len(products),
                "n_reactants": len(reactants),
            })
    print(f"[mit] 抽样 {len(recs)} 条（seed={HASH_SEED}, pct={MIT_SAMPLE_PCT}）")
    return recs


_G: dict = {}


def _init() -> None:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    kw = {}
    for env, key, conv in (
        ("CHEMCREACT_BENCH_EXTRA_LIMIT", "extra_template_limit", int),
        ("CHEMCREACT_BENCH_EXTRA_MIN_SUPPORT", "extra_template_min_support", int),
        ("CHEMCREACT_BENCH_MONO_LIMIT", "mono_template_limit", int),
        ("CHEMCREACT_BENCH_MAXPROD", "max_products_per_pair", int),
    ):
        if _os.environ.get(env):
            kw[key] = conv(_os.environ[env])
    if _os.environ.get("CHEMCREACT_BENCH_MONO_CO_REAGENT"):
        kw["mono_include_co_reagent"] = True
    _G["eng"] = SmartReactEngine(**kw)
    _G["cond"] = T.get_template("煎煮")
    _G["Compound"] = Compound
    _G["canon"] = lambda s: (lambda m: Chem.MolToSmiles(m) if m else None)(
        Chem.MolFromSmiles(s))


def _work(batch: list[dict]) -> list[dict]:
    canon = _G["canon"]
    out = []
    for rec in batch:
        comps = [_G["Compound"](smiles=s, name="R%d" % j, herb="(bench)")
                 for j, s in enumerate(rec["reactants"])]
        try:
            prods = _G["eng"].step(comps, _G["cond"], round_no=1)
        except Exception as ex:  # 逐条记录，不静默吞掉
            out.append({"i": rec["i"], "error": type(ex).__name__})
            continue
        ordered = sorted(prods, key=lambda p: int(getattr(p, "seq", 0) or 0))
        seq_smiles = [getattr(p, "smiles", "") for p in ordered if getattr(p, "smiles", "")]
        want = canon(rec["product"])
        hit = bool(want and want in seq_smiles)
        rank = (seq_smiles.index(want) + 1) if hit else 0
        out.append({
            "i": rec["i"], "class": rec["class"], "hit": hit, "rank": rank,
            "n_products": len(seq_smiles),
        })
    return out


def main() -> int:
    t0 = time.time()
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    recs = load_records()
    if _os.environ.get("CHEMCREACT_BENCH_SHARD"):
        si, sn = (int(x) for x in _os.environ["CHEMCREACT_BENCH_SHARD"].split("/"))
        recs = [r for k, r in enumerate(recs) if k % sn == si]
        print("分片 %d/%d：本片 %d 条" % (si, sn, len(recs)))
    if _os.environ.get("CHEMCREACT_BENCH_LIMIT"):
        recs = recs[: int(_os.environ["CHEMCREACT_BENCH_LIMIT"])]
    print("官方 test split：%d 条（workers=%d）" % (len(recs), workers))

    batches = [recs[k:k + 64] for k in range(0, len(recs), 64)]
    res: list[dict] = []
    if workers <= 1:
        _init()
        for k, b in enumerate(batches):
            res.extend(_work(b))
            if k % 5 == 0:
                print("  ...%d/%d  %.0f s" % (len(res), len(recs), time.time() - t0))
                sys.stdout.flush()
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(workers, initializer=_init) as pool:
            for k, part in enumerate(pool.imap_unordered(_work, batches)):
                res.extend(part)
                if k % 5 == 0:
                    print("  ...%d/%d  %.0f s" % (len(res), len(recs), time.time() - t0))
                    sys.stdout.flush()

    res.sort(key=lambda r: r["i"])
    ok = [r for r in res if "error" not in r]
    err = [r for r in res if "error" in r]
    n = len(recs)
    hits = sum(1 for r in ok if r["hit"])
    ranks = [r["rank"] for r in ok if r["hit"]]
    mean_cand = sum(r["n_products"] for r in ok) / max(1, len(ok))
    by_class: dict = {}
    for r in ok:
        d = by_class.setdefault(str(r["class"]), {"n": 0, "hit": 0})
        d["n"] += 1
        d["hit"] += 1 if r["hit"] else 0

    def topk(k: int) -> float:
        return round(sum(1 for x in ranks if x <= k) / max(1, len(ok)), 4)

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": str(SRC),
        "n_reactions": n,
        "n_scored": len(ok),
        "n_errors": len(err),
        "recall_1step": round(hits / max(1, len(ok)), 4),
        "top1": topk(1), "top3": topk(3), "top5": topk(5), "top10": topk(10),
        "mrr": round(sum(1.0 / x for x in ranks) / max(1, len(ok)), 4),
        "candidate_stats": {"mean": round(mean_cand, 2)},
        "by_class_recall": {c: {"n": d["n"], "rate": round(d["hit"] / d["n"], 4)}
                            for c, d in sorted(by_class.items())},
        "seconds": round(time.time() - t0, 1),
        "config_env": {k: v for k, v in _os.environ.items()
                       if k.startswith("CHEMCREACT_BENCH_")},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / ("forward_official_test__%s.json" % TAG)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    per_path = OUT_DIR / ("forward_official_test__%s.jsonl" % TAG)
    with open(per_path, "w", encoding="utf-8", newline="\n") as fh:
        for r in res:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("命中 %d/%d = %.2f%%  top1 %.2f%%  top5 %.2f%%  MRR %.4f  平均候选 %.1f  错误 %d"
          % (hits, len(ok), 100.0 * hits / max(1, len(ok)),
             100 * summary["top1"], 100 * summary["top5"], summary["mrr"], mean_cand, len(err)))
    print("写出", out_path)
    print("耗时 %.0f s" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
