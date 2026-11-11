# -*- coding: utf-8 -*-
r"""学习型反应中心：训练 + 三项评估。

数据：reports/center_dataset.jsonl（tools/build_center_dataset.py 产出，
      每行一个反应，候选原子上、y ∈ {0 不变, 1 成键, 2 断键, 3 键级升, 4 键级降}）。

模型：HistGradientBoosting 多分类（CPU、分钟级）。特征全是原子对局部环境，
      不使用模板、不使用映射号 —— 化学之外的东西一概不给。

三项评估（按反应哈希对半切）：
  1. 键级变化 P/R（逐对，按类）
  2. **反应中心完全命中率**：预测的非零编辑集合 == 真实集合
  3. **产物完全命中率**：把预测编辑施加到反应物后，产物（含碎片）与记录一致

第 3 项是这条路线的终点：如果中心能预测对，产物就是确定性的。
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE))
sys.path.insert(0, str(STAGE / "libs"))

import numpy as np  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402

RDLogger.DisableLog("rdApp.*")

from core.center_apply import apply_edits  # noqa: E402
from core.center_apply2 import apply_edits2 as _apply2  # noqa: E402


def _wl(smiles_p):
    """产物侧出现的映射号：施加前按它剥掉反应物里的试剂残渣。"""
    m = Chem.MolFromSmiles(smiles_p)
    if m is None:
        return None
    return {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum()}


def _apply(smiles_r, edits, smiles_p):
    return _apply2(smiles_r, edits, maps_whitelist=_wl(smiles_p))

DATA = STAGE / "reports" / (os.environ.get("CENTER_DATASET") or "center_dataset.jsonl")
LABELS = {0: "不变", 1: "成键", 2: "断键", 3: "升键", 4: "降键"}
NEG_RATIO_TRAIN = 8


def _h(s: str) -> int:
    import hashlib
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


def load():
    rows = []
    with open(DATA, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _old_orders(smi: str) -> dict:
    """反应物里「按映射号索引」的键级表，用来把「升/降键」翻译成具体目标键级。"""
    from core.center_apply import _bond_order
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return {}
    out = {}
    for b in m.GetBonds():
        m1 = b.GetBeginAtom().GetAtomMapNum()
        m2 = b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            out[(min(m1, m2), max(m1, m2))] = _bond_order(b)
    return out


_PT = Chem.GetPeriodicTable()


def _atom_budget(smi: str) -> dict:
    """每个映射原子还剩多少「价态容量」：max_allowed - current。

    约束解码只接受「不把任何原子顶爆」的编辑，这一步在施加之前做，
    而不是等 sanitize 报错再丢掉（第 146 轮实测 37% 的预测编辑是这样废掉的）。
    """
    from core.center_apply import _bond_order
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return {}
    out = {}
    for a in m.GetAtoms():
        mp = a.GetAtomMapNum()
        if not mp:
            continue
        cur = sum(_bond_order(b) for b in a.GetBonds()) + a.GetNumExplicitHs()
        try:
            base = max(_PT.GetValenceList(a.GetAtomicNum()))
        except Exception:
            base = 4
        out[mp] = [float(cur), float(base + a.GetFormalCharge())]
    return out


def _to_order_cls(cls: int, base: float) -> float:
    """把「成/断/升/降」翻译成具体目标键级；升/降按现有键级推一步。"""
    if cls == 1:
        return max(base, 1.0) if base > 0 else 1.0
    if cls == 2:
        return 0.0
    if cls == 3:
        return min(3.0, base + 1.0)
    return max(1.0, base - 1.0)


def canon_set(smi: str) -> str:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return ""
    # ★ 必做：产物侧带原子映射号，比较前必须抹掉，否则永远不可能相等
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    frags = Chem.GetMolFrags(m, asMols=True, sanitizeFrags=False)
    outs = []
    for p in frags:
        try:
            Chem.SanitizeMol(p)
            outs.append(Chem.MolToSmiles(p))
        except Exception:
            return ""
    return ".".join(sorted(outs))


def main() -> int:
    n_limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    rows = load()[:n_limit]
    if not rows:
        print("没有数据")
        return 1
    tr = [r for r in rows if _h(r["rid"]) % 2 == 0]
    te = [r for r in rows if _h(r["rid"]) % 2 == 1]
    print(f"反应 训练 {len(tr)} / 测试 {len(te)}")

    def stack(rs):
        X, y = [], []
        for r in rs:
            X.extend(r["X"])
            y.extend(r["y"])
        return np.asarray(X, dtype="float32"), np.asarray(y, dtype="int8")

    Xtr, ytr = stack(tr)
    Xte, yte = stack(te)
    print(f"候选对 训练 {len(ytr)} / 测试 {len(yte)} · 训练标签 "
          f"{ {LABELS[k]: v for k, v in Counter(ytr.tolist()).items()} }")

    # 类不平衡：按逆频率加权（不变类占 ~90%）
    cnt = Counter(ytr.tolist())
    w = np.array([len(ytr) / (len(cnt) * cnt[int(t)]) for t in ytr], dtype="float32")
    clf = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_leaf_nodes=63,
        min_samples_leaf=40, l2_regularization=1.0, random_state=20261111)
    # HistGBM 不支持 sample_weight？它支持 —— 用 class_weight 的等价做法
    clf.fit(Xtr, ytr, sample_weight=w)
    import pickle
    out_pkl = STAGE / "reports" / (os.environ.get("CENTER_MODEL_OUT") or "center_model.pkl")
    with open(out_pkl, "wb") as fh:
        pickle.dump(clf, fh)
    print(f"模型已存 {out_pkl}")
    pred = clf.predict(Xte)
    print("\n== 逐对键级变化（测试集）==")
    for cls in sorted(LABELS):
        tp = int(np.sum((pred == cls) & (yte == cls)))
        fp = int(np.sum((pred == cls) & (yte != cls)))
        fn = int(np.sum((pred != cls) & (yte == cls)))
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        print(f"  {LABELS[cls]:<3} P {p:5.1%}  R {r:5.1%}  (真 {tp + fn})")

    # 按反应聚合
    probea_all = clf.predict_proba(np.asarray([x for r in te for x in r["X"]], dtype="float32"))
    ptr = clf.predict(np.asarray([x for r in te for x in r["X"]], dtype="float32"))
    i = 0
    pi = 0
    center_hit = exact_hit = invalid = 0
    c_exact = c_invalid = c_center = 0
    n = 0
    for r in te:
        k = len(r["y"])
        yp = ptr[i:i + k]
        i += k
        pairs = r["pair_idx"]
        true_edits = {(int(a), int(b)): float(v) for (a, b), v in zip(pairs, r["y"]) if v}
        pred_edits = {(int(a), int(b)): float(v) for (a, b), v in zip(pairs, yp) if v}
        # 预测里「目标键级」：0=断；1/2/3/4 -> 2/0/2/1 需要按真实目标推断，
        # 这里只用类别语义：成键=1，断键=0，升键=双键，降键=单键
        old_ord = _old_orders(r["smiles_r"])

        def to_order(cls, a, b):
            # 成键/断键由类别决定；升/降键要按反应物里该键现有的键级推一步，
            # 否则「1→2」和「2→3」会被混成同一个目标。
            base = old_ord.get((min(a, b), max(a, b)), 1.0)
            if cls == 1:
                return max(base, 1.0) if base > 0 else 1.0
            if cls == 2:
                return 0.0
            if cls == 3:
                return min(3.0, base + 1.0)
            return max(1.0, base - 1.0)

        pred_apply = [(a, b, to_order(int(c), a, b)) for (a, b), c in pred_edits.items()]
        true_apply = [(a, b, to_order(int(c), a, b)) for (a, b), c in true_edits.items()]
        if set(pred_edits) == set(true_edits):
            center_hit += 1
        got = _apply(r["smiles_r"], pred_apply, r["smiles_p"])
        want = canon_set(r["smiles_p"])
        if got and want and got == want:
            exact_hit += 1
        if got is None:
            invalid += 1

        # —— 约束解码：按置信度从高到低接受编辑，任何一步把原子价态顶爆就跳过 ——
        budget = _atom_budget(r["smiles_r"])
        cur = {mp: b[0] for mp, b in budget.items()}
        cap = {mp: b[1] for mp, b in budget.items()}
        cand = []
        for j, (a, b) in enumerate(pairs):
            probs = probea_all[pi + j]
            for cls in (1, 2, 3, 4):
                if probs[cls] > 0.5:
                    cand.append((float(probs[cls]), int(a), int(b), cls))
        cand.sort(reverse=True)
        accepted = []
        seen = set()
        for prob, a, b, cls in cand:
            key = (min(a, b), max(a, b))
            if key in seen:
                continue
            base = old_ord.get(key, 1.0)
            tgt = to_order(cls, a, b)
            delta = tgt - base
            if delta > 0:
                if cur.get(a, 0) + delta > cap.get(a, 0) + 1e-9:
                    continue
                if cur.get(b, 0) + delta > cap.get(b, 0) + 1e-9:
                    continue
            cur[a] = cur.get(a, 0) + delta
            cur[b] = cur.get(b, 0) + delta
            seen.add(key)
            accepted.append((a, b, tgt))
        c_got = _apply(r["smiles_r"], accepted, r["smiles_p"]) if accepted else None
        if c_got and want and c_got == want:
            c_exact += 1
        if c_got is None:
            c_invalid += 1
        if {(a, b) for a, b, _t in accepted} == set(true_edits):
            c_center += 1
        n += 1
        pi += k
    print("\n== 按反应 ==")
    print(f"  反应中心完全命中 {center_hit}/{n} = {center_hit / n:.1%}")
    print(f"  产物完全命中     {exact_hit}/{n} = {exact_hit / n:.1%}")
    print(f"  施加失败(无效结构) {invalid}/{n} = {invalid / n:.1%}")
    print("\n== 约束解码（价态容量校验后再接受编辑）==")
    print(f"  反应中心完全命中 {c_center}/{n} = {c_center / n:.1%}")
    print(f"  产物完全命中     {c_exact}/{n} = {c_exact / n:.1%}")
    print(f"  施加失败(无效结构) {c_invalid}/{n} = {c_invalid / n:.1%}")

    # 上界：用真实编辑施加上去，能不能还原记录产物？不能的话说明是「施加器」的锅，
    # 不是模型的锅 —— 这一条必须先跑，否则会把施加器的失败算到模型头上。
    upper = 0
    for r in te:
        old_ord = _old_orders(r["smiles_r"])
        true_apply = []
        for (a, b), c in zip(r["pair_idx"], r["y"]):
            c = int(c)
            if not c:
                continue
            a, b = int(a), int(b)
            base = old_ord.get((min(a, b), max(a, b)), 1.0)
            tgt = {1: max(base, 1.0), 2: 0.0, 3: min(3.0, base + 1.0), 4: max(1.0, base - 1.0)}[c]
            true_apply.append((a, b, tgt))
        got = _apply(r["smiles_r"], true_apply, r["smiles_p"])
        want = canon_set(r["smiles_p"])
        if got and want and got == want:
            upper += 1
    print(f"  上界（真实编辑能否还原）{upper}/{n} = {upper / n:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
