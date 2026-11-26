# -*- coding: utf-8 -*-
"""用「USPTO-50k 训练半区挖出的正向模板」测官方 test 的 390 条 miss 能补回多少。

只做覆盖探针，不接引擎：
  · 训练池已按反应级 signature 排除官方 test（mine_forward_templates_uspto_train.py）；
  · 用 core/rescue.py 的 RescuePool（原子环境预筛 + 真实反应应用）；
  · 每条 miss 跑「单底物 + 两两」job，与引擎 _rescue_apply 同构；
  · 命中 = 主产物（重原子最多）出现；同时报去立体（平面）命中和新增候选数。

用法：
  python -I tools\\probe_uspto_train_coverage.py --min-support 2
  python -I tools\\probe_uspto_train_coverage.py --min-support 1 --limit 50
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "core", ROOT / "libs", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rescue import RescuePool  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TEST = ROOT / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"
BASE = ROOT / "reports" / "paper" / "results" / "forward_official_test__rerank_v4_official.jsonl"
TPL = ROOT / "reports" / "mined_forward_templates_uspto_train.jsonl"

_MAP = re.compile(r"\[([^:\]]*):\d+\]")


def strip_map(s: str) -> str:
    return _MAP.sub(r"[\1]", s or "")


def canon(s: str, iso: bool = True) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m, isomericSmiles=iso) if m is not None else ""


def heavy(s: str) -> int:
    m = Chem.MolFromSmiles(s) if s else None
    return m.GetNumHeavyAtoms() if m is not None else 0


def load_rows() -> dict:
    rows = {}
    with open(TEST, encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            rxn = row.get("reactants>reagents>production") or ""
            parts = rxn.split(">")
            if len(parts) != 3:
                continue
            reactants = [strip_map(s) for s in parts[0].split(".") if s.strip()]
            products = [strip_map(s) for s in parts[2].split(".") if s.strip()]
            if not (1 <= len(reactants) <= 2) or not products:
                continue
            products.sort(key=heavy, reverse=True)
            rows[i] = {"reactants": reactants, "product": products[0]}
    return rows


def load_miss() -> set:
    out = set()
    with open(BASE, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if not d.get("hit"):
                out.add(d["i"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-support", type=int, default=2)
    ap.add_argument("--max-support", type=int, default=10 ** 9)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dump-flat", default="",
                    help="把「骨架对、精确立体不对」的案例写到这个 JSON")
    a = ap.parse_args()

    rows = load_rows()
    miss = sorted(load_miss())
    if a.limit:
        miss = miss[: a.limit]
    print("miss %d 条；模板 support %d-%d" % (len(miss), a.min_support, a.max_support))
    t0 = time.time()
    pool = RescuePool(path=TPL, min_support=a.min_support,
                      max_support=a.max_support, verbose=True)
    print("模板池 %d 条（%.0fs）" % (len(pool.tpls), time.time() - t0), flush=True)

    n_hit = n_flat = 0
    n_extra = 0
    hit_tpls = []
    flat_only = []
    t1 = time.time()
    for k, i in enumerate(miss):
        rec = rows.get(i)
        if not rec:
            continue
        mols = [Chem.MolFromSmiles(s) for s in rec["reactants"]]
        mols = [m for m in mols if m is not None]
        if not mols:
            continue
        jobs = [(m,) for m in mols]
        if len(mols) == 2:
            jobs.append((mols[0], mols[1]))
        got = []
        for job in jobs:
            got.extend(pool.run(list(job)))
        smis = {canon(x[0]) for x in got}
        want = canon(rec["product"])
        want_flat = canon(rec["product"], iso=False)
        flat = {canon(x[0], iso=False) for x in got}
        hit = bool(want and want in smis)
        if hit:
            n_hit += 1
            for smi, tpl, _sup in got:
                if canon(smi) == want:
                    hit_tpls.append((i, tpl))
                    break
        if want_flat and want_flat in flat:
            n_flat += 1
            if not hit and a.dump_flat:
                pick = next((x for x in got if canon(x[0], iso=False) == want_flat), None)
                if pick is not None:
                    flat_only.append({"i": i, "want": want, "got": canon(pick[0]),
                                      "template": pick[1], "support": pick[2]})
        n_extra += len(smis)
        if (k + 1) % 50 == 0:
            print("  ...%d/%d  hit=%d flat=%d  候选/反应=%.1f  %.0fs"
                  % (k + 1, len(miss), n_hit, n_flat, n_extra / (k + 1),
                     time.time() - t1), flush=True)
    n = len(miss)
    print("\n结论（support>=%d）：命中 %d/%d = %.1f%% · 去立体命中 %d/%d = %.1f%%"
          " · 新增候选/反应 %.1f · %.0fs"
          % (a.min_support, n_hit, n, 100.0 * n_hit / max(1, n),
             n_flat, n, 100.0 * n_flat / max(1, n), n_extra / max(1, n),
             time.time() - t1))
    if hit_tpls:
        out = ROOT / "reports" / ("probe_train_cover_s%d_hits.json" % a.min_support)
        out.write_text(json.dumps(hit_tpls, ensure_ascii=False, indent=1), encoding="utf-8")
        print("命中模板 ->", out)
    if a.dump_flat:
        out = Path(a.dump_flat)
        out.write_text(json.dumps(flat_only, ensure_ascii=False, indent=1), encoding="utf-8")
        print("flat-only 案例 %d -> %s" % (len(flat_only), out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
