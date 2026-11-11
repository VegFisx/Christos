# -*- coding: utf-8 -*-
"""条件包络的区分度：真产物 vs 同批候选，fit 能不能把它们分开？

为什么要这个：包络（模板级）此前测过 AUC 0.488，等于抛硬币。
第 145 轮改成「反应中心类型级」后覆盖率从 1.7% 抬到 32.5%，
必须重测一次区分度——否则这列只是「看起来有信息」。

口径：
  * 数据：reports/ord_condition_dataset/*.parquet，只取同时有温度与时长、
    且反应物/产物都带原子映射的记录；每条用自己的真实条件跑引擎（不套煎煮）。
  * 标签：候选是否等于该记录的产物（规范化 SMILES 比较，抹映射、去氢）。
  * 指标：sklearn roc_auc_score（fit 越大越可能是真产物）；同时报覆盖率、
    真/假两侧 fit 的中位数。
  * 只有「两边都有观测」的样本参与 AUC；全无观测的样本信息量为 0。

用法：python _diag\probe_envelope_auc.py [样本数]
"""
import glob
import json
import os
import sys
from statistics import median

import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.dirname(HERE)
for sub in ("core", "conditions", "rules", "libs", "tools", "sources"):
    p = os.path.join(STAGE, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from rdkit import Chem, RDLogger                       # noqa: E402

RDLogger.DisableLog("rdApp.*")

DATA = os.path.join(STAGE, "reports", "ord_condition_dataset")


def canon(smi):
    if not smi:
        return ""
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return ""
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    try:
        Chem.SanitizeMol(m)
    except Exception:                                  # noqa: BLE001
        return ""
    return Chem.MolToSmiles(m)


def strip_map(smi):
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    try:
        Chem.SanitizeMol(m)
    except Exception:                                  # noqa: BLE001
        return None
    return Chem.MolToSmiles(m)


def load_rows(want):
    rows = []
    for path in sorted(glob.glob(os.path.join(DATA, "*.parquet"))):
        t = pq.read_table(path, columns=["reactants", "product", "temperature_C",
                                         "reaction_time_min"])
        cols = {k: t.column(k).to_pylist() for k in t.schema.names}
        for i in range(len(cols["reactants"])):
            r, p = cols["reactants"][i], cols["product"][i]
            tt, tm = cols["temperature_C"][i], cols["reaction_time_min"][i]
            if not r or not p or tt is None or tm is None:
                continue
            if ":" not in r or ":" not in p:
                continue
            rows.append({"r": r, "p": p, "T": float(tt), "tm": float(tm)})
            if len(rows) >= want:
                return rows
    return rows


def main():
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    rows = load_rows(want)
    print("样本 %d 条（都有自己的温度/时长）" % len(rows))

    from engine import Compound                            # noqa: E402
    from smartreact_engine import SmartReactEngine         # noqa: E402
    import templates as T                                  # noqa: E402
    from dataclasses import replace

    eng = SmartReactEngine()
    base = T.get_template("煎煮")

    ys, fits, cov, err = [], [], 0, 0
    n_cand = 0
    for row in rows:
        parts = [strip_map(s) for s in row["r"].split(".") if ":" in s]
        parts = [s for s in parts if s]
        want_p = canon(row["p"])
        if not parts or not want_p:
            err += 1
            continue
        cond = replace(base, temperature=row["T"], time_min=row["tm"])
        comps = [Compound(smiles=s, name="R%d" % j, herb="(probe)")
                 for j, s in enumerate(parts)]
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception:                                  # noqa: BLE001
            err += 1
            continue
        seen = set()
        for p in prods:
            smi = canon(getattr(p, "smiles", ""))
            if not smi or smi in seen:
                continue
            seen.add(smi)
            fit = float(getattr(p, "condition_fit", 1.0) or 1.0)
            why = str(getattr(p, "condition_fit_why", "") or "")
            if "无足够观测" not in why and "无模板" not in why:
                cov += 1
            n_cand += 1
            ys.append(1 if smi == want_p else 0)
            fits.append(fit)

    print("候选 %d 个（真产物 %d），命中覆盖 %d 个候选（%.1f%%），异常 %d 条"
          % (n_cand, sum(ys), cov, 100.0 * cov / max(1, n_cand), err))
    if not fits:
        return 2
    try:
        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score(ys, fits)
    except Exception as exc:                                # noqa: BLE001
        print("AUC 计算失败：%s" % exc)
        return 2
    pos = [f for f, y in zip(fits, ys) if y == 1]
    neg = [f for f, y in zip(fits, ys) if y == 0]
    print("AUC = %.3f" % auc)
    print("真产物 fit 中位 %.3f（n=%d），假候选 中位 %.3f（n=%d）"
          % (median(pos) if pos else -1, len(pos),
             median(neg) if neg else -1, len(neg)))
    out = os.path.join(STAGE, "reports", "envelope_auc_type_20261111.json")
    json.dump({"rows": len(rows), "candidates": n_cand, "positives": len(pos),
               "auc": auc, "median_fit_pos": median(pos) if pos else None,
               "median_fit_neg": median(neg) if neg else None,
               "coverage_candidates": cov},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("写出：%s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
