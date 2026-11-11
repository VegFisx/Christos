"""用学习型反应中心模型给候选产物打分（生产侧）。

来源：`reports/第一百四十六轮-学习型反应中心-20261111.md` §9。
在 ORD 全映射子集上，模板引擎 recall 50.8%、发射序 top-1 3.4%；
用这个信号给同一批候选重排后 top-1 20.0%（recall 不变）。

原理（一句话）：模板命中时引擎已经把模板 SMARTS 记进 `template_smarts`；
模板 SMARTS 本身就写明「左侧哪些键、右侧哪些键」，把左侧和底物做一次标准子结构匹配，
就能得到「这一步真实改了哪几处键」，再问中心模型「每种改动有多可能」。

不做任何反查图匹配 —— 那条路在真实产物上只有 67% 能匹配（模板会删原子）。

设计取舍：
    * 模型或 SMARTS 缺失时**退回原序**，不抛异常（生产路径不能因为排序模型挂掉而失败）。
    * 打分失败的产物给地板分，但**保持它们之间的原始相对顺序**（稳定排序）。
    * 只用于排序，不改候选集合 —— 与 `core/rerank.py` 的契约一致。
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
DEFAULT_MODEL = _STAGE / "reports" / "center_model.pkl"

_ORD = {Chem.BondType.SINGLE: 1.0, Chem.BondType.DOUBLE: 2.0,
        Chem.BondType.TRIPLE: 3.0, Chem.BondType.AROMATIC: 1.5}
_ELEM = {"C": 0, "N": 1, "O": 2, "S": 3, "P": 4, "F": 5, "Cl": 6, "Br": 7,
         "I": 8, "B": 9, "Si": 10, "Na": 11, "K": 12, "Se": 13}
_HYB = {"S": 0, "SP": 1, "SP2": 2, "SP3": 3, "SP3D": 4, "SP3D2": 5, "UNSPECIFIED": 6}


def _atom_feat(a: Chem.Atom) -> List[float]:
    return [float(_ELEM.get(a.GetSymbol(), 14)), float(a.GetDegree()),
            float(a.GetTotalNumHs()), float(a.GetFormalCharge() + 3),
            1.0 if a.GetIsAromatic() else 0.0, 1.0 if a.IsInRing() else 0.0,
            float(_HYB.get(str(a.GetHybridization()), 6))]


def _nbr_feat(a: Chem.Atom) -> List[float]:
    cnt = {"N": 0.0, "O": 0.0, "S": 0.0, "C": 0.0}
    for nb in a.GetNeighbors():
        s = nb.GetSymbol()
        if s in cnt:
            cnt[s] += 1.0
    return [cnt["N"], cnt["O"], cnt["S"], cnt["C"]]


def _bonds(mol: Chem.Mol) -> Dict[Tuple[int, int], float]:
    out: Dict[Tuple[int, int], float] = {}
    for b in mol.GetBonds():
        m1 = b.GetBeginAtom().GetAtomMapNum()
        m2 = b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            out[(min(m1, m2), max(m1, m2))] = _ORD.get(b.GetBondType(), 1.0)
    return out


class CenterRanker:
    """把中心模型当排序器。`ok=False` 时 `score()` 全部返回地板分。"""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self.ok = False
        self.note = ""
        path = Path(model_path) if model_path else DEFAULT_MODEL
        if not path.exists():
            self.note = f"缺模型 {path.name}"
            return
        try:
            with open(path, "rb") as fh:
                self._model = pickle.load(fh)
            self.ok = True
            self.note = f"已加载 {path.name}"
        except Exception as exc:                      # noqa: BLE001
            self.note = f"模型加载失败：{exc}"

    # ---------------- 内部 ----------------
    @staticmethod
    def _parts(smarts: str):
        if not smarts or ">>" not in smarts:
            return None
        lhs, rhs = smarts.split(">>", 1)
        left = Chem.MolFromSmarts(lhs)
        right = Chem.MolFromSmarts(rhs)
        if left is None or right is None:
            return None
        return left, _bonds(left), _bonds(right)

    def _pair_feats(self, mol: Chem.Mol, i: int, j: int, dm, ci: int = 0) -> List[float]:
        a, b = mol.GetAtomWithIdx(i), mol.GetAtomWithIdx(j)
        # ★ 特征顺序必须与 tools/build_center_dataset.py 的 _row() 完全一致：
        #   原子 7 + 邻域 4 + [组分下标, 最远距离] = 13，两侧 26，再加 5 项 = 31。
        fi = _atom_feat(a) + _nbr_feat(a) + [float(ci), float(dm[i, :].max())]
        fj = _atom_feat(b) + _nbr_feat(b) + [float(ci), float(dm[j, :].max())]
        rb = mol.GetBondBetweenAtoms(i, j)
        r = _ORD.get(rb.GetBondType(), 1.0) if rb is not None else 0.0
        d = dm[i, j]
        return fi + fj + [float(d), 1.0, r, float(r == 0), fi[0] * 20 + fj[0]]

    def _score_one(self, smarts: str, mols: Sequence[Chem.Mol]) -> float:
        parsed = self._parts(smarts)
        if parsed is None:
            return -9.0
        left, lb, rb = parsed
        keys = set(lb) | set(rb)
        if not keys:
            return -9.0
        best = -9.0
        for ci, mol in enumerate(mols):
            if mol is None:
                continue
            mm = mol.GetSubstructMatch(left)
            if not mm:
                continue
            map2sub = {left.GetAtomWithIdx(k).GetAtomMapNum(): mm[k]
                       for k in range(left.GetNumAtoms())
                       if left.GetAtomWithIdx(k).GetAtomMapNum()}
            feats, labels = [], []
            dm = Chem.GetDistanceMatrix(mol)
            for key in sorted(keys):
                o1, o2 = lb.get(key, 0.0), rb.get(key, 0.0)
                if abs(o1 - o2) < 0.01:
                    continue
                a, b = key
                if a not in map2sub or b not in map2sub:
                    continue
                lab = 2 if o2 == 0.0 else (1 if o1 == 0.0 else (3 if o2 > o1 else 4))
                feats.append(self._pair_feats(mol, map2sub[a], map2sub[b], dm, ci))
                labels.append(lab)
            if not feats:
                continue
            import numpy as np

            pr = self._model.predict_proba(np.asarray(feats, dtype="float32"))
            lp = sum(float(np.log(max(pr[k][lab], 1e-6))) for k, lab in enumerate(labels))
            sc = lp / len(labels)
            if sc > best:
                best = sc
        return best

    # ---------------- 对外 ----------------
    def score(self, product: Any, mols: Sequence[Chem.Mol]) -> float:
        if not self.ok:
            return -9.0
        try:
            return self._score_one(getattr(product, "template_smarts", "") or "", mols)
        except Exception:                              # noqa: BLE001
            return -9.0

    def reorder(self, products: List[Any], mols: Sequence[Chem.Mol]) -> List[Any]:
        """按中心模型得分降序（稳定排序，同分保持发射序）。"""
        if not self.ok or len(products) < 2:
            return products
        scored = [(self.score(p, mols), i, p) for i, p in enumerate(products)]
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [p for _s, _i, p in scored]


def load(model_path: Optional[Path] = None) -> Optional[CenterRanker]:
    r = CenterRanker(model_path)
    return r if r.ok else None


__all__ = ["CenterRanker", "load", "DEFAULT_MODEL"]
