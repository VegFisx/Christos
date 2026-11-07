# -*- coding: utf-8 -*-
r"""14 条 ORD 零命中规则的**离线**逐条核验报告。

输入：
  data\rules_provenance_ord.json
  data\rule_condition_examples.json
输出：
  reports\第七十五轮-14条零命中规则-离线核验.md

分类只描述“为什么这批抽样没命中”，不是对规则打分；行序 = rules.json 原序。
"""
from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
PROV = STAGE / "data" / "rules_provenance_ord.json"
COND = STAGE / "data" / "rule_condition_examples.json"
FP = STAGE / "data" / "rules_provenance_fp.json"
OUT = STAGE / "reports" / "第七十五轮-零命中规则-离线核验（修复后）.md"

# 离线判读（基于 mismatch_example 的底物/记录产物/条件，不是重新问 AI 自证）
NOTES = {
    "hydrolysis_hemiacetal_001": (
        "样本内无该反应",
        "触发的记录实际是 HWE 烯化（生成丙烯酸酯），不是半缩醛水解；记录没有水。",
        "保留；等外部文献确认半缩醛水解的适用条件。",
    ),
    "oxidation_phenol_quinone_001": (
        "样本内无该反应",
        "触发的记录实际是氯代/成盐，邻二酚没有被氧化；记录里没有氧化剂。",
        "保留；等外部文献或含氧化剂的 ORD 记录。",
    ),
    "reduction_quinone_001": (
        "已加环约束；抽样内仍无醌还原记录",
        "原 SMARTS 会把草酰氯 O=C(Cl)C(=O)Cl 的 O=C-C=O 当成醌；"
        "已加 ;R 环约束（邻苯醌/萘醌仍匹配，草酰氯/丁二酮不再触发）。"
        "60k 触发从 1,164 降到 117，但这条抽样里仍没有同产物记录。",
        "保留 active；等含醌还原的 ORD/文献记录。",
    ),
    "hydration_enone_001": (
        "样本内无该反应",
        "触发的记录实际是 Pd/C 加氢（C=C→CH-CH），不是水合；记录是甲醇、Pd/C。",
        "保留；等含水/酸催化的 ORD 记录。",
    ),
    "esterification_delta_lactone_001": (
        "近失：取代基",
        "内酯环确实生成了；规则产物保留 C(Cl)3，记录产物是 C(Cl)2（三氯甲基被还原）。",
        "环化中心有先例；差异在侧链，不应据此判规则错。",
    ),
    "oxidation_thiol_disulfide_001": (
        "禁用/空规则",
        "SMARTS `[S:1][H]>>[S:1]` 只映射一个 S，没有生成 S-S 键；当前 disabled。",
        "保持 disabled；要启用必须先重写为 2 个 S 的偶联模板。",
    ),
    "reduction_nitro_001": (
        "近失：质子化",
        "记录是 Pd/C、水、45°C 的硝基还原；实际产物是中性苯胺，规则生成的是 [NH3+]。",
        "建议把产物模板改成中性 [NX3;H2]，再重跑；这是可修的表示差异。",
    ),
    "cyclization_lactone_delta_001": (
        "近失：取代基",
        "与 `esterification_delta_lactone_001` 命中同一条记录；内酯环生成，侧链三氯甲基→二氯甲基。",
        "与上一条功能重叠；建议保留一条主规则，另一条标备用/禁用，避免重复枚举。",
    ),
    "condensation_aldol_intra_001": (
        "禁用/空规则",
        "抽样内 0 次触发；当前 disabled。",
        "保持 disabled；若启用需补测试底物和产物模板。",
    ),
    "elimination_decarboxylation_phenol_001": (
        "底物/条件不对",
        "触发的记录实际是 EDC 介导的酰胺缩合，不是酚酸脱羧；规则当前 disabled。",
        "保持 disabled；等有热脱羧条件的记录再评估。",
    ),
    "condensation_hemiacetal_001": (
        "样本内无该反应",
        "触发的记录实际是苯并呋喃环化，不是简单半缩醛；半缩醛常是瞬态中间体。",
        "保留；外部核验时优先找“可分离半缩醛”的记录。",
    ),
    "addition_thiohemiacetal_001": (
        "样本内无该反应",
        "触发的记录实际是 SOCl2 氯代，不是硫代半缩醛形成。",
        "保留；等有硫醇+醛的真实记录。",
    ),
    "decarboxylation_cinnamic_001": (
        "样本内无该反应",
        "触发的记录实际是肉桂酸的酰胺化，不是脱羧；记录没有热/铜条件。",
        "保留；外部核验时找加热/铜催化脱羧记录。",
    ),
    "esterification_paper_original_001": (
        "禁用/已知产物模板错误",
        "规则名已注明“产物模板有误”，当前 disabled；触发记录实际是酰胺缩合。",
        "保持 disabled；不要用于预测。",
    ),
}


