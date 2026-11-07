# -*- coding: utf-8 -*-
r"""D7（方案 a）标定：用**确定性判据**替代 R1 的限时 MCS。

背景（实测）：`rdFMCS.FindMCS(timeout=2)` 在天然产物尺寸上 94% 超时，结果随机器负载变；
所以先把"确定性粗判据"和 MCS 在**中小分子**上（MCS 可靠、不超时）做一致率标定。

数据：`reports/ord_dataset_sample_limit5000_seed20261013.parquet` 里的产物（12~30 重原子，真实药物化学分子）
-> 套 3,228 条逆模板 -> 得到一批 (目标, 前体集合) -> 逐个判 R1。

候选判据（都只读分子图，不做搜索）：
  A 重原子比: p_hac >= t_hac * r
  B 元素重叠比: Σ_元素 min(目标, 前体) / t_hac >= r   （注意：它是 MCS 的**上界**，召回高、精度低）
  C Morgan 指纹 Tanimoto >= r

用法: python tools/calib_r1_criterion.py [N_TARGETS] [N_TEMPLATES]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb                                                    # noqa: E402
from rdkit import Chem, RDLogger                                 # noqa: E402
from rdkit.Chem import rdFMCS, rdMolDescriptors, DataStructs     # noqa: E402
from rdkit.Chem import rdFingerprintGenerator, rdChemReactions    # noqa: E402
import retro_search as rs                                        # noqa: E402

RDLogger.DisableLog("rdApp.*")

PQ = STAGE / "reports" / "ord_dataset_sample_limit5000_seed20261013.parquet"
OUT = STAGE / "reports" / "r1_criterion_calibration.json"
FRAC = 0.80
GEN = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024)


def load_targets(n: int):
    con = duckdb.connect()
    rows = con.execute(
        "SELECT product_smiles FROM read_parquet('%s') WHERE product_smiles IS NOT NULL"
        % PQ.as_posix()).fetchall()
    out = []
    for (s,) in rows:
        m = Chem.MolFromSmiles(str(s).split(".")[0])
        if m is None:
            continue
        h = m.GetNumHeavyAtoms()
        if 12 <= h <= 30:
            out.append(Chem.MolToSmiles(m))
        if len(out) >= n:
            break
    return out


def main() -> int:
    n_t = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    n_tpl = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    targets = load_targets(n_t)
    tmpl = rs.load_rdchiral_templates()
    if n_tpl:
        tmpl = tmpl[:n_tpl]
    print("目标 %d 个（12~30 重原子）· 模板 %d 条" % (len(targets), len(tmpl)), flush=True)

    pairs = []          # (t_smi, p_smi, t_hac, p_hac)
    t0 = time.time()
    for tgt in targets:
        m = Chem.MolFromSmiles(tgt)
        th = m.GetNumHeavyAtoms()
        for t in tmpl:
            try:
                rx = rdChemReactions.ReactionFromSmarts(t.smarts)
            except Exception:
                continue
            try:
                outs = rx.RunReactants((m,))
            except Exception:
                continue
            for tup in outs:
                for p in tup:
                    if p is None:
                        continue
                    cs = rs.canon(Chem.MolToSmiles(p))
                    if not cs:
                        continue
                    ph = p.GetNumHeavyAtoms()
                    if th >= rs.USABILITY_MIN_TARGET_HAC and ph >= th - 2:
                        pairs.append((tgt, cs, th, ph))
    print("进入 MCS 支路的 (目标,前体) 对：%d（收集耗时 %.0fs）" % (len(pairs), time.time() - t0), flush=True)

    # ground truth = MCS（超时则丢弃，不参与标定）
    data, n_cancel = [], 0
    for (ts, ps, th, ph) in pairs:
        t = Chem.MolFromSmiles(ts)
        p = Chem.MolFromSmiles(ps)
        res = rdFMCS.FindMCS([t, p], timeout=5,
                             atomCompare=rdFMCS.AtomCompare.CompareElements,
                             bondCompare=rdFMCS.BondCompare.CompareOrder,
                             ringMatchesRingOnly=True, completeRingsOnly=True)
        if getattr(res, "canceled", False):
            n_cancel += 1
            continue
        gold = int(res.numAtoms) >= th * FRAC
        elem = rs._common_atom_upper_bound(rs._elem_counts(ts), rs._elem_counts(ps)) / float(th)
        fp_t = GEN.GetFingerprint(t)
        fp_p = GEN.GetFingerprint(p)
        tani = DataStructs.TanimotoSimilarity(fp_t, fp_p)
        data.append({"hac_ratio": ph / float(th), "elem_ratio": elem, "tanimoto": tani,
                     "gold": bool(gold)})
    print("可用样本 %d（MCS 超时丢弃 %d）" % (len(data), n_cancel), flush=True)

    def metrics(pred):
        tp = sum(1 for d, q in zip(data, pred) if q and d["gold"])
        fp = sum(1 for d, q in zip(data, pred) if q and not d["gold"])
        fn = sum(1 for d, q in zip(data, pred) if (not q) and d["gold"])
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {"tp": tp, "fp": fp, "fn": fn, "precision": round(prec, 4),
                "recall": round(rec, 4), "f1": round(f1, 4)}

    out = {"n_pairs_entered": len(pairs), "n_samples": len(data), "n_mcs_canceled": n_cancel,
           "gold_positive_rate": round(sum(1 for d in data if d["gold"]) / max(1, len(data)), 4),
           "gold": {"r1_frac": FRAC},
           "candidates": {}}
    for r in (0.8, 0.85, 0.9, 0.95):
        out["candidates"]["hac_ratio>=%.2f" % r] = metrics([d["hac_ratio"] >= r for d in data])
    for r in (0.8, 0.85, 0.9, 0.95):
        out["candidates"]["elem_ratio>=%.2f" % r] = metrics([d["elem_ratio"] >= r for d in data])
    for r in (0.7, 0.8, 0.9):
        out["candidates"]["tanimoto>=%.2f" % r] = metrics([d["tanimoto"] >= r for d in data])
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
