#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""候选缓存：把所有候选（含打分要用的字段）dump 成 JSONL，之后排序实验不再重跑引擎。

一条记录：
  {"want": 真产物规范 SMILES, "cands": [{"smi","rule","act","tpl","sup","eng"}...]}

用法：
    python -I tools\\collect_candidates.py --n 3000 --out reports/cand_cache_3000.jsonl
"""
from __future__ import annotations

import argparse
import ast
import json
import random
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TESTSET = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
MINED = ROOT / "reports" / "mined_forward_templates_full_s5.jsonl"


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def load_support() -> dict:
    sup = {}
    with MINED.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            t = d.get("template") or ""
            if t:
                sup[t] = int(d.get("support") or 0)
    return sup


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--out", default=str(ROOT / "reports" / "cand_cache.jsonl"))
    a = ap.parse_args()

    import smartreact_engine as SE
    import templates as T
    from engine import Compound

    sup = load_support()
    print("support 表 %d 条" % len(sup))

    # ★ 第 97 轮：把 extent 与「curated 规则族」也一并缓存，排序实验才有得比。
    import extent as _extent
    _ext_params = _extent.load_params()
    _ext_cache = {}
    _curated_ids = set()
    try:
        _rj = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))
        _curated_ids = {r.get("id") for r in (_rj.get("rules") or []) if r.get("id")}
    except Exception as _ex:                     # noqa: BLE001 —— 打印，不静默
        print("  [warn] rules.json 读不了，curated 标记全为 0：%s" % _ex)
    print("curated 规则 id %d 条" % len(_curated_ids))

    rows = [json.loads(l) for l in TESTSET.open(encoding="utf-8")]
    random.Random(a.seed).shuffle(rows)

    eng = SE.SmartReactEngine()
    cond = T.get_template("煎煮")
    t0 = time.time()
    n_written = 0
    with open(a.out, "w", encoding="utf-8") as fo:
        for d in rows[: a.n]:
            rl = ast.literal_eval(d["reactants"]) if isinstance(d["reactants"], str) else d["reactants"]
            comps = [Compound(smiles=s, name="R%d" % i, herb="(bench)")
                     for i, s in enumerate(rl[:2]) if Chem.MolFromSmiles(s)]
            if not comps:
                continue
            want = canon(d.get("product") or "")
            if not want:
                continue
            try:
                prods = eng.step(comps, cond, round_no=1)
            except Exception:
                continue
            cands = []
            for p in prods:
                cs = canon(getattr(p, "smiles", "") or "")
                if not cs:
                    continue
                tpl = getattr(p, "template_smarts", "") or ""
                rid = getattr(p, "rule_id", "") or ""
                # extent：按反应名缓存（与 step 的 ext_cache 同源同表）
                _per = _ext_cache.get(rid)
                if _per is None:
                    _entry = (getattr(eng, "cond_table", {}).get(rid)
                              or getattr(eng, "curated_cond_table", {}).get(rid)
                              or getattr(eng, "mined_top_cond_table", {}).get(rid))
                    try:
                        _per = _extent.extent_from_table(_entry, cond, _ext_params)
                    except Exception as _ex:        # noqa: BLE001
                        _per = (1.0, "extent 计算失败：%s" % type(_ex).__name__)
                    _ext_cache[rid] = _per
                cands.append({
                    "smi": cs,
                    "rule": rid,
                    "act": round(float(getattr(p, "activation", 0.0) or 0.0), 4),
                    "tpl": tpl[:400],
                    "sup": int(sup.get(tpl, 0)),
                    "eng": round(float(getattr(p, "score", 0.0) or 0.0), 4),
                    "ext": round(float(_per[0]), 4),
                    "cur": 1 if rid in _curated_ids else 0,
                    "src": (getattr(p, "source_smiles", "") or "")[:200],
                })
            if not cands:
                continue
            fo.write(json.dumps({"want": want, "cands": cands}, ensure_ascii=False) + "\n")
            n_written += 1
    print("写出 %d 条 / %s（%.1f s）" % (n_written, a.out, time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
