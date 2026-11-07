# -*- coding: utf-8 -*-
r"""验证【单底物模板】真的接进引擎了：用三个有明确化学预期的探针，对比 开/关。

预期（来自 mined_mono_templates.jsonl 里 support 较高的自给自足模板）：
  · 苄胺  NCc1ccccc1      -> 腈 N#Cc1ccccc1        （模板 [NH2]-[CH2]-[c] >> [N]#[C]-[c]）
  · 苯甲醇 OCc1ccccc1     -> 醛 O=Cc1ccccc1        （模板 [OH]-[CH2]-[c] >> [O]=[CH]-[c]）
  · 苯甲醛 O=Cc1ccccc1    -> 醇 OCc1ccccc1         （模板 [C]-[CH]=O >> [C]-[CH2]-[OH]）
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "sources", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from smartreact_engine import SmartReactEngine    # noqa: E402
from engine import Compound                       # noqa: E402
import model as M                                 # noqa: E402
import mapped_chem as mc                          # noqa: E402

COND = M.Conditions(solvent="water", temperature=100.0, time_min=60.0)
PROBES = [
    ("苄胺", "NCc1ccccc1", "N#Cc1ccccc1", "腈"),
    ("苯甲醇", "OCc1ccccc1", "O=Cc1ccccc1", "醛"),
    ("苯甲醛", "O=Cc1ccccc1", "OCc1ccccc1", "醇"),
]

print("=" * 96)
print("单底物模板接入验证")
print("=" * 96)
for mono in (False, True):
    eng = SmartReactEngine(gate_conditions=True, use_extra_templates=False,
                           use_mono_templates=mono, verbose=False)
    print(f"\n[use_mono_templates={mono}]  {eng.mono_template_note}")
    for name, smi, want, want_label in PROBES:
        prods = eng.step([Compound(smiles=smi, name=name, herb="probe")], COND, 0.15, round_no=1)
        got = {mc.canon_plain(p.smiles) for p in prods}
        wc = mc.canon_plain(want)
        rule_names = sorted({p.rule_name for p in prods})
        print(f"   {name:<4} 产物 {len(prods):>3} 条  规则 {rule_names}")
        for p in prods[:6]:
            tag = "  ← 期望产物" if mc.canon_plain(p.smiles) == wc else ""
            print(f"        [{p.rule_name:<12}] {p.smiles[:64]}{tag}")
        print(f"        期望的{want_label} {'✅ 出现' if wc in got else '❌ 未出现'}")