def main() -> int:
    d = json.loads(PROV.read_text(encoding="utf-8"))
    rows = [r for r in d["rows"] if r.get("product_match", 0) == 0]
    cond = json.loads(COND.read_text(encoding="utf-8")).get("found", {})
    fp = {r["id"]: r for r in json.loads(FP.read_text(encoding="utf-8"))}

    classes = Counter()
    for r in rows:
        note = NOTES.get(r["id"])
        if not note:
            print("   [warn] 没有离线判读：%s" % r["id"])
            classes["未分类"] += 1
        else:
            classes[note[0]] += 1

    with OUT.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · ORD 零命中规则：离线核验（修复后）\n\n")
        f.write("> 对象：`data/rules_provenance_ord.json` 里当前 `product_match == 0` 的规则。\n")
        f.write("> **原 14 条**；`reduction_nitro_001` 改成中性苯胺后，60k 复核命中 **1,034 条**，"
                "已移出零命中清单。修复前报告保留在 "
                "`reports/第七十五轮-14条零命中规则-离线核验.md`。\n")
        f.write("> 方法：看该规则**触发但产物不符**的那条 ORD 记录（底物、真实产物、条件），"
                "区分“抽样里没有这个反应”与“规则/表示有问题”。\n")
        f.write("> **不打分、不排序**；这是离线判读，外部文献核验另做。\n\n")

        f.write("## 分类总览\n\n")
        for k, v in classes.most_common():
            f.write("* **%s**：%d 条\n" % (k, v))
        f.write("\n")
        f.write("说明：\n\n")
        f.write("* **样本内无该反应**：ORD 这条记录做的是别的反应，"
                "不能据此说规则错；需要外部文献/更多记录。\n")
        f.write("* **近失**：反应中心其实发生了，只是产物差一个质子/取代基；"
                "这类应算“有反应中心先例”，不是零证据。\n")
        f.write("* **SMARTS 过宽/空规则/禁用**：规则本身需要改或保持禁用。\n")
        f.write("* **底物/条件不对**：记录的反应类型与规则无关。\n\n")

        f.write("## 逐条\n\n")
        for i, r in enumerate(rows, 1):
            rid = r["id"]
            note = NOTES.get(rid, ("未分类", "", ""))
            cls, why, action = note
            ex = r.get("mismatch_example") or {}
            c = cond.get(ex.get("rid") or "", {})
            f.write("### %d. `%s` %s\n\n" % (i, rid, r.get("name", "")))
            f.write("* 论文档位：%s；状态：%s；结构证据：%s\n"
                    % (r.get("paper_tier", "?"), r.get("status", "?"),
                       fp.get(rid, {}).get("evidence", "?")))
            f.write("* ORD：fired=%d，product_match=0\n" % r.get("fired", 0))
            f.write("* 判定：**%s**\n" % cls)
            f.write("* 依据：%s\n" % why)
            f.write("* 建议：%s\n" % action)
            if ex.get("rid"):
                f.write("* 记录：`%s`\n" % ex["rid"])
                f.write("  * 反应物：`%s`\n" % " + ".join(ex.get("reactants") or []))
                f.write("  * 规则生成：`%s`\n" % (ex.get("generated") or "—"))
                f.write("  * 记录产物：`%s`\n" % " ; ".join(ex.get("actual") or []))
                f.write("  * 温度：%s；催化剂：%s；试剂：%s；溶剂：%s\n"
                        % (c.get("temp") or "—",
                           "、".join(c.get("catalysts") or []) or "—",
                           "、".join(c.get("reagents") or []) or "—",
                           "、".join(c.get("solvents") or []) or "—"))
            else:
                f.write("* 记录：抽样内没有触发（无 mismatch 样例）。\n")
            f.write("\n")

        f.write("## 需要动的规则（离线就能定）\n\n")
        f.write("1. `reduction_quinone_001`：**已改**，加环约束，避免草酰氯误触发。"
                "SMARTS 为 "
                "`[O:1]=[C;R:2][C;R:3]=[O:4]>>[OH:1][c:2][c:3][OH:4]`："
                "邻苯醌/1,2-萘醌能匹配，草酰氯/丁二酮不匹配。"
                "60k 触发从 1,164 降到 117；回归 0 失败；该规则仍是 0 条 ORD 产物命中。\n")
        f.write("2. `reduction_nitro_001`：**已修**。产物改成 `[NX3;H2;+0:1]` 后，"
                "60k 复核命中 1,034 条；规则仍保持 disabled，等启用前的配平/专项校验。\n")
        f.write("3. `oxidation_thiol_disulfide_001`：空模板，保持 disabled。\n")
        f.write("4. `cyclization_lactone_delta_001` 与 `esterification_delta_lactone_001` 功能重叠，"
                "建议保留一条主规则。\n")
        f.write("5. `esterification_paper_original_001`：已知产物模板错误，保持 disabled。\n\n")

        f.write("## 外部核验状态（B）\n\n")
        ext = [r for r in rows if NOTES.get(r["id"], ("",))[0] == "样本内无该反应"]
        for r in ext:
            f.write("* `%s` %s（%s）\n"
                    % (r["id"], r.get("name", ""), r.get("paper_tier", "?")))
        f.write("\nB 外部文献核验（2026-10-17）已完成：**6/6 找到至少一条直接文献支持**；"
                "详见 `reports/第七十五轮-规则外部文献核验.md`。\n")
        f.write("论文/软著里仍要写成“ORD 抽样内未见同产物记录；"
                "外部文献支持反应类型，具体条件/底物范围待验证”，"
                "不能写成“已由 ORD 验证”。\n")

        f.write("\n## 数据文件\n\n")
        f.write("* `data/rules_provenance_ord.json`（逐条计数与样例）\n")
        f.write("* `data/rule_condition_examples.json`（样例记录的条件原值）\n")
        f.write("* `reports/第七十五轮-规则条件样例.md`（条件表）\n")

    print("-> %s" % OUT)
    print("  零命中 %d 条；分类 %s" % (len(rows), dict(classes)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
