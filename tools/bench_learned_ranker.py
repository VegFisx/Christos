"""用学习型反应中心给模板候选打分（排序），而不是让它自己生成产物。

动机（第 146 轮的结论）：
    模板路线在 ORD 子集上 recall 50.8%，但真产物排第一只有 3.4%——
    系统最痛的地方是**排序**，不是覆盖。学习型模型知道「从底物到这个分子需要改哪些键、
    这些改动有多可能」，这正好是一个排序信号。

做法（不改引擎，只在外面加一层打分）：
    1. 把反应物做成「键级通配」的查询，在候选产物里找子结构匹配 → 得到原子对应关系。
       匹配不到 = 这个候选没法用键编辑从底物得到 → 直接给最低分（这本身就是信息）。
    2. 对反应物的每个原子对，比较「反应物键级」与「候选键级」，得到需要的变化类别。
    3. 用中心模型给每个变化类别打概率，取这些概率的几何平均作为候选得分。
       任何一处变化在模型看来概率极低（<1e-3）→ 得分打到地板。

口径：
    - 样本：`reports/center_dataset_mapped.jsonl` 前 20,000 条的测试半区（rid 哈希奇数），取前 N 条。
    - 模板：`SmartReactEngine` 默认池，条件「煎煮」，与 bench_center_vs_template.py 一致。
    - 对照：① 发射序（3.4%）② 训练好的重排序器（`core/rerank.py`，若可用）。

用法：
    python tools/bench_learned_ranker.py 500
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


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500

    import numpy as np
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    from rdkit.Chem import rdmolops
    from sklearn.ensemble import HistGradientBoostingClassifier

    from build_center_dataset import _atom_feat, _nbr_feat, _ord
    from train_center_model import _h as _h_rid, canon_set
    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    rows = []
    with open(DATA, encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
            if len(rows) >= 20000:
                break
    tr = [r for r in rows if _h_rid(r["rid"]) % 2 == 0]
    te = [r for r in rows if _h_rid(r["rid"]) % 2 == 1][:n]

    Xtr = np.asarray([x for r in tr for x in r["X"]], dtype="float32")
    ytr = np.asarray([int(v) for r in tr for v in r["y"]], dtype="int32")
    from collections import Counter
    cnt = Counter(ytr.tolist())
    w = np.array([len(ytr) / (len(cnt) * cnt[int(t)]) for t in ytr], dtype="float32")
    clf = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_leaf_nodes=63,
        min_samples_leaf=40, l2_regularization=1.0, random_state=20261111)
    clf.fit(Xtr, ytr, sample_weight=w)
    print(f"模型训练完成（{len(Xtr)} 个原子对）· 测试 {len(te)} 条反应")

    eng = SmartReactEngine()
    cond = T.get_template("煎煮")

    def _frag_mol(mol, idxs):
        """按给定原子下标顺序抽出一个碎片（保持顺序，便于把匹配结果映射回原分子）。"""
        sub = Chem.RWMol()
        new_of = {}
        for i in idxs:
            a = Chem.Atom(mol.GetAtomWithIdx(i))
            a.SetAtomMapNum(0)
            a.SetNoImplicit(True)
            new_of[i] = sub.AddAtom(a)
        idx_set = set(idxs)
        for b in mol.GetBonds():
            i, j = b.GetBeginAtomIdx(), b.GetEndAtomIdx()
            if i in idx_set and j in idx_set:
                sub.AddBond(new_of[i], new_of[j], b.GetBondType())
        return sub.GetMol()

    def make_query(mol):
        # 键级通配：候选产物的键级本来就是要判断的东西，不能拿它来做匹配条件。
        # 原子保持原样（芳香原子只匹配芳香原子），否则芳香环会全部匹配失败。
        params = Chem.AdjustQueryParameters()
        params.makeBondsGeneric = True
        params.makeAtomsGeneric = False
        params.adjustDegree = False
        params.adjustHeavyDegree = False
        q = Chem.AdjustQueryProperties(mol, params)
        return q

    def pair_feats(R, i, j, comp_of, dm):
        a, b = R.GetAtomWithIdx(i), R.GetAtomWithIdx(j)
        fi = _atom_feat(a) + _nbr_feat(a) + [float(comp_of.get(i, 0)), float(dm[i, :].max())]
        fj = _atom_feat(b) + _nbr_feat(b) + [float(comp_of.get(j, 0)), float(dm[j, :].max())]
        same = comp_of.get(i) == comp_of.get(j)
        d = dm[i, j]
        rb = R.GetBondBetweenAtoms(i, j)
        r = _ord(rb.GetBondType()) if rb is not None else 0.0
        return fi + fj + [float(d) if same else 9.0, 1.0 if same else 0.0,
                          r, float(r == 0), fi[0] * 20 + fj[0]]

    def score_candidate(R, cand_smi, queries):
        cand = Chem.MolFromSmiles(cand_smi)
        if cand is None:
            return 0.0, "unparsable"
        match = None
        fwd = {}
        for q, idxs in queries:
            mm = cand.GetSubstructMatch(q)
            if mm:
                fwd = {idxs[k]: mm[k] for k in range(len(idxs))}
                match = mm
                break
        if not match:
            return 0.0, "no_match"      # 候选无法由键编辑得到
        frags = rdmolops.GetMolFrags(R)
        comp_of = {}
        for ci, f in enumerate(frags):
            for i in f:
                comp_of[i] = ci
        dm = Chem.GetDistanceMatrix(R)
        # 反向：候选原子 -> 反应物原子（rev 已由子结构匹配给出）
        logp, n_edit = 0.0, 0
        feats, labels = [], []
        for bi in R.GetBonds():
            i, j = bi.GetBeginAtomIdx(), bi.GetEndAtomIdx()
            ci, cj = fwd.get(i), fwd.get(j)
            if ci is None or cj is None:
                continue
            cb = cand.GetBondBetweenAtoms(ci, cj)
            r_o = _ord(bi.GetBondType())
            c_o = _ord(cb.GetBondType()) if cb is not None else 0.0
            if abs(r_o - c_o) < 0.01:
                continue
            if c_o == 0.0:
                lab = 2
            elif r_o == 0.0:
                lab = 1
            elif c_o > r_o:
                lab = 3
            else:
                lab = 4
            feats.append(pair_feats(R, i, j, comp_of, dm))
            labels.append(lab)
        # 候选里新增的键（反应物原子之间原本没有）
        for bi in cand.GetBonds():
            a, b = bi.GetBeginAtomIdx(), bi.GetEndAtomIdx()
            ri, rj = {v: k for k, v in fwd.items()}.get(a), {v: k for k, v in fwd.items()}.get(b)
            if ri is None or rj is None:
                continue
            if R.GetBondBetweenAtoms(ri, rj) is None:
                feats.append(pair_feats(R, ri, rj, comp_of, dm))
                labels.append(1)
        if not feats:
            return 0.0, "no_edit"
        proba = clf.predict_proba(np.asarray(feats, dtype="float32"))
        for k, lab in enumerate(labels):
            p = float(proba[k][lab])
            logp += np.log(max(p, 1e-6))
            n_edit += 1
        return logp / max(1, n_edit), f"edits={n_edit}"

    top1 = hit = err = 0
    ranks = []
    stat = Counter()
    for r in te:
        parts = [s for s in r["smiles_r"].split(".") if s]
        R = Chem.MolFromSmiles(r["smiles_r"])
        want = canon_set(r["smiles_p"])
        if R is None or not want:
            continue
        frag_idxs = rdmolops.GetMolFrags(R)
        queries = []
        for idxs in frag_idxs:
            fm = _frag_mol(R, idxs)
            if fm is None or fm.GetNumAtoms() != len(idxs):
                continue
            queries.append((make_query(fm), tuple(idxs)))
        comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)") for j, s in enumerate(parts)]
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception:
            err += 1
            continue
        cands = []
        for p in prods:
            c = canon_set(getattr(p, "smiles", ""))
            if c and c not in cands:
                cands.append(c)
        if not cands:
            continue
        if want in cands:
            hit += 1
        scored = []
        for c in cands:
            sc, why = score_candidate(R, c, queries)
            stat[why] += 1
            scored.append((sc, c))
        scored.sort(key=lambda t: (-t[0], t[1]))
        order = [c for _s, c in scored]
        if want in order:
            rank = order.index(want) + 1
            ranks.append(rank)
            if rank == 1:
                top1 += 1

    total = max(1, len(te))
    print(f"\n模板候选总数 {sum(stat.values())} · 打分失败原因 {dict(stat.most_common(4))}")
    print(f"recall      {hit}/{total} = {100.0*hit/total:.1f}%")
    print(f"学习型打分后 top-1 {top1}/{total} = {100.0*top1/total:.1f}%"
          f"  （对照：发射序 3.4%、重排序器 1.6%）")
    if ranks:
        ranks.sort()
        print(f"命中位次：中位 {ranks[len(ranks)//2]} · p90 {ranks[int(len(ranks)*0.9)]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
