# -*- coding: utf-8 -*-
r"""修一个我自己埋的雷：3 条规则 priority 被压到 0.1，永远卡在激活门槛下。

【事故经过】
  第 8 轮我把 3 条规则标为 verify（待复核）时，顺手把 priority 压到 0.1：
      by_id[rid]["priority"] = min(float(...), 0.1)
  后来（第 13 轮）修好了 SMARTS，把 status 改回 active，
  **却忘了同时把 priority 恢复**。

  结果：这 3 条规则 priority=0.1 < 激活阈值 0.15，
        在【全部 10 种工艺】下都激活不了 —— 规则验证得再好，等于不存在。

【教训】
  把一条规则"降级"时改动的字段，恢复时要把它们当成一组一起恢复。
  只改 status 不改 priority，就会留下"永远不会触发"的僵尸规则。

【永久防护】
  已加 tools/check_never_active.py：扫描"在全部工艺下都激活不了"的规则。
  这类规则是【静默失效】—— 不报错、不告警，只是永远不出结果。
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

# 恢复到它们本来应有的优先级（依据：当初创建/修复时设定的值）
RESTORE = {
    "cyclization_hemiacetal_001": (0.5, "分子内半缩醛化：4-羟基丁醛→2-羟基四氢呋喃，已验证"),
    "cyclization_lactam_001": (0.4, "分子内酰胺化：4-氨基丁酸→γ-丁内酰胺，已验证"),
    "decarboxylation_cinnamic_001": (0.5, "肉桂酸型脱羧：肉桂酸/咖啡酸/阿魏酸，已验证"),
}

for rid, (prio, why) in RESTORE.items():
    r = by_id.get(rid)
    if r is None:
        print(f"[跳过] {rid} 不存在")
        continue
    old = r.get("priority")
    r["priority"] = prio
    r["notes"] = (r.get("notes", "") +
                  f" 【修复】priority 曾被压到 0.1（标 verify 时一并降级），"
                  f"但 status 恢复 active 时忘了同步恢复，导致永远卡在激活阈值 0.15 之下。"
                  f"现恢复为 {prio}。依据：{why}")
    print(f"[修] {r['name']:<18} priority {old} → {prio}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

low = [(r["name"], r.get("priority"), r.get("status"))
       for r in data["rules"]
       if r.get("status") == "active" and float(r.get("priority") or 0) < 0.15]
print()
print("仍有 active 但 priority < 0.15 的规则（会永远激活不了）：")
if low:
    for n, p, s in low:
        print(f"   {n:<22} priority={p}")
else:
    print("   （无）")
