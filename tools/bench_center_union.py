"""模板候选 ∪ 学习型单解：这两条路是「二选一」还是「该并联」。

问题（第 146 轮留下的）：
    模板引擎在同一批全映射 ORD 反应上 recall 50.8% / top-1 3.4%；
    学习型反应中心（约束解码）一次命中 32.1%。
    但这两个数字各测各的，没人知道它们**是不是覆盖同一批反应**。

判据（先写死，跑完不许改）：
    A. 学习型命中的那部分里，落在模板候选集合内的比例 < 70%
       → 两条路互补，并联有意义（合并覆盖应明显高于 50.8%）。
    B. 如果 >= 90% 都落在候选内
       → 并联无增益，学习型只能当「排序器」用。

口径：
    - 样本：`reports/center_dataset_mapped.jsonl` 前 20,000 条的测试半区（rid 哈希为奇数），
      与 `tools/train_center_model.py`、`tools/bench_center_vs_template.py` 同一函数。
    - 学习型：同一超参训练（HistGBM 五分类），解码用第 146 轮 §7 的约束解码
      （价态容量按置信度降序接受）。
    - 模板：`SmartReactEngine` 默认池，条件「煎煮」，产物比较用同一 canon_set。

用法：
    python tools/bench_center_union.py 500
"""

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_HERE = Path(__file__).resolve().parent
STAGE = _HERE.parent
for _p in (STAGE, STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs", _HERE):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DATA = STAGE / "reports" / (os.environ.get("CENTER_DATASET") or "center_dataset_mapped.jsonl")
LABELS = {0: "不变", 1: "成键", 2: "断键", 3: "升键", 4: "降键"}


def _h(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500

    import numpy as np
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    from sklearn.ensemble import HistGradientBoostingClassifier

    from train_center_model import _atom_budget, _old_orders, canon_set, _to_order_cls
    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    rows = []
    with open(DATA, encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
            if len(rows) >= 20000:
                break
    tr = [r for r in rows if _h(r["rid"]) % 2 == 0]
    te = [r for r in rows if _h(r["rid"]) % 2 == 1][:n]
    print(f"训练 {len(tr)} 条 / 测试 {len(te)} 条（前 20,000 条内按 rid 哈希切分）")

    Xtr = np.asarray([x for r in tr for x in r["X"]], dtype="float32")
    ytr = np.asarray([int(v) for r in tr for v in r["y"]], dtype="int32")
    cnt = Counter(ytr.tolist())
    w = np.array([len(ytr) / (len(cnt) * cnt[int(t)]) for t in ytr], dtype="float32")
    clf = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_leaf_nodes=63,
        min_samples_leaf=40, l2_regularization=1.0, random_state=20261111)
    clf.fit(Xtr, ytr, sample_weight=w)

    Xte = np.asarray([x for r in te for x in r["X"]], dtype="float32")
    proba = clf.predict_proba(Xte)

    eng = SmartReactEngine()
    cond = T.get_template("煎煮")

    n_tpl = n_learn = n_union = n_both = n_learn_outside = 0
    n_valid = 0
    idx = 0
    for r in te:
        k = len(r["y"])
        # —— 学习型：约束解码 ——
        budget = _atom_budget(r["smiles_r"])
        cur = {mp: b[0] for mp, b in budget.items()}
        cap = {mp: b[1] for mp, b in budget.items()}
        old_ord = _old_orders(r["smiles_r"])
        cand = []
        for j, (a, b) in enumerate(r["pair_idx"]):
            p = proba[idx + j]
            for cls in (1, 2, 3, 4):
                if p[cls] > 0.5:
                    cand.append((float(p[cls]), int(a), int(b), cls))
        idx += k
        cand.sort(reverse=True)
        accepted, seen = [], set()
        for _p, a, b, cls in cand:
            key = (min(a, b), max(a, b))
            if key in seen:
                continue
            base = old_ord.get(key, 1.0)
            tgt = _to_order_cls(cls, base)
            d = tgt - base
            if d > 0 and (cur.get(a, 0) + d > cap.get(a, 0) + 1e-9
                          or cur.get(b, 0) + d > cap.get(b, 0) + 1e-9):
                continue
            cur[a] = cur.get(a, 0) + d
            cur[b] = cur.get(b, 0) + d
            seen.add(key)
            accepted.append((a, b, tgt))
        from core.center_apply import apply_edits
        learned = apply_edits(r["smiles_r"], accepted) if accepted else None
        if learned:
            n_valid += 1

        # —— 模板 ——
        parts = [s for s in r["smiles_r"].split(".") if s]
        comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)") for j, s in enumerate(parts)]
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception:
            prods = []
        got = sorted({canon_set(getattr(p, "smiles", "")) for p in prods} - {""})
        want = canon_set(r["smiles_p"])
        if not want:
            continue

        tpl_hit = want in got
        learn_hit = bool(learned) and learned == want
        if tpl_hit:
            n_tpl += 1
        if learn_hit:
            n_learn += 1
            if tpl_hit:
                n_both += 1
            else:
                n_learn_outside += 1
        if tpl_hit or learn_hit:
            n_union += 1

    total = max(1, len(te))
    print(f"模板命中          {n_tpl}/{total} = {100.0*n_tpl/total:.1f}%")
    print(f"学习型命中        {n_learn}/{total} = {100.0*n_learn/total:.1f}%"
          f"（其中输出结构合法 {n_valid}/{total}）")
    print(f"两者都命中        {n_both}/{total} = {100.0*n_both/total:.1f}%")
    print(f"只有学习型命中    {n_learn_outside}/{total} = {100.0*n_learn_outside/total:.1f}%")
    print(f"合并覆盖          {n_union}/{total} = {100.0*n_union/total:.1f}%")
    if n_learn:
        inside = 100.0 * n_both / n_learn
        print(f"学习型命中落在模板候选内的比例 = {inside:.1f}%（判据 A 阈值 <70% 才算互补）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
