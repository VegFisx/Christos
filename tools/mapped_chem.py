# -*- coding: utf-8 -*-
r"""★ 原子映射安全工具 —— 堵住本工作区反复踩的那个坑 ★

## 背景：同一个坑踩了两次（2026-10-11）

  `canon_nomap()` 会【抹掉原子映射号】。它返回的 SMILES 再做 MolFromSmiles，
  得到的分子**没有任何映射号**。如果把它喂给依赖映射的逻辑（bond_set、
  RDChiral 等），会**静默地**得到空集合或抽不出模板，而不是报错。

  踩坑记录：
    ① `extract_new_templates.py`：用 canon_nomap 的输出喂 RDChiral
       → 340 次尝试抽出 0 个模板，还被 try/except 吞掉
    ② `measure_ord_np_share.py`：用 canon_nomap 的输出算 bond_set
       → 底物键集恒为空 → 每条反应都被判成"多键"，跑出"单键 0 条"

## 本模块的原则

  · **带映射**的分子  -> 用 `parse_mapped()`，它保证映射号存在，否则抛错
  · **不带映射**的分子 -> 用 `parse_plain()`；只用于比较/规范化
  · 需要映射的地方一律用 `bonds_over_maps()`，**没有映射就抛 MapStrippedError**
  · 不要再用 `MolFromSmiles(canon_nomap(x))` 这种写法

## 用法

    import mapped_chem as mc

    prod = mc.parse_mapped(rhs)                 # 产物（带映射）
    raws, plains = mc.contributing_components(lhs, mc.map_nums(prod))
    left, _ = mc.bonds_over_maps_all(raws)      # 底物侧键集合
    formed, broken = mc.formed_broken(prod, left)

自检：python mapped_chem.py
"""
from __future__ import annotations

import sys
from typing import Iterable, Optional, Sequence

# ★ 防止在 GBK 控制台上因非 ASCII 字符（✓ 等）崩溃
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem

__all__ = [
    "MapStrippedError", "parse_mapped", "parse_plain", "canon_plain",
    "map_nums", "bonds_over_maps", "bonds_over_maps_all",
    "split_rxn", "contributing_components", "formed_broken",
]


class MapStrippedError(ValueError):
    """把【没有原子映射号】的分子喂给了依赖映射的逻辑。"""


# ---------------------------------------------------------------- 解析
def parse_mapped(smiles: str, context: str = "") -> Optional[Chem.Mol]:
    """解析一个【必须带原子映射号】的 SMILES。没有映射号就抛 MapStrippedError。"""
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    if not map_nums(m):
        raise MapStrippedError(
            f"这个分子没有任何原子映射号，不能用它做映射相关运算。{context}\n"
            f"  常见原因：它的 SMILES 来自 canon_plain()/canon_nomap()（映射号被抹掉了）\n"
            f"  SMILES: {smiles[:120]}"
        )
    return m


def parse_plain(smiles: str) -> Optional[Chem.Mol]:
    """解析一个普通 SMILES（不要求映射号）。只用于比较/规范化。"""
    try:
        return Chem.MolFromSmiles(smiles)
    except Exception:
        return None


def canon_plain(smiles: str) -> Optional[str]:
    """规范化 SMILES 并把映射号清零 —— 只用于【比较】，不要拿结果做映射运算。

    （这是原 canon_nomap 的替代品，改名是为了让"它不带映射"这件事写在脸上。）
    """
    m = parse_plain(smiles)
    if m is None:
        return None
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m)


# ---------------------------------------------------------------- 映射
def map_nums(mol: Chem.Mol) -> set:
    """分子里所有非零原子映射号。"""
    return {a.GetAtomMapNum() for a in mol.GetAtoms() if a.GetAtomMapNum() > 0}


def bonds_over_maps(mol: Chem.Mol) -> set:
    """映射原子之间的键集合 (min,max)。

    ★ 这个函数是本模块的核心防线：没有映射号就【抛错】，不再静默返回空集。
    这正是那两次事故的根因（空集被当成"底物没有键"）。"""
    if mol is None:
        return set()
    nums = map_nums(mol)
    if not nums:
        raise MapStrippedError(
            "bonds_over_maps() 收到一个【没有任何原子映射号】的分子。\n"
            "  如果你是想算反应中心，请传【带映射的原始组分】，\n"
            "  不要传 canon_plain()/canon_nomap() 的结果。"
        )
    out = set()
    for b in mol.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            out.add((min(m1, m2), max(m1, m2)))
    return out


def bonds_over_maps_all(smiles_list: Iterable[str]) -> set:
    """把多个【带映射】组分的键集合合并。"""
    out = set()
    for s in smiles_list:
        m = parse_mapped(s, context="(来自 bonds_over_maps_all)")
        if m is not None:
            out |= bonds_over_maps(m)
    return out


