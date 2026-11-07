# -*- coding: utf-8 -*-
r"""
修：移除「煎煮里不可能存在」的陪跑试剂
========================================

审计发现（tools/audit_cosubstrates.py）4 条规则的池子里有【氨(N)】和【甲胺(CN)】，
且 when_solvent=None（六种工艺下永远可用）：

    席夫碱生成 / 酰胺化(分子间) / 酯的氨解 / Michael加成(胺)

后果：**给每个方剂凭空造出 N-甲基酰胺、亚胺等产物**。
      实测煎煮下苯甲酸 → CNC(=O)c1ccccc1（N-甲基苯甲酰胺）。

★ 判据不是"我觉得"，而是"煎煮水里有没有" ★
  氨、甲胺：煎煮水里没有        → 移除
  甘氨酸 NCC(=O)O：药材游离氨基酸 → 保留
  半胱氨酸 NC(CS)C(=O)O：药材氨基酸 → 保留
  乙醇/甲醇：醇提才有，已有 when_solvent → 保留
"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
F = STAGE / "rules" / "rules.json"

# 明确移除的（煎煮水里不可能凭空出现）
REMOVE = {"N", "CN"}
# 备注里写清理由
NOTE = ("【修复】原池子含【氨(N)/甲胺(CN)】且 when_solvent=None，"
        "导致六种工艺下都能凭空生成 N-甲基酰胺/亚胺类产物"
        "（煎煮水里既无氨也无甲胺）。已移除，保留药材真实存在的甘氨酸/半胱氨酸。"
        "审计见 tools/audit_cosubstrates.py")

d = json.loads(F.read_text(encoding="utf-8"))
rules = d["rules"]
changed = []
for r in rules:
    pool = r.get("co_substrate_pool")
    if not pool:
        continue
    kept = []
    removed = []
    for it in pool:
        smi = (it or {}).get("smiles")
        if smi in REMOVE:
            removed.append(smi)
        else:
            kept.append(it)
    if removed:
        r["co_substrate_pool"] = kept
        if NOTE not in (r.get("notes") or ""):
            r["notes"] = ((r.get("notes") or "").rstrip() + " " + NOTE).strip()
        changed.append((r["name"], removed, [k.get("smiles") for k in kept]))

F.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("已修改的规则：")
for nm, rm, kept in changed:
    print(f"  {nm:<22}移除 {rm}   剩余 {kept}")
print()
print(f"共 {len(changed)} 条规则")

# 复查
print()
print("复查：全库还有没有 when_solvent=None 的氨/甲胺：")
bad = []
for r in rules:
    for it in (r.get("co_substrate_pool") or []):
        if (it or {}).get("smiles") in REMOVE:
            bad.append((r["name"], it.get("smiles"), it.get("when_solvent")))
if bad:
    print(f"  ★ 仍有 {len(bad)} 处: {bad}")
else:
    print("  ✓ 已清空")
