"""用中心模型给模板候选打分——第二版：不做图匹配，改用「模板自己声明的编辑」。

第一版（`tools/bench_learned_ranker.py`）失败的原因：
    候选产物 ↔ 反应物的原子对应关系靠反查子结构匹配，真实产物只有 67% 能匹配上，
    所以打分建立在错误对应上，top-1 反而掉到 0%。

这一版的前提（引擎已经具备的）：
    `core/smartreact_engine.py` 在发射产物时已经把命中的模板 SMARTS 记进
    `Product.template_smarts`（第 89 轮为立体判断加的）。模板 SMARTS 本身就写明了
    「左边哪些键、右边哪些键」——把它和底物做一次标准子结构匹配（模板左侧是具体
    SMARTS，匹配是可靠的），就能把模板里的映射号翻译成底物原子下标，不需要任何反查。

于是打分是：
    1. 模板左侧匹配到某个底物分子 → 映射号 → 原子下标；
    2. 比较模板左右两侧在「两个映射原子之间」的键级，得到真实编辑集；
    3. 用中心模型算每一步编辑类别的概率，取几何平均。

口径与 `bench_center_vs_template.py` 一致：默认池、条件「煎煮」、同一批测试反应。

用法：
    python tools/bench_learned_ranker2.py 150
"""

import json
import os
import sys
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
ORD = {1: 1.0, 2: 2.0, 3: 3.0, 1.5: 1.5}


from rdkit import Chem  # 模块级：smarts_edits() 在 main 之外用


def _bond_map(mol):
    """把分子里的键写成 {(map1,map2): order}，只收两端都有映射号的键。"""
    out = {}
    for b in mol.GetBonds():
        m1 = b.GetBeginAtom().GetAtomMapNum()
        m2 = b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            bt = b.GetBondType()
            out[(min(m1, m2), max(m1, m2))] = ORD.get(float(bt), 1.0)
    return out


def smarts_edits(smarts: str):
    """从模板 SMARTS 读出「左侧映射号之间的键」与「右侧同对原子的键」。"""
    if ">>" not in smarts:
        return None
    lhs, rhs = smarts.split(">>", 1)
    left = Chem.MolFromSmarts(lhs)
    right = Chem.MolFromSmarts(rhs)
    if left is None or right is None:
        return None
    return left, right, _bond_map(left), _bond_map(right)


def main() -> int:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    rows = []
    with open(DATA, encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
            if len(rows) >= 20000:
                break
    from train_center_model import _h as _h_rid, canon_set
    te = [r for r in rows if _h_rid(r["rid"]) % 2 == 1][:n]

    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    eng = SmartReactEngine()
    cond = T.get_template("煎煮")

    from build_center_dataset import _atom_feat, _nbr_feat, _ord
    from rdkit.Chem import rdmolops

    # 中心模型：直接用训练好的模型（如果存在），否则跳过打分只报 recall
    model_path = STAGE / "reports" / "center_model.pkl"
    clf = None
    if model_path.exists():
        import pickle
        with open(model_path, "rb") as fh:
            clf = pickle.load(fh)

    def feats_for(R, i, j, comp_of, dm):
        a, b = R.GetAtomWithIdx(i), R.GetAtomWithIdx(j)
        fi = _atom_feat(a) + _nbr_feat(a) + [float(comp_of.get(i, 0)), float(dm[i, :].max())]
        fj = _atom_feat(b) + _nbr_feat(b) + [float(comp_of.get(j, 0)), float(dm[j, :].max())]
        rb = R.GetBondBetweenAtoms(i, j)
        r = _ord(rb.GetBondType()) if rb is not None else 0.0
        same = comp_of.get(i) == comp_of.get(j)
        d = dm[i, j]
        return fi + fj + [float(d) if same else 9.0, 1.0 if same else 0.0,
                          r, float(r == 0), fi[0] * 20 + fj[0]]

    hit = top1 = 0
    ranked = 0
    for r in te:
        parts = [s for s in r["smiles_r"].split(".") if s]
        R = Chem.MolFromSmiles(r["smiles_r"])
        want = canon_set(r["smiles_p"])
        if R is None or not want:
            continue
        comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)") for j, s in enumerate(parts)]
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception:
            continue
        cands = []
        for p in prods:
            c = canon_set(getattr(p, "smiles", ""))
            if c and c not in [x[0] for x in cands]:
                cands.append((c, getattr(p, "template_smarts", "") or ""))
        if not cands:
            continue
        if want in [c for c, _s in cands]:
            hit += 1
        if clf is None:
            continue

        frags = rdmolops.GetMolFrags(R)
        comp_of = {i: ci for ci, f in enumerate(frags) for i in f}
        dm = Chem.GetDistanceMatrix(R)
        scored = []
        for c, sm in cands:
            sc = -9.0
            parsed = smarts_edits(sm) if sm else None
            if parsed:
                left, right, lb, rb_ = parsed
                # 模板左侧在底物里找一处匹配
                for part in parts:
                    pm = Chem.MolFromSmiles(part)
                    if pm is None:
                        continue
                    mm = pm.GetSubstructMatch(left)
                    if not mm:
                        continue
                    # 模板映射号 -> 底物原子下标（底物内部的 index）
                    map2sub = {left.GetAtomWithIdx(k).GetAtomMapNum(): mm[k]
                               for k in range(left.GetNumAtoms())
                               if left.GetAtomWithIdx(k).GetAtomMapNum()}
                    # 底物在整体 R 里的偏移
                    off = None
                    for f in frags:
                        if pm.GetNumAtoms() == len(f):
                            off = f[0]
                            break
                    if off is None:
                        continue
                    feats, labels = [], []
                    for key in set(lb) | set(rb_):
                        o1 = lb.get(key, 0.0)
                        o2 = rb_.get(key, 0.0)
                        if abs(o1 - o2) < 0.01:
                            continue
                        a, b = key
                        if a not in map2sub or b not in map2sub:
                            continue
                        ia, ib = off + map2sub[a], off + map2sub[b]
                        lab = 2 if o2 == 0.0 else (1 if o1 == 0.0 else (3 if o2 > o1 else 4))
                        feats.append(feats_for(R, ia, ib, comp_of, dm))
                        labels.append(lab)
                    if feats:
                        import numpy as np
                        pr = clf.predict_proba(np.asarray(feats, dtype="float32"))
                        lp = sum(float(np.log(max(pr[k][lab], 1e-6))) for k, lab in enumerate(labels))
                        sc = lp / len(labels)
            scored.append((sc, c))
        scored.sort(key=lambda t: (-t[0], t[1]))
        order = [c for _s, c in scored]
        if want in order:
            ranked += 1
            if order.index(want) == 0:
                top1 += 1

    total = max(1, len(te))
    print(f"recall {hit}/{total} = {100.0*hit/total:.1f}%")
    if clf is not None:
        print(f"学习型打分后 top-1 {top1}/{total} = {100.0*top1/total:.1f}%"
              f"（可打分 {ranked}/{total}；对照：发射序 3.4%）")
    else:
        print("未找到 reports/center_model.pkl，跳过打分")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