# ---------------------------------------------------------------- 反应
def split_rxn(cx: str):
    """拆 CXSMILES 反应：支持两段式 底物>>产物 与三段式 底物>试剂>产物。

    返回 (底物侧, 试剂侧, 产物侧)；拆不出返回 (None, None, None)。
    """
    if not cx:
        return None, None, None
    body = cx[:cx.index("|")] if "|" in cx else cx
    parts = [p for p in body.split(">") if p.strip()]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return None, None, None


def contributing_components(lhs: str, prod_map_nums: set, ratio: float = 0.5):
    """从底物侧挑出【贡献原子到产物】的组分。

    返回 (raws, plains)：
      · raws   —— 带映射的原始 SMILES  ★ 算反应中心只能用这个 ★
      · plains —— 规范化去映射的 SMILES（用于比较、喂枚举器）
    """
    raws, plains = [], []
    for s in (x for x in (lhs or "").split(".") if x):
        m = parse_plain(s)
        if m is None:
            continue
        nums = map_nums(m)
        if nums and len(nums & prod_map_nums) / len(nums) > ratio:
            raws.append(s)
            cs = canon_plain(s)
            if cs:
                plains.append(cs)
    return raws, plains


def formed_broken(prod_mapped: Chem.Mol, left_bonds: set):
    """返回 (成键, 断键)。prod_mapped 必须带映射。"""
    right = bonds_over_maps(prod_mapped)
    return right - left_bonds, left_bonds - right


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    # 单元测试用的示意数据（不是化学数据，仅为验证代码路径）
    RXN = "CC(=O)O.NCC>>CC(=O)NCC"
    MAPPED = "[CH3:1][C:2](=[O:3])[OH:4].[NH2:5][CH2:6][CH3:7]>>[CH3:1][C:2](=[O:3])[NH:5][CH2:6][CH3:7]"

    ok = 0
    fail = 0

    def check(name, cond):
        global ok, fail
        if cond:
            ok += 1
            print(f"   ✓ {name}")
        else:
            fail += 1
            print(f"   ✗ {name}")

    print("=" * 88)
    print("mapped_chem 自检")
    print("=" * 88)

    # ① 核心防线：去映射的分子不能进 bonds_over_maps
    print("\n① 核心防线：静默失败 -> 响亮报错")
    stripped = canon_plain(MAPPED.split(">>")[1])
    try:
        bonds_over_maps(Chem.MolFromSmiles(stripped))
        check("去映射分子应当抛 MapStrippedError", False)
    except MapStrippedError as ex:
        check("去映射分子抛出了 MapStrippedError", True)
        print(f"       报错信息首行：{str(ex).splitlines()[0]}")

    # ② 带映射的分子正常返回
    print("\n② 带映射的分子正常工作")
    pm = parse_mapped(MAPPED.split(">>")[1])
    bs = bonds_over_maps(pm)
    check("产物键集合非空", len(bs) > 0)
    print(f"       产物映射键 {len(bs)} 条: {sorted(bs)[:6]}")

    # ③ 复现那两次事故的写法，确认现在会报错
    print("\n③ 复现事故写法（canon_plain 的输出再 MolFromSmiles）")
    try:
        bad = Chem.MolFromSmiles(canon_plain(MAPPED.split(">>")[1]))
        bonds_over_maps(bad)
        check("事故写法应当报错", False)
    except MapStrippedError:
        check("事故写法现在会报错（以前是静默返回空集）", True)

    # ④ contributing_components 正常
    print("\n④ 组分识别")
    lhs, _, rhs = split_rxn(MAPPED)
    pm2 = parse_mapped(rhs)
    raws, plains = contributing_components(lhs, map_nums(pm2))
    check("识别出 2 个贡献组分", len(raws) == 2)
    check("raws 仍带映射号", all(map_nums(parse_plain(s)) for s in raws))
    check("plains 已去映射", all(not map_nums(parse_plain(s)) for s in plains))

    # ⑤ formed_broken 得到【1 根成键】（复现正常结果）
    print("\n⑤ 反应中心")
    left = bonds_over_maps_all(raws)
    formed, broken = formed_broken(pm2, left)
    # 羧酸 + 胺 -> 酰胺：成 1 根 C-N 键，断 1 根 C-OH 键（脱去水）。这是正确的化学。
    check("得到 1 根成键（酰胺 C-N）", len(formed) == 1)
    check("断 1 根键（羧酸的 C-OH，脱水）", len(broken) == 1)
    print(f"       成键 {sorted(formed)}  断键 {sorted(broken)}")

    print()
    print("=" * 88)
    print(f"自检结果：通过 {ok}，失败 {fail}")
    print("=" * 88)
    raise SystemExit(1 if fail else 0)
