# -*- coding: utf-8 -*-
r"""查清补这三样东西的技术缺口：
  ① 三组分以上  ② 分子内环化  ③ 多步级联

关键问题：
  · SmartReact 的底层模板是不是 RDKit ChemicalReaction？（能直接跑单分子/多分子吗）
  · 有没有单分子（intramolecular）的调用路径？
  · template_index / templates 的结构是什么？
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

enum = ReactionEnumerator()

print("=" * 90)
print("① API 签名")
print("=" * 90)
import inspect  # noqa: E402
for name in ("enumerate_pair", "enumerate_pairs", "enumerate_pairs_lazy", "products_for_pair"):
    fn = getattr(enum, name, None)
    if fn is None:
        continue
    try:
        print(f"   {name}{inspect.signature(fn)}")
    except Exception as ex:
        print(f"   {name}  (签名取不到: {ex})")

print()
print("=" * 90)
print("② templates / template_index 结构")
print("=" * 90)
t = enum.templates
ti = enum.template_index
print(f"   templates      : {type(t).__name__}", end="")
try:
    print(f"  len={len(t)}")
except Exception:
    print()
print(f"   template_index : {type(ti).__name__}", end="")
try:
    print(f"  len={len(ti)}")
except Exception:
    print()

# 取一条看结构
sample = None
if isinstance(t, dict):
    k0 = next(iter(t))
    print(f"   第一个 key : {k0!r}")
    print(f"   对应 value : {type(t[k0]).__name__}")
    sample = t[k0]
elif isinstance(t, (list, tuple)):
    sample = t[0]
    print(f"   第一个元素 : {type(sample).__name__}")

if sample is not None:
    print(f"   元素内容 : {str(sample)[:300]}")
    # 若是 dict/list，再看一层
    if isinstance(sample, dict):
        for k, v in list(sample.items())[:8]:
            print(f"        {k}: {type(v).__name__}  {str(v)[:110]}")
    elif isinstance(sample, (list, tuple)):
        for i, v in enumerate(sample[:6]):
            print(f"        [{i}] {type(v).__name__}  {str(v)[:110]}")

print()
print("=" * 90)
print("③ 能否直接对【单分子】跑模板？（分子内环化需要）")
print("=" * 90)
# 从 template_index 里挖出 RDKit ChemicalReaction
found_rxn = None
if isinstance(ti, dict):
    for k, v in list(ti.items())[:5]:
        print(f"   template_index[{str(k)[:40]!r}] -> {type(v).__name__}")
        if isinstance(v, (list, tuple)) and v:
            inner = v[0]
            print(f"        内层: {type(inner).__name__}  {str(inner)[:120]}")
            found_rxn = inner
        else:
            found_rxn = v
        break
elif isinstance(ti, (list, tuple)) and ti:
    found_rxn = ti[0]
    print(f"   template_index[0] -> {type(found_rxn).__name__}")

if found_rxn is not None:
    from rdkit.Chem.rdChemReactions import ChemicalReaction
    print(f"   是不是 RDKit ChemicalReaction: {isinstance(found_rxn, ChemicalReaction)}")
    if isinstance(found_rxn, ChemicalReaction):
        print(f"   底物模板数: {found_rxn.GetNumReactantTemplates()}")
        print(f"   产物模板数: {found_rxn.GetNumProductTemplates()}")

enum.close()
