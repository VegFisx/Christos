# -*- coding: utf-8 -*-
r"""验证「隐含氧化还原环境」门控：同一底物在 空气 / N2 / H2 下，产物是否被正确筛掉。

预期：
  · 苄胺  NCc1ccccc1
      - 空气：允许【需氧化】的模板（如 胺->腈，ΔH<0）→ 产出腈；**不允许**加氢模板
        → 不应再出现 `NCC1=CCC=CC1`（芳环加氢 = Birch 还原）
      - N2 / He / Ne / Ar ：两者都不允许 → 只剩 ΔH=0 的模板
      - H2 ：允许【需还原】的模板 → 可以出现加氢产物
  · 苯甲醇 -> 醛（ΔH<0，需氧化）：空气应有、N2 应无
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

PROBES = [("苄胺", "NCc1ccccc1", "N#Cc1ccccc1", "腈（需氧化）"),
          ("苯甲醇", "OCc1ccccc1", "O=Cc1ccccc1", "醛（需氧化）"),
          ("苯甲醛", "O=Cc1ccccc1", "OCc1ccccc1", "醇（需还原）")]

eng = SmartReactEngine(gate_conditions=True, use_extra_templates=False,
                       mono_redox_gate=True, strict_redox_gate=True,
                       verbose=False)   # ★ 生产预测路径显式启用严格气氛门控
print("=" * 100)
print("氧化还原气氛门控验证")
print("=" * 100)
print(eng.mono_template_note)
print()
for atm in ("air", "N2", "He", "Ne", "Ar", "H2"):
    cond = M.Conditions(solvent="water", temperature=100.0, time_min=60.0, atmosphere=atm)
    print(f"\n[气氛 {atm}]")
    for name, smi, want, label in PROBES:
        prods = eng.step([Compound(smiles=smi, name=name, herb="probe")], cond, 0.15, round_no=1)
        got = {mc.canon_plain(p.smiles) for p in prods}
        wc = mc.canon_plain(want)
        hydro = [p.smiles for p in prods if p.smiles.count("=") >= 2 and "c1ccccc1" not in p.smiles]
        print(f"   {name:<4} 产物 {len(prods):>3} 条   {label} {'✅ 有' if wc in got else '❌ 无'}"
              + (f"   加氢类产物 {len(hydro)} 条: {hydro[:2]}" if hydro else ""))
    print(f"      stats 跳过：需还原 {eng.stats.get('gated_zero_by_type', {})}；"
          f"gate_stats={ {k: v for k, v in eng.gate_stats.items() if '单底物' in k} }")
