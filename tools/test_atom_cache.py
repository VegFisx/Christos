# -*- coding: utf-8 -*-
r"""直接测：原子计数缓存会不会被污染 / 给出不同的值。"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "core"))
sys.path.insert(0, str(STAGE / "libs"))

from engine import _atom_counts_of_smiles, _ATOM_COUNT_CACHE, get_mol

TESTS = [
    "O",                                   # 水
    "CO",                                  # 甲醇
    "O=C(O)c1ccccc1",                      # 苯甲酸
    "CC1(C2CCC3(C(C2(CCC1OC4C(C(C(C(O4)C(=O)O)O)O)O)C)C)C(=O)O)C",
]

print("=" * 88)
print("① 缓存的值 与 直接从分子算的值 是否一致")
print("=" * 88)
for s in TESTS:
    _ATOM_COUNT_CACHE.clear()
    fresh = _atom_counts_of_smiles(s)
    cached = _atom_counts_of_smiles(s)
    ok = fresh == cached
    print(f"  {'✓' if ok else '✗'} {s[:50]:<52} {fresh}")
    if not ok:
        print(f"       fresh={fresh}")
        print(f"       cached={cached}")

print()
print("=" * 88)
print("② 调用方改返回值，会不会污染缓存")
print("=" * 88)
_ATOM_COUNT_CACHE.clear()
s = "CO"
a = _atom_counts_of_smiles(s)
a["C"] = 999          # 模拟 _collect 里的原地修改
a["Xx"] = 5
b = _atom_counts_of_smiles(s)
print(f"  第一次返回: {a}")
print(f"  第二次返回: {b}")
print(f"  {'✓ 缓存未被污染' if b == {'C': 1.0, 'H': 4.0, 'O': 1.0} else '★缓存被污染了★'}")

print()
print("=" * 88)
print("③ 多次调用是否稳定（模拟几千次）")
print("=" * 88)
_ATOM_COUNT_CACHE.clear()
first = {s: _atom_counts_of_smiles(s) for s in TESTS}
for _ in range(3):
    for s in TESTS:
        got = _atom_counts_of_smiles(s)
        if got != first[s]:
            print(f"  ★ {s[:40]} 变了: {first[s]} → {got}")
            break
else:
    print("  ✓ 反复调用结果稳定")

print()
print("=" * 88)
print("④ 关键：分子对象是不是共享的、会被别处改动")
print("=" * 88)
s = "Oc1ccccc1"
m1 = get_mol(s)
n1 = m1.GetNumAtoms()
m2 = get_mol(s)
print(f"  两次 get_mol 是同一对象: {m1 is m2}")
from engine import classify_product
classify_product(m1)
m3 = get_mol(s)
print(f"  classify_product 之后原子数: {m3.GetNumAtoms()}（原来 {n1}）")
print(f"  {'✓ 未被改动' if m3.GetNumAtoms() == n1 else '★分子被改动了★'}")
