# -*- coding: utf-8 -*-
r"""重建候选排序数据集 —— 这次每条记录带**它自己的条件**。

数据：reports/ord_condition_dataset/*.parquet（reactants/product 带映射，含温度/时长/溶剂/催化剂）
做法：把映射抹掉 → 用该记录自己的条件跑引擎 → 每个候选记 9 个原有特征 + 3 个条件特征。

输出：reports/rank_dataset_cond.jsonl

用法: python tools\build_rank_dataset_cond.py [n=4000] [shift=0]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
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

ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for p in (str(ROOT / "libs"), str(ROOT), str(ROOT / "core"),
          str(ROOT / "conditions"), str(ROOT / "sources")):
    if p not in sys.path:
        sys.path.insert(0, p)

from rdkit import Chem, RDLogger  # noqa: E402
RDLogger.DisableLog("rdApp.*")

MINED = ROOT / "reports" / "mined_forward_templates_full_s5.jsonl"

_SOLV = [("water", "water"), ("h2o", "water"), ("ethanol", "ethanol"),
         ("methanol", "methanol"), ("dmso", "dmso"), ("dmf", "dmf"),
         ("toluene", "toluene"), ("dioxane", "dioxane"), ("thf", "thf"),
         ("acetonitrile", "mecn"), ("acetone", "acetone"), ("dcm", "dcm"),
         ("chloroform", "chcl3"), ("isopropanol", "isopropanol"),
         ("ethyl acetate", "etoac"), ("hexane", "hexane"),
         ("pyridine", "pyridine"), ("benzene", "benzene")]


def norm_solvent(name) -> str:
    low = str(name or "").lower()
    if low in ("nan", "none", ""):
        return "water"
    for key, ours in _SOLV:
        if key in low:
            return ours
    return "water"


def strip_maps(smi: str) -> str:
    m = Chem.MolFromSmiles(smi) if smi else None
    if m is None:
        return ""
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m)


def ha(smi: str) -> int:
    m = Chem.MolFromSmiles(smi) if smi else None
    return m.GetNumHeavyAtoms() if m is not None else 0


def split_of(seed: int, key: str) -> str:
    h = hashlib.md5((str(seed) + "|" + key).encode("utf-8")).hexdigest()
    return "train" if int(h[:8], 16) % 2 == 0 else "test"


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
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=20261111)
    ap.add_argument("--files", type=int, default=40)
    ap.add_argument("--out", default=str(ROOT / "reports" / "rank_dataset_cond.jsonl"))
    a = ap.parse_args()

    import pyarrow.parquet as pq
    import smartreact_engine as SE
    import templates as T
    from engine import Compound
    import extent as _extent

    sup = load_support()
    _ext_params = _extent.load_params()
    try:
        _rj = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))
        _curated_ids = {r.get("id") for r in (_rj.get("rules") or []) if r.get("id")}
    except Exception:                             # noqa: BLE001
        _curated_ids = set()

    files = sorted(glob.glob(str(ROOT / "reports" / "ord_condition_dataset" / "*.parquet")))
    random.Random(a.seed).shuffle(files)
    files = files[:a.files]

    recs = []
    for p in files:
        df = pq.ParquetFile(p).read(columns=[
            "reactants", "product", "product_smiles", "temperature_C",
            "reaction_time_min", "solvent_names", "catalyst_names"]).to_pandas()
        for r in df.to_dict("records"):
            if r.get("temperature_C") is None or r.get("reaction_time_min") is None:
                continue
            recs.append(r)
        if len(recs) >= a.n * 3:
            break
    random.Random(a.seed).shuffle(recs)
    print(f"候选记录池 {len(recs)}，目标 {a.n}", flush=True)

    eng = SE.SmartReactEngine()
    n_rxn = n_cand = n_hit = 0
    t0 = time.time()
    with open(a.out, "w", encoding="utf-8") as fo:
        for d in recs:
            if n_rxn >= a.n:
                break
            rs = [strip_maps(s) for s in str(d.get("reactants") or "").split(".")]
            rs = [s for s in rs if s]
            if not rs:
                continue
            want = strip_maps(str(d.get("product") or ""))
            if not want:
                continue
            cond = T.get_template("自定义")
            cond = cond.__class__(
                solvent=norm_solvent(d.get("solvent_names")),
                temperature=float(d["temperature_C"]),
                time_min=float(d["reaction_time_min"]),
                pH=7.0,
                catalyst=(str(d.get("catalyst_names"))
                          if d.get("catalyst_names") else ""),
                atmosphere="air")
            comps = [Compound(smiles=s, name="R%d" % i, herb="(rank)")
                     for i, s in enumerate(rs[:2]) if Chem.MolFromSmiles(s)]
            if not comps:
                continue
            try:
                prods = eng.step(comps, cond, round_no=1)
            except Exception:                     # noqa: BLE001
                continue
            src_ha = sum(ha(c.smiles) for c in comps)
            sp = split_of(a.seed, want)
            rank = 0
            hit = False
            for p in prods:
                smi = getattr(p, "smiles", "") or ""
                if not smi:
                    continue
                tpl = getattr(p, "template_smarts", "") or ""
                rule = getattr(p, "rule_id", "") or ""
                _entry = (getattr(eng, "cond_table", {}).get(rule)
                          or getattr(eng, "curated_cond_table", {}).get(rule)
                          or getattr(eng, "mined_top_cond_table", {}).get(rule))
                try:
                    per = _extent.extent_from_table(_entry, cond, _ext_params)
                except Exception:                 # noqa: BLE001
                    per = (1.0, "")
                pha = ha(smi)
                _src = getattr(p, "source_smiles", "") or ""
                _par = getattr(p, "partner_smiles", "") or ""
                shr = (ha(_src) if _src else 0) + (ha(_par) if _par else 0)
                src_c = shr or src_ha
                rec = {
                    "rid": n_rxn, "split": sp, "want": want, "rank": rank,
                    "label": 1 if smi == want else 0, "smi": smi, "rule": rule,
                    "act": round(float(getattr(p, "activation", 0.0) or 0.0), 4),
                    "sup": int(sup.get(tpl, 0)),
                    "ext": round(float(per[0]), 4),
                    "cur": 1 if rule in _curated_ids else 0,
                    "prod_ha": pha, "src_ha": src_c,
                    "keep": round(pha / src_c, 4) if src_c else 0.0,
                    "byp": 1 if getattr(p, "is_byproduct", False) else 0,
                    # ---- 条件特征（本次新增）----
                    "t_C": round(float(cond.temperature), 1),
                    "log_time": round(__import__("math").log10(
                        max(0.1, float(cond.time_min))), 3),
                    "fit": round(float(getattr(p, "condition_fit", 1.0) or 1.0), 4),
                    "is_water": 1 if cond.solvent == "water" else 0,
                    "has_cat": 1 if getattr(cond, "catalyst", "") else 0,
                }
                fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_cand += 1
                hit = hit or rec["label"] == 1
                rank += 1
            n_rxn += 1
            n_hit += 1 if hit else 0
            if n_rxn % 200 == 0:
                print(f"  {n_rxn} 反应 / {n_cand} 候选 / 命中 {n_hit} "
                      f"({time.time() - t0:.0f}s)", flush=True)

    print(f"完成：反应 {n_rxn} · 候选 {n_cand} · 含正确产物 {n_hit} "
          f"({n_hit / max(1, n_rxn):.1%}) · {time.time() - t0:.0f}s → {a.out}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
