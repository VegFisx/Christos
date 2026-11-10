# -*- coding: utf-8 -*-
r"""C3 探针（2026-11-10）：把池换成「全量 ORD 挖矿的 10% 抽样」，稀有层会涨吗？

背景：第 137 轮实测，120 条稀有记录里 100 条的模板逐字存在于全量挖矿池（286 片、0.85 GB），
而生产池只有 41,619 条（5 万条切片挖出来的，约为语料的 3%）。于是做一个比例实验：

    从 286 片里等距抽 SHARDS 片 → 去重编译 → 对同一批 120 条稀有记录跑，比召回与候选数。

基线（第 136 轮，同一批记录、41,619 条池）：raw 15/120 = 12.5%，中位候选 35。

用法：
    SHARDS=3  python _diag/probe_shard_pool_10pct.py   # 先试内存/耗时
    SHARDS=28 python _diag/probe_shard_pool_10pct.py   # 10% 抽样
"""
from __future__ import annotations

import json
import os
import random
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
for _p in (STAGE / "libs", STAGE / "core", STAGE / "conditions", STAGE / "tools"):
    sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import bench_class_strata as B  # noqa: E402

SHARDS = int(os.environ.get("SHARDS", "3"))
N_RARE = int(os.environ.get("SHARD_N", "120"))
SEED = 20261110
MAX_CAND = 3000
OUT = STAGE / "reports" / ("shard_pool_%dpct_%s_20261110.json" % (max(1, SHARDS * 100 // 286), "union" if os.environ.get("MERGE_S5") else "ordonly"))


def load_templates(n_shards: int):
    files = sorted((STAGE / "reports" / "ord_shards_full").glob("shard_*.jsonl"))
    if n_shards < len(files):
        step = len(files) / n_shards
        files = [files[int(i * step)] for i in range(n_shards)]
    seen = set()
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                j = line.find('"template": "')
                if j < 0:
                    continue
                start = j + 13
                end = line.find('", "rx"', start)
                if end < 0:
                    continue
                seen.add(line[start:end])
    if os.environ.get("MERGE_S5", "") in ("1", "true", "yes"):
        extra = STAGE / "reports" / "mined_forward_templates_full_s5.jsonl"
        n0 = len(seen)
        with open(extra, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                sm = d.get("template")
                if sm:
                    seen.add(sm)
        print("merged production pool: +%d unique (total %d)" % (len(seen) - n0, len(seen)),
              flush=True)
    return files, seen


def compile_pool(smarts_set):
    out = {1: [], 2: [], 3: []}
    bad = 0
    for sm in smarts_set:
        try:
            rxn = AllChem.ReactionFromSmarts(sm)
        except Exception:
            bad += 1
            continue
        if rxn is None:
            bad += 1
            continue
        a = rxn.GetNumReactantTemplates()
        if a in out:
            out[a].append((sm, rxn))
    return out, bad


def run_pool(compiled, mols, want, cap=MAX_CAND):
    from itertools import permutations

    cands = set()
    applied = 0
    for arity, items in compiled.items():
        if arity > len(mols):
            continue
        for sm, rxn in items:
            for perm in permutations(mols, arity):
                try:
                    outs = rxn.RunReactants(perm)
                except Exception:
                    continue
                if not outs:
                    continue
                applied += 1
                for combo in outs:
                    for m in combo:
                        if m is None:
                            continue
                        try:
                            Chem.SanitizeMol(m)
                        except Exception:
                            continue
                        s = Chem.MolToSmiles(m)
                        if s:
                            cands.add(s)
                if len(cands) > cap:
                    return False, len(cands), applied
    want_k = B.ikey(want)
    found = want in cands or (want_k and want_k in {B.ikey(c) for c in cands})
    return found, len(cands), applied


def main() -> int:
    t0 = time.time()
    recs = B.build_sample()
    sigs = [B.class_sig(str(r["reactants"]) + ">>" + str(r["product"])) for r in recs]
    ok = [(r, s) for r, s in zip(recs, sigs) if s is not None]
    freq = Counter(s for _, s in ok)
    rare = [r for r, s in ok if freq[s] <= 3]
    rng = random.Random(SEED)
    picked = rng.sample(rare, min(N_RARE, len(rare)))
    print("rare %d, picked %d, sample built in %.0fs" % (len(rare), len(picked), time.time() - t0),
          flush=True)

    files, smarts = load_templates(SHARDS)
    print("shards %d (%s .. %s), unique templates %d (%.0fs)"
          % (len(files), files[0].name, files[-1].name, len(smarts), time.time() - t0), flush=True)

    compiled, bad = compile_pool(smarts)
    print("compiled arity", {k: len(v) for k, v in compiled.items()}, "bad", bad,
          "(%.0fs)" % (time.time() - t0), flush=True)

    hits = 0
    cands_list = []
    skipped = 0
    for i, r in enumerate(picked, 1):
        parts, _ = B.substrate_components(str(r["reactants"]))
        mols = []
        for p in parts[:2]:
            smi = B.strip_maps(p)
            m = Chem.MolFromSmiles(smi) if smi else None
            if m is not None:
                mols.append(m)
        want = B.canon(r["product"])
        if not mols or not want:
            skipped += 1
            continue
        found, ncand, _applied = run_pool(compiled, mols, want)
        hits += 1 if found else 0
        cands_list.append(ncand)
        if i % 20 == 0:
            print("  %d/%d hits %d (%.0fs)" % (i, len(picked), hits, time.time() - t0),
                  flush=True)

    cands_list.sort()
    median = cands_list[len(cands_list) // 2] if cands_list else None
    payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "shards": len(files),
        "unique_templates": len(smarts),
        "arity": {str(k): len(v) for k, v in compiled.items()},
        "bad": bad,
        "n_picked": len(picked),
        "skipped": skipped,
        "hits": hits,
        "recall": round(hits / max(1, len(picked) - skipped), 4),
        "median_candidates": median,
        "elapsed_s": round(time.time() - t0),
        "baseline_41k": {"hits": 15, "n": 120, "median_candidates": 35},
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

