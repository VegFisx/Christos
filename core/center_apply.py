# -*- coding: utf-8 -*-
r"""把「预测出的键变化」确定性地施加到反应物上，得到产物。

这是学习型反应中心路线的第二步：模型只负责**指出哪些键变、变成什么**，
成键/断键之后的结构由这里按规则组装，不再查模板。

用法：
    from core.center_apply import apply_edits
    smi = apply_edits("CCO.O=C(O)c1ccccc1", [(9, 26, 1.0)])

约定：
  * edits = [(原子映射号 a, 原子映射号 b, 目标键级)]，0 = 断键，1/2/3 = 单/双/三键，
    1.5 = 芳香键。
  * **不做 Kekulize**：反应物与产物里的同一张芳香环可能被 RDKit 选成不同的 Kekulé
    结构，逐键相减会凭空造出「升键/降键」，施加时价态必然爆掉（这是第一版 3.4% 上界
    的主因）。这里全程在芳香表示下比较与施加，芳香键记 1.5。
  * 氢的处理：按「配体替换」语义 —— 成一根键，就给两端各扣一个氢；
    断一根键，各补一个氢；键级升降按差量扣补。
  * 施加后清掉映射号、sanitize；失败返回 None（不猜）。
  * 产物按「重原子碎片」规范排序返回，便于与文献产物逐字比较（含离去基团）。
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

_ORD = {1.0: Chem.BondType.SINGLE, 1.5: Chem.BondType.AROMATIC,
        2.0: Chem.BondType.DOUBLE, 3.0: Chem.BondType.TRIPLE}


def _bond_order(b: Chem.Bond) -> float:
    t = b.GetBondType()
    if t == Chem.BondType.SINGLE:
        return 1.0
    if t == Chem.BondType.DOUBLE:
        return 2.0
    if t == Chem.BondType.TRIPLE:
        return 3.0
    if t == Chem.BondType.AROMATIC:
        return 1.5
    return 1.0


def _sum_orders(rw: Chem.RWMol, idx: int) -> float:
    s = 0.0
    for b in rw.GetAtomWithIdx(idx).GetBonds():
        s += _bond_order(b)
    return s


_PT = Chem.GetPeriodicTable()


def _relax_charge(a: Chem.Atom) -> None:
    """价态超出允许范围时，用形式电荷把价态拉回合法值。

    规则来自价电子数：电荷每 +1，允许价态上限 +1；电荷每 -1，上限 -1。
    只在「改过的原子」上调用，且优先选 |q| 最小的电荷，避免乱改电荷。
    """
    try:
        base = list(_PT.GetValenceList(a.GetAtomicNum()))
    except Exception:
        return
    if not base:
        return
    v = int(round(sum(_bond_order(b) for b in a.GetBonds()) + a.GetNumExplicitHs()))
    best = None
    for q in (0, 1, -1, 2, -2):
        allowed = [x + q for x in base]
        if v in allowed or v <= max(allowed):
            best = q
            break
    if best is not None and best != a.GetFormalCharge():
        a.SetFormalCharge(best)


def _canon_parts(mol: Chem.Mol) -> str:
    parts = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False)
    outs = []
    for p in parts:
        try:
            Chem.SanitizeMol(p)
            outs.append(Chem.MolToSmiles(p))
        except Exception:
            return ""
    return ".".join(sorted(outs))


def apply_edits(smiles_r: str, edits: Iterable[Tuple[int, int, float]],
                keep_maps: bool = False) -> Optional[str]:
    m = Chem.MolFromSmiles(smiles_r)
    if m is None:
        return None
    rw = Chem.RWMol(m)
    map2idx: Dict[int, int] = {}
    for a in rw.GetAtoms():
        n = a.GetAtomMapNum()
        if n:
            map2idx[n] = a.GetIdx()

    def _idx(x: int) -> Optional[int]:
        if x in map2idx:
            return map2idx[x]
        if 0 <= x < rw.GetNumAtoms():
            return x
        return None

    old_sum: Dict[int, float] = {}
    old_h: Dict[int, int] = {}
    for a in rw.GetAtoms():
        i = a.GetIdx()
        old_sum[i] = _sum_orders(rw, i)
        old_h[i] = a.GetTotalNumHs(includeNeighbors=False)

    touched = set()
    for i, j, order in edits:
        a, b = _idx(int(i)), _idx(int(j))
        if a is None or b is None or a == b:
            return None
        touched.add(a)
        touched.add(b)
        bt = rw.GetBondBetweenAtoms(a, b)
        if order <= 0.0:
            if bt is not None:
                rw.RemoveBond(a, b)
            continue
        t = _ORD.get(float(order), Chem.BondType.SINGLE)
        if bt is not None:
            bt.SetBondType(t)
            if t == Chem.BondType.AROMATIC:
                bt.SetIsAromatic(True)
                rw.GetAtomWithIdx(a).SetIsAromatic(True)
                rw.GetAtomWithIdx(b).SetIsAromatic(True)
        else:
            rw.AddBond(a, b, t)

    # 只调被改过的原子的显式氢：让它们「总价态守恒」。
    for i in touched:
        a = rw.GetAtomWithIdx(i)
        delta = old_sum[i] - _sum_orders(rw, i)   # 成键为负、断键为正
        a.SetNoImplicit(True)
        a.SetNumExplicitHs(max(0, old_h[i] + int(round(delta))))

    # 价态超了就用形式电荷吸收：每多一个负电荷，允许价态少 1；正电荷多 1。
    # 例：叠氮末端 N⁻ 成键后需要变回中性 N（价态 3），否则 sanitize 直接报 Explicit valence。
    for i in touched:
        _relax_charge(rw.GetAtomWithIdx(i))

    if not keep_maps:
        for a in rw.GetAtoms():
            a.SetAtomMapNum(0)

    mol = rw.GetMol()
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        return None
    s = _canon_parts(mol)
    return s or None
