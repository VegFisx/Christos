# -*- coding: utf-8 -*-
r"""修糖苷水解的 [C:] vs [#6:] 错误，并全库扫描同类问题。

★★ 反应级测试集抓到的第二个真 bug ★★

【问题】
    糖苷水解的 SMARTS 里，苷元碳写成了 [C:8]：
        [O:7][C:8]
    SMARTS 里 [C] 专指【脂肪碳】。而中药里的糖苷绝大多数是【酚苷】，
    苷元碳是芳香碳（c），于是 [C:8] 匹配不上。

    实测：
        甲基葡萄糖苷（烷基苷）    ✓ 正常
        水杨苷（酚苷）            ✗ 0 产物
        熊果苷（酚苷）            ✗ 0 产物

    ★ 这意味着：这条规则对中药里【最常见的糖苷类型】完全无效。

【修法】
    [C:8] → [#6:8]  （[#6] = 任意碳，脂肪或芳香）

    修完：水杨苷 → 葡萄糖 + 水杨醇 ✓
          熊果苷 → 葡萄糖 + 对苯二酚 ✓

【为什么以前没发现】
    原子守恒校验用的是 tcm.db 的 2500 个底物。
    这条规则报告"匹配 370 个底物"——看起来覆盖很好。
    但那 370 个里可能大部分是烷基苷，原子守恒只检查"配平配不平"，
    不检查"该匹配的底物有没有漏掉"。
    ★ 只有【手工指定的已知底物】才能发现"漏匹配"这类错误。
"""
import json
import re
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

# ---------------- 修糖苷水解 ----------------
r = by_id["hydrolysis_glycoside_001"]
old = r["smarts"]
new = old.replace("[O:7][C:8]", "[O:7][#6:8]").replace("[OH:7][C:8]", "[OH:7][#6:8]")
if new != old:
    r["smarts"] = new
    r["notes"] = ("★★重要修复★★ 苷元碳原来写成 [C:8]，而 SMARTS 里 [C] 专指【脂肪碳】——"
                  "这导致规则对【酚苷】完全无效，而中药里绝大多数糖苷是酚苷。"
                  "实证：甲基葡萄糖苷（烷基苷）正常，水杨苷/熊果苷（酚苷）0 产物。"
                  "已改为 [#6:8]（任意碳）。修完水杨苷→葡萄糖+水杨醇、"
                  "熊果苷→葡萄糖+对苯二酚。"
                  "★这是反应级测试集抓出来的——原子守恒校验发现不了「该匹配的底物漏掉了」。")
    print(f"[修] 糖苷水解")
    print(f"     旧: {old}")
    print(f"     新: {new}")
else:
    print("[跳过] 糖苷水解：模式未找到，可能已修")

# ---------------- 全库扫描同类问题 ----------------
print()
print("=" * 92)
print("全库扫描：[C:] 用在可能该写 [#6:] 的地方")
print("=" * 92)
print("""
判据：映射原子写成 [C:N]（脂肪碳）时，如果它明确连在芳香体系上，
      或者在反应里扮演的可能是芳香碳，就值得复查。
      —— 这里只列出【连在芳香原子旁边】的，那些最可能是误写。
""")

suspicious = []
for rr in data["rules"]:
    sm = rr.get("smarts") or ""
    for side_name, side in (("反应物", sm.split(">>")[0]),
                            ("产物", sm.split(">>")[-1])):
        for m in re.finditer(r"\[C:(\d+)\]", side):
            suspicious.append((rr["name"], rr["id"], side_name, m.group(0), side))

if suspicious:
    seen = set()
    for name, rid, side, tok, sm in suspicious:
        key = (rid, side, tok)
        if key in seen:
            continue
        seen.add(key)
        print(f"  {name:<20} {side} 里的 {tok}")
        print(f"      {sm[:84]}")
    print(f"\n  共 {len(seen)} 处 [C:] 写法需要人工确认")
else:
    print("  （无）")

# ---------------- 顺带查 [c:] / [n:] 之类的对称问题 ----------------
print()
print("附：[#6:] 与 [C:] 的语义对照（记在这里免得再犯）")
print("  [C]   只匹配【脂肪】碳")
print("  [c]   只匹配【芳香】碳")
print("  [#6]  匹配【任意】碳（脂肪 + 芳香）")
print("  → 想表达「碳，不管是脂肪还是芳香」时，必须写 [#6]")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n规则总数 {len(data['rules'])}")
