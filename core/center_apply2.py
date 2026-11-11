# -*- coding: utf-8 -*-
r"""施加器 v2：按「目标价态」补氢，而不是按键级差量扣补。

为什么需要 v2：数据集放宽到「产物全映射、反应物可带未映射试剂」之后，施加前要把试剂
残渣剥掉（`maps_whitelist`），剥掉后原子上会残留悬挂键，v1 的「差量扣补」会在芳香/带电
原子上算错氢，出现 `[C]` 自由基或超价（实测上界从 70.7% 掉到 23.5%）。

v2 的做法：
  1. 剥掉白名单外的原子（试剂/溶剂残基）；
  2. 在保留分子上按映射号改键（芳香键记 1.5，不 Kekulize）；
  3. 对被改过的原子**重新分配氢**：目标价态 = 该元素在给定电荷下的价态表里
     「不小于当前键级和」的最小值；氢 = 目标 - 键级和；
  4. 目标价态配不上时用形式电荷扩容（每 +1 电荷容量 +1），再不行就放弃（不猜）。

与 v1 的差别只有第 3 步：v1 用 `delta = 旧键级和 - 新键级和` 在旧氢数上做加减，
在「原子集合变过」的情况下旧氢数本身就不可比，所以会崩。
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from rdkit import Chem, RDLogger

from core.center_apply import _bond_order, _canon_parts, _relax_charge, _ORD

RDLogger.DisableLog("rdApp.*")

_PT = Chem.GetPeriodicTable()


def _strip(smiles_r: str, whitelist=None) -> Optional[Chem.Mol]:
    m = Chem.MolFromSmiles(smiles_r)
    if m is None:
        return None
    if whitelist is None:
        whitelist = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
    keep = [a.GetIdx() for a in m.GetAtoms() if a.GetAtomMapNum() in whitelist]
    if not keep:
        return None
    if len(keep) == m.GetNumAtoms():
        return m
    em = Chem.RWMol(m)
    for i in sorted(set(range(m.GetNumAtoms())) - set(keep), reverse=True):
        em.RemoveAtom(i)
    try:
        Chem.SanitizeMol(em)
    except Exception:
        return None
    return em.GetMol()


def _target_valence(atom: Chem.Atom, bond_sum: float) -> Optional[int]:
    q = int(atom.GetFormalCharge())
    try:
        base = list(_PT.GetValenceList(atom.GetAtomicNum()))
    except Exception:
        return None
    if not base:
        return None
    allowed = [v + q for v in base]
    need = int(round(bond_sum))
    cands = [v for v in allowed if v >= need]
    if cands:
        return min(cands)
    # 配不上：允许用电荷把容量顶上去（最多把容量放大到 need）
    if max(allowed) < need:
        extra = need - max(allowed)
        if extra <= 2:
            atom.SetFormalCharge(q + extra)
            return need
    return None


def apply_edits2(smiles_r: str, edits: Iterable[Tuple[int, int, float]],
                 maps_whitelist=None, keep_maps: bool = False) -> Optional[str]:
    # ★ 先 kekulize 成整数键级再改键：改完让 sanitize 重新感知芳香性。
    #   在「芳香键记 1.5」的表示里改环上的键，会让环原子同时挂芳香键与非芳香键，
    #   sanitize/kekulize 直接失败（实测 relaxed 子集 233/377 就是这个）。
    #   触碰芳香键的编辑本就不做（见 probe_apply_aromatic 的 supported 口径），
    #   所以这里可以对整分子放心 kekulize。
    m = _strip(smiles_r, maps_whitelist)
    if m is None:
        return None
    try:
        m = Chem.Mol(m)
        Chem.Kekulize(m, clearAromaticFlags=True)
    except Exception:
        return None
    rw = Chem.RWMol(m)
    map2idx: Dict[int, int] = {a.GetAtomMapNum(): a.GetIdx()
                               for a in rw.GetAtoms() if a.GetAtomMapNum()}

    touched = set()
    for i, j, order in edits:
        a, b = map2idx.get(int(i)), map2idx.get(int(j))
        if a is None or b is None or a == b:
            return None
        touched.add(a)
        touched.add(b)
        bt = rw.GetBondBetweenAtoms(a, b)
        if order <= 0.0:
            if bt is not None:
                rw.RemoveBond(a, b)
            continue
        if abs(float(order) - 1.5) < 0.01:
            return None          # 芳香键的编辑不做（方案 2）
        t = _ORD.get(float(order), Chem.BondType.SINGLE)
        if bt is not None:
            bt.SetBondType(t)
            if t == Chem.BondType.AROMATIC:
                bt.SetIsAromatic(True)
                rw.GetAtomWithIdx(a).SetIsAromatic(True)
                rw.GetAtomWithIdx(b).SetIsAromatic(True)
        else:
            rw.AddBond(a, b, t)

    for i in touched:
        a = rw.GetAtomWithIdx(i)
        bs = sum(_bond_order(b) for b in a.GetBonds())
        if a.GetIsAromatic():
            # 芳香原子交给 sanitize 的隐式氢（芳香键记 1.5，按整数价态算会差半个键）
            a.SetNoImplicit(False)
            a.SetNumExplicitHs(0)
            continue
        tv = _target_valence(a, bs)
        if tv is None:
            return None
        h = tv - int(round(bs))
        if h < 0:
            return None
        a.SetNoImplicit(True)
        a.SetNumExplicitHs(int(h))

    # 芳香原子跳过了配氢，但改键同样可能让它们超价（N 4 键、O 3 键），统一用形式电荷收尾。
    for i in touched:
        _relax_charge(rw.GetAtomWithIdx(i))

    if not keep_maps:
        for a in rw.GetAtoms():
            a.SetAtomMapNum(0)
    mol = rw.GetMol()
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        # 改键可能破坏芳香体系。先尝试正规的 kekulize（写成交替单双键），
        # sanitize 时再重新感知芳香性。**不能**把所有芳香键一口气改成单键——
        # 那会把分子里每一个芳环都毁掉（实测 diff 里 [C]2[CH][CH]... 就是它干的）。
        try:
            Chem.Kekulize(mol, clearAromaticFlags=True)
            Chem.SanitizeMol(mol)
        except Exception:
            return None
    s = _canon_parts(mol)
    return s or None
