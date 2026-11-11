# -*- coding: utf-8 -*-
r"""学习型反应中心：数据集构建。

思路（与模板范式不同的表示）：
  模板 = 「把底物的局部环境对齐到某个字面写法」，环境一多就漏。
  学习型 = 直接问「这些原子里，哪一对的键会变、变成什么」，由模型从语料里学，
           再按预测出的键变化**确定性地**重建产物（不需要再查模板）。

本脚本只做数据集：
  输入 reports/ord_shards_full/*.jsonl（每行 {"template", "rx": 带映射的反应式}）
  输出 reports/center_dataset.jsonl，每行一个反应：
    {"rid", "n_atoms", "n_comp", "pair_idx": [...], "X": [[...]], "y": [...], "n_neg"}
  y: 0=不变 1=成键 2=断键 3=键级升 4=键级降

候选对（决定问题规模）：
  * 同分子内：图距离 ≤ 3 的对
  * 跨分子：全部对（上限 300/反应）
  * 已有键且距离 >3：默认不变（不进候选，省算力），除非键级变（从标签里单独补进来）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
if str(STAGE / "libs") not in sys.path:
    sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdmolops  # noqa: E402
import os

RDLogger.DisableLog("rdApp.*")

ELEMS = ["C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "B", "Si", "Se"]
EIDX = {e: i for i, e in enumerate(ELEMS)}
HYB = {Chem.HybridizationType.S: 0, Chem.HybridizationType.SP: 1,
       Chem.HybridizationType.SP2: 2, Chem.HybridizationType.SP3: 3,
       Chem.HybridizationType.SP3D: 4, Chem.HybridizationType.SP3D2: 5}

MAX_DIST = 3
MAX_CROSS = 300


def _ord(m):
    if m is None:
        return 0
    if m == Chem.BondType.SINGLE:
        return 1
    if m == Chem.BondType.DOUBLE:
        return 2
    if m == Chem.BondType.TRIPLE:
        return 3
    if m == Chem.BondType.AROMATIC:
        return 1.5
    return 1


def _atom_feat(a) -> list:
    el = EIDX.get(a.GetSymbol(), 12)
    return [
        float(el), float(a.GetDegree()), float(a.GetTotalNumHs()),
        float(a.GetFormalCharge() + 3), 1.0 if a.GetIsAromatic() else 0.0,
        1.0 if a.IsInRing() else 0.0, float(HYB.get(a.GetHybridization(), 6)),
    ]


def _nbr_feat(a) -> list:
    cnt = {e: 0.0 for e in ("N", "O", "S", "C")}
    for nb in a.GetNeighbors():
        s = nb.GetSymbol()
        if s in cnt:
            cnt[s] += 1.0
    return [cnt["N"], cnt["O"], cnt["S"], cnt["C"]]


def _row(rid, rx) -> dict | None:
    if ">>" not in rx:
        return None
    lhs, rhs = rx.split(">>", 1)
    R = Chem.MolFromSmiles(lhs)
    P = Chem.MolFromSmiles(rhs)
    # ★ 不在两侧做 Kekulize：同一张芳香环在反应物与产物里可能被选成不同的
    #   Kekulé 结构，逐键相减会凭空多出「升键/降键」，施加时价态必爆。
    #   统一在芳香表示下比较（芳香键记 1.5），施加器也按芳香键处理。
    if R is None or P is None:
        return None
    # ★ 键编辑只能表达「两侧都带映射号」的原子之间的变化；未映射原子（离去基团、
    #   试剂残基）在产物里出现时，拓扑编辑造不出来。实测这类反应占 ORD 的 96.7%，
    #   把全映射子集的还原率（61.9%）稀释成了 3%。
    #   CENTER_ALL_MAPPED=1 时只保留「所有原子都带映射号」的反应。
    if os.environ.get("CENTER_ALL_MAPPED", "").strip() in ("1", "true", "yes", "on"):
        if any(a.GetAtomMapNum() == 0 for a in R.GetAtoms()):
            return None
        if any(a.GetAtomMapNum() == 0 for a in P.GetAtoms()):
            return None
    if not any(a.GetAtomMapNum() for a in R.GetAtoms()):
        return None
    # 原子映射 -> 产物下标
    pmap = {}
    for a in P.GetAtoms():
        n = a.GetAtomMapNum()
        if n:
            pmap[n] = a.GetIdx()
    # 反应物侧：保留映射原子的顺序
    atoms = [a for a in R.GetAtoms()]
    idx_of = {}
    keep = []
    for a in atoms:
        if a.GetAtomMapNum() in pmap:
            idx_of[a.GetIdx()] = len(keep)
            keep.append(a.GetIdx())
    if len(keep) < 2:
        return None
    # 成分（用于判断跨分子）
    frags = rdmolops.GetMolFrags(R)
    comp_of = {}
    for ci, f in enumerate(frags):
        for i in f:
            comp_of[i] = ci
    # 距离矩阵
    dm = Chem.GetDistanceMatrix(R)
    # 原子特征
    AF = {}
    for i in keep:
        a = atoms[i]
        AF[i] = _atom_feat(a) + _nbr_feat(a) + [float(comp_of.get(i, 0)),
                                                float(dm[i, :].max())]
    # 产物侧键表（按映射号）
    pbond = {}
    for b in P.GetBonds():
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        m1, m2 = a1.GetAtomMapNum(), a2.GetAtomMapNum()
        if m1 and m2:
            pbond[(min(m1, m2), max(m1, m2))] = _ord(b.GetBondType())
    rbonds = {}
    for b in R.GetBonds():
        m1 = R.GetAtomWithIdx(b.GetBeginAtomIdx()).GetAtomMapNum()
        m2 = R.GetAtomWithIdx(b.GetEndAtomIdx()).GetAtomMapNum()
        if m1 and m2:
            rbonds[(min(m1, m2), max(m1, m2))] = _ord(b.GetBondType())

    X, y, pairs = [], [], []
    n_cross = 0
    for ii in range(len(keep)):
        for jj in range(ii + 1, len(keep)):
            i, j = keep[ii], keep[jj]
            same = comp_of.get(i) == comp_of.get(j)
            d = dm[i, j]
            if same and d > MAX_DIST:
                continue
            if not same:
                n_cross += 1
                if n_cross > MAX_CROSS:
                    continue
            m1 = atoms[i].GetAtomMapNum()
            m2 = atoms[j].GetAtomMapNum()
            key = (min(m1, m2), max(m1, m2))
            r = rbonds.get(key, 0.0)
            p = pbond.get(key, 0.0)
            if abs(r - p) < 0.01:
                lab = 0
            elif r == 0.0:
                lab = 1
            elif p == 0.0:
                lab = 2
            elif p > r:
                lab = 3
            else:
                lab = 4
            fi, fj = AF[i], AF[j]
            # ★ 只许用反应物侧信息：p 是标签本身，绝不能进特征（第一版因此 100% 命中）
            X.append(fi + fj + [
                float(d) if same else 9.0,
                1.0 if same else 0.0,
                r, float(r == 0),
                fi[0] * 20 + fj[0],
            ])
            y.append(lab)
            pairs.append([int(m1), int(m2)])
    if not X:
        return None
    return {"rid": rid, "n_atoms": len(keep), "n_comp": len(frags),
            "pair_idx": pairs, "X": X, "y": y,
            "smiles_r": lhs, "smiles_p": rhs}


def main() -> int:
    n_shard = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    neg_ratio = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    out = STAGE / "reports" / (os.environ.get("CENTER_OUT") or "center_dataset.jsonl")
    files = sorted((STAGE / "reports" / "ord_shards_full").glob("shard_*.jsonl"))[:n_shard]
    print(f"文件 {len(files)} 个 · 上限 {limit} 反应 · 负样本比 {neg_ratio}:1", flush=True)
    n_ok = n_bad = 0
    lab_cnt = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    import random as _rnd
    rng = _rnd.Random(20261111)
    with open(out, "w", encoding="utf-8") as f:
        for p in files:
            for line in open(p, encoding="utf-8"):
                if n_ok >= limit:
                    break
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                rid = f"{p.stem}:{n_ok}"
                row = _row(rid, rec.get("rx") or "")
                if not row:
                    n_bad += 1
                    continue
                # 负样本下采样：候选对里 99% 是「不变」，全留会把模型训成只会猜 0
                pos = [i for i, v in enumerate(row["y"]) if v != 0]
                neg = [i for i, v in enumerate(row["y"]) if v == 0]
                if not pos:
                    continue
                keep_neg = rng.sample(neg, min(len(neg), neg_ratio * len(pos)))
                keep = sorted(pos + keep_neg)
                row["X"] = [row["X"][i] for i in keep]
                row["y"] = [row["y"][i] for i in keep]
                row["pair_idx"] = [row["pair_idx"][i] for i in keep]
                for v in row["y"]:
                    lab_cnt[v] = lab_cnt.get(v, 0) + 1
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_ok += 1
            if n_ok >= limit:
                break
    print(f"写出反应 {n_ok}（跳过 {n_bad}）· 标签分布 {lab_cnt} · {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
