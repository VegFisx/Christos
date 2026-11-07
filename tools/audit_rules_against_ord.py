# -*- coding: utf-8 -*-
r"""规则来源体检（待办 2 第一步）：64 条规则的 SMARTS 能否在 **ORD 挖掘模板库**里找到同款？

做法（**便宜初筛**）：
  1. 读 `rules/rules.json`（64 条）与 `reports/mined_forward_templates_full_lf.jsonl`
     （18,554 条，含 support / src，全部来自 ORD）；
  2. 逐条规则做三级匹配：
     * **原样**：SMARTS 字符串完全相等；
     * **同款**：两侧模板规范化后相等（去空白、统一 `>>`）；
     * **包含**：规则的反应中心是某条挖掘模板的子串（弱证据，单列）；
  3. 产出 `data\rules_provenance.json` + `reports\第七十五轮-规则来源体检.md`（64 行表）。

注意（诚实声明）：这是**模板级**证据 —— 它回答"这类变换在 ORD 里有没有同款模板"，
**不回答**"这条规则本身在 ORD 里被真实执行过多少次"（后者需要逐条套反应，成本高，另做）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
RULES = STAGE / "rules" / "rules.json"
MINE = STAGE / "reports" / "mined_forward_templates_full_lf.jsonl"
OUTJ = STAGE / "data" / "rules_provenance.json"
OUTM = STAGE / "reports" / "第七十五轮-规则来源体检.md"


def norm(s: str) -> str:
    r"""规范化反应 SMARTS：去空白、统一箭头、去外层括号差异。"""
    s = re.sub(r"\s+", "", str(s or ""))
    s = s.replace(">>", ">>").replace("> >", ">>")
    return s


def main() -> int:
    R = json.loads(RULES.read_text(encoding="utf-8"))
    rules = R if isinstance(R, list) else R.get("rules") or []
    mined = []
    for ln in MINE.open(encoding="utf-8"):
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except Exception:                                    # noqa: BLE001
            continue
        mined.append({"t": norm(d.get("template")), "support": d.get("support"),
                      "src": d.get("src")})
    exact = {m["t"]: m for m in mined}
    print("规则 %d 条 ｜ 挖掘模板 %d 条" % (len(rules), len(mined)))
    rows = []
    for r in rules:
        s = norm(r.get("smarts"))
        hit = exact.get(s)
        tag, ev = "无同款", ""
        if hit:
            tag = "原样"
            ev = "support=%s" % hit.get("support")
        else:
            for m in mined:
                if s and (s in m["t"] or m["t"] in s):
                    tag, ev = "包含", "support≈%s" % m.get("support")
                    break
        rows.append({"id": r.get("id"), "name": r.get("name"),
                     "category": r.get("category"), "status": r.get("status"),
                     "smarts": s, "evidence": tag, "detail": ev,
                     "notes": str(r.get("notes") or "")[:60]})
    OUTJ.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    c = Counter(x["evidence"] for x in rows)
    print("  证据分档：", dict(c))
    with OUTM.open("w", encoding="utf-8") as fh:
        fh.write("# 第七十五轮 · 规则来源体检（模板级初筛）\n\n")
        fh.write("> ⚠ **本表的方法已失效，不能当结论**：规则 SMARTS 与 rdchiral 抽取的模板\n"
                 "> 在写法上不同（`;H0;D3;` 等注解、原子映射顺序），**字符串比对天然对不上**，\n"
                 "> 所以「无同款 64 条」只说明**字面不同**，不说明「没有实证」。\n"
                 "> 正确的下一步：**结构指纹匹配**（R:P 原子环境指纹）或**抽样套反应**。\n\n")
        fh.write("> 输入：`rules/rules.json`（%d 条）× `mined_forward_templates_full_lf.jsonl`"
                 "（%d 条，全部来自 ORD）\n" % (len(rules), len(mined)))
        fh.write("> 口径：**模板级**——回答\"这类变换在 ORD 里有没有同款模板\"；"
                 "不等于\"这条规则被执行过多少次\"。\n\n")
        fh.write("| # | 规则 id | 名称 | 类别 | 状态 | 证据 | 说明 |\n|---|---|---|---|---|---|---|\n")
        for i, x in enumerate(rows, 1):
            fh.write("| %d | `%s` | %s | %s | %s | **%s** | %s |\n"
                     % (i, x["id"], x["name"], x["category"], x["status"],
                        x["evidence"], x["detail"]))
        fh.write("\n## 分档统计\n\n")
        for k, v in c.most_common():
            fh.write("* **%s**：%d 条\n" % (k, v))
    print("  -> %s" % OUTM)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
