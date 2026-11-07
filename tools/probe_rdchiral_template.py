# -*- coding: utf-8 -*-
r"""查 rdchiral 内部用哪个模板做匹配——决定预筛该用哪个。

风险：如果我拿 RDKit 的原始模板预筛，而 rdchiral 用的是【清洗过】的模板，
      两者可能不一致 → 预筛会误杀本该匹配的组合。

必须先看清 rdchiralReaction 里有什么。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
for d in ("core", "conditions", "rules"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from rdchiral.main import rdchiralReaction, rdchiralRun, rdchiralReactants
from rdchiral.initialization import rdchiralReactants as RR2  # noqa

SM_AROM = "[OH:1][c:2]>>[O:1]=[c:2]"
SM_STEREO = "[C:1][C@H:2][OH:3]>>[C:1][C:2]=[O:3]"

for label, SM in (("无手性", SM_AROM), ("带手性", SM_STEREO)):
    print("=" * 96)
    print(f"【{label}】{SM}")
    print("=" * 96)
    rr = rdchiralReaction(SM)
    print("  rdchiralReaction 的属性:")
    for a in dir(rr):
        if a.startswith("_"):
            continue
        try:
            v = getattr(rr, a)
        except Exception:
            continue
        if a in ("reactant_template", "product_template", "reactant_template_list",
                 "product_template_list"):
            print(f"    {a}: {type(v).__name__}  = {str(v)[:90]}")
        elif callable(v):
            continue
        else:
            print(f"    {a}: {type(v).__name__}  = {str(v)[:70]}")

    # RDKit 原始模板
    rxn = AllChem.ReactionFromSmarts(SM)
    patt = rxn.GetReactantTemplate(0)
    print(f"  RDKit GetReactantTemplate(0): {Chem.MolToSmarts(patt)}")

    # rdchiral 用来匹配的模板
    tmpl = getattr(rr, "reactant_template", None)
    if tmpl is not None:
        if isinstance(tmpl, (list, tuple)):
            for t in tmpl:
                print(f"  rdchiral reactant_template: {Chem.MolToSmarts(t)}")
        else:
            print(f"  rdchiral reactant_template: {Chem.MolToSmarts(tmpl)}")

    # 拿几个底物比一比：两个模板的匹配结果是否一致
    TESTS = [
        ("苯酚", "Oc1ccccc1"),
        ("2-丙醇", "CC(C)O"),
        ("(R)-2-丁醇", "CC[C@@H](C)O"),
        ("(S)-2-丁醇", "CC[C@H](C)O"),
        ("无手性2-丁醇", "CCC(C)O"),
        ("苯甲醚", "COc1ccccc1"),
    ]
    print(f"  {'底物':<16}{'RDKit原始模板':>14}{'rdchiral模板':>14}  一致?")
    for nm, smi in TESTS:
        m = Chem.MolFromSmiles(smi)
        a = m.HasSubstructMatch(patt)
        b = None
        tm = getattr(rr, "reactant_template", None)
        if tm is not None:
            if isinstance(tm, (list, tuple)):
                b = any(m.HasSubstructMatch(t) for t in tm)
            else:
                b = m.HasSubstructMatch(tm)
        flag = "✓" if a == b else "★不一致★"
        print(f"  {nm:<16}{str(a):>14}{str(b):>14}  {flag}")
    print()
