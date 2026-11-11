#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""为「学习型排序器」构建数据集：每个候选一行，带标签与特征。

一行 =
  {"rid": 反应在测试集里的行号, "split": "train"|"test",
   "want": 真产物规范 SMILES, "rank": 候选发射序号, "label": 0/1,
   "smi": 候选规范 SMILES, "rule": rule_id, "act": float, "sup": int,
   "eng": float, "ext": float, "cur": 0/1,
   "prod_ha": 候选重原子数, "src_ha": 底物重原子数, "keep": 重原子保留率,
   "byp": 0/1}

用法：
    python -I tools\\build_rank_dataset.py --n 12000 --out reports/rank_dataset_20261107.jsonl
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
from rdkit.Chem import Descriptors  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TESTSET = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
MINED = ROOT / "reports" / "mined_forward_templates_full_s5.jsonl"


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def ha(s: str) -> int:
    m = Chem.MolFromSmiles(s) if s else None
    return m.GetNumHeavyAtoms() if m is not None else 0


def load_support() -> dict:
    sup = {}
    with MINED.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            t = d.get("template") or ""
            if t:
                sup[t] = int(d.get("support") or 0)
    return sup


def split_of(seed: int, key: str) -> str:
    import hashlib
    h = hashlib.md5((str(seed) + "|" + key).encode("utf-8")).hexdigest()
    return "train" if int(h[:8], 16) % 2 == 0 else "test"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12000)
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--out", default=str(ROOT / "reports" / "rank_dataset.jsonl"))
    a = ap.parse_args()

    import smartreact_engine as SE
    import templates as T
    from engine import Compound
    import extent as _extent

    sup = load_support()
    _ext_params = _extent.load_params()
    _ext_cache = {}
    _curated_ids = set()
    try:
        _rj = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))
        _curated_ids = {r.get("id") for r in (_rj.get("rules") or []) if r.get("id")}
    except Exception as _ex:                     # noqa: BLE001
        print("  [warn] rules.json 读不了：%s" % _ex)

    rows = [json.loads(l) for l in TESTSET.open(encoding="utf-8")]
    random.Random(a.seed).shuffle(rows)

    eng = SE.SmartReactEngine()
    cond = T.get_template("煎煮")
    t0 = time.time()
    n_rxn = 0
    n_cand = 0
    n_hit = 0
    skipped = 0
    with open(a.out, "w", encoding="utf-8") as fo:
        for d in rows[: a.n]:
            rl = ast.literal_eval(d["reactants"]) if isinstance(d["reactants"], str) else d["reactants"]
            comps = [Compound(smiles=s, name="R%d" % i, herb="(bench)")
                     for i, s in enumerate(rl[:2]) if Chem.MolFromSmiles(s)]
            if not comps:
                skipped += 1
                continue
            want = canon(d.get("product") or "")
            if not want:
                skipped += 1
                continue
            try:
                prods = eng.step(comps, cond, round_no=1)
            except Exception:
                skipped += 1
                continue
            src_ha = sum(ha(c.smiles) for c in comps)
            rid_key = want
            sp = split_of(a.seed, rid_key)
            rank = 0
            hit = False
            for p in prods:
                cs = canon(getattr(p, "smiles", "") or "")
                if not cs:
                    continue
                tpl = getattr(p, "template_smarts", "") or ""
                rule = getattr(p, "rule_id", "") or ""
                _per = _ext_cache.get(rule)
                if _per is None:
                    _entry = (getattr(eng, "cond_table", {}).get(rule)
                              or getattr(eng, "curated_cond_table", {}).get(rule)
                              or getattr(eng, "mined_top_cond_table", {}).get(rule))
                    try:
                        _per = _extent.extent_from_table(_entry, cond, _ext_params)
                    except Exception:
                        _per = (1.0, "")
                    _ext_cache[rule] = _per
                pha = ha(cs)
                # 底物重原子数按候选自己的来源算：单底物反应=该底物；
                # 双底物反应=两个底物之和（生产侧用 source_smiles + partner_smiles 复算，口径一致）
                _src_smi = getattr(p, "source_smiles", "") or ""
                _par_smi = getattr(p, "partner_smiles", "") or ""
                shr = ha(_src_smi) if _src_smi else 0
                if _par_smi:
                    shr += ha(_par_smi)
                src_ha_c = shr or src_ha
                rec = {
                    "rid": n_rxn,
                    "split": sp,
                    "want": want,
                    "rank": rank,
                    "label": 1 if cs == want else 0,
                    "smi": cs,
                    "rule": rule,
                    "act": round(float(getattr(p, "activation", 0.0) or 0.0), 4),
                    "sup": int(sup.get(tpl, 0)),
                    "eng": round(float(getattr(p, "score", 0.0) or 0.0), 4),
                    "ext": round(float(_per[0]), 4),
                    "cur": 1 if rule in _curated_ids else 0,
                    "prod_ha": pha,
                    "src_ha": src_ha_c,
                    "keep": round(pha / src_ha_c, 4) if src_ha_c else 0.0,
                    "byp": 1 if getattr(p, "is_byproduct", False) else 0,
                    # v2：把产物侧与底物侧原样留下，训练时可以现算产物级特征
                    "sub": (getattr(p, "source_smiles", "") or "")
                           + (("." + getattr(p, "partner_smiles", "")) if getattr(p, "partner_smiles", "") else ""),
                    "tpl": tpl,
                }
                fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_cand += 1
                hit = hit or rec["label"] == 1
                rank += 1
            n_rxn += 1
            n_hit += 1 if hit else 0
            if n_rxn % 1000 == 0:
                print("  ...%d 反应 / %.0f s / 命中 %d" % (n_rxn, time.time() - t0, n_hit), flush=True)
    print("完成：%d 反应（跳过 %d）/ %d 候选 / 发射序命中 %d（%.2f%%）/ 耗时 %.1f s"
          % (n_rxn, skipped, n_cand, n_hit, 100.0 * n_hit / max(1, n_rxn), time.time() - t0))
    print("写出 %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
