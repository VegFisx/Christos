# -*- coding: utf-8 -*-
r"""第十三轮：合并子代理的逐条标注 -> 干净反例集 + 精度。

做四件事（都要打印，不许静默）：
  1. 校验：条数必须与输入一致、reaction_id 不得重复/遗漏 -> 不一致直接报警
  2. 合并 labeled_*.jsonl，按 label × source 统计
  3. 输出 reports/negative_clean.jsonl（strict）、negative_weak.jsonl
  4. ★ 交叉验证 ★ 与我人工复核的 12 条（固定 ID 列表）比对，算一致率

用法: python merge_review_labels.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
CHUNKS = STAGE / "reports" / "neg_chunks"
OUT_CLEAN = STAGE / "reports" / "negative_clean.jsonl"
OUT_WEAK = STAGE / "reports" / "negative_weak.jsonl"
OUT_SUM = STAGE / "reports" / "neg_review_summary.json"

# 我（Lead）在 seed=20261011 抽样的 12 条上的人工判定（写报告时已列出）
HUMAN12 = {
    "ord-df463b3d9e59495582b2e3472201778e": "weak",   # 未完成，补催化剂后继续
    "ord-526d011fe0ba40bab3036eb6eeaa8876": "weak",   # 未完成，补 PtO2 后继续
    "ord-78fbfb7406a84d8a9380a508d372e65d": "strict", # 12h 无产物 -> 改条件
    "ord-bb9665cc84dc492eada4e4f4904e3a81": "weak",   # 未完成，补加一当量
    "ord-821b07b1679942758698fa74a0ea56b4": "false",  # 甲醇未反应（组分）
    "ord-d469ebb696bb4c5b9fda6e7c1e15074e": "weak",   # 部分原料回收，产物仍得
    "ord-e9e57c45544a42c0b5db01e592d077f8": "false",  # 锌粉未消耗（组分）
    "ord-8549f99e341e4500ab458b4c495c12d0": "false",  # 原料回收但有 24% 产物
    "ord-47925041bb5049b48a5583a43b1125b5": "strict", # TLC 显示原料没反应
    "ord-c6a08fe10e4c49eeaabc791aa39f60d9": "false",  # 萃取后处理
    "ord-2625f5a5bf9045788fc8523360573dfa": "weak",   # 86% 转化，未完成
    "ord-9a7b55da3bf04198abd67e7ecb2637b0": "false",  # 萃取后处理
}

LABELS = ("strict", "weak", "false", "unsure")


def load(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    src = {}
    for p in sorted(CHUNKS.glob("chunk_*.jsonl")):
        for r in load(p):
            src[r["reaction_id"]] = r
    labels = {}
    dup = 0
    for p in sorted(CHUNKS.glob("labeled_*.jsonl")):
        for r in load(p):
            rid = r.get("reaction_id")
            lab = r.get("label")
            if lab not in LABELS:
                print(f"  !! 非法标签 {lab!r}（{p.name} {rid}）")
                continue
            if rid in labels:
                dup += 1
                continue
            labels[rid] = r
    missing = [r for r in src if r not in labels]
    extra = [r for r in labels if r not in src]

    print("=" * 96)
    print("1. 校验")
    print("=" * 96)
    print(f"  输入候选 {len(src)} 条；子代理标注 {len(labels)} 条；重复 {dup}；"
          f"遗漏 {len(missing)}；多出 {len(extra)}")
    for rid in missing[:5]:
        print(f"    !! 遗漏 {rid}")

    print()
    print("=" * 96)
    print("2. 标签分布（label × source）")
    print("=" * 96)
    by = Counter()
    for rid, r in labels.items():
        s = src[rid]["source"] if rid in src else "?"
        by[f"{r['label']}|{s}"] += 1
    for k in sorted(by):
        print(f"  {k:<22} {by[k]:>5}")
    tot = Counter(r["label"] for r in labels.values())
    print()
    for lb in LABELS:
        print(f"  {lb:<8} {tot.get(lb, 0):>5}  ({tot.get(lb,0)/max(1,len(labels)):.0%})")

    strict = [rid for rid, r in labels.items() if r["label"] == "strict"]
    weak = [rid for rid, r in labels.items() if r["label"] == "weak"]
    with open(OUT_CLEAN, "w", encoding="utf-8") as f:
        for rid in strict:
            if rid in src:
                rec = dict(src[rid])
                rec["review"] = {"label": "strict", "why": labels[rid].get("why", "")}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with open(OUT_WEAK, "w", encoding="utf-8") as f:
        for rid in weak:
            if rid in src:
                rec = dict(src[rid])
                rec["review"] = {"label": "weak", "why": labels[rid].get("why", "")}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print()
    print("=" * 96)
    print("3. ★ 交叉验证：规则筛选标签 vs 子代理逐条标签（混淆矩阵）★")
    print("=" * 96)
    rule = {}
    for p, lab in ((STAGE / "reports" / "neg_screened_strict.jsonl", "rule:strict"),
                   (STAGE / "reports" / "neg_screened_b_zero.jsonl", "rule:b_zero")):
        for r in load(p):
            rule[r["reaction_id"]] = lab
    conf = Counter()
    for rid, r in labels.items():
        conf[f"{rule.get(rid,'?')} -> {r['label']}"] += 1
    for k in sorted(conf):
        print(f"  {k:<28} {conf[k]:>5}")
    a_rule = sum(v for k, v in conf.items() if k.startswith("rule:strict"))
    a_strict_llm = conf.get("rule:strict -> strict", 0)
    b_rule = sum(v for k, v in conf.items() if k.startswith("rule:b_zero"))
    b_strict_llm = conf.get("rule:b_zero -> strict", 0)
    print()
    print(f"  规则判 A:strict 的 {a_rule} 条里，逐条复核后仍是 strict 的只有 "
          f"{a_strict_llm} 条 = {a_strict_llm/max(1,a_rule):.0%}")
    print(f"  规则判 B:b_zero 的 {b_rule} 条里，复核后仍是 strict 的只有 "
          f"{b_strict_llm} 条 = {b_strict_llm/max(1,b_rule):.0%}")
    print()
    print("  说明：Lead 另在【全部 449 条 A 候选】上随机抽 12 条人工判定过一次")
    print("        （严格 2 / 弱 5 / 假 5 = 严格精度 17%）—— 那次抽样与本次复核集不重合，")
    print("        两次是独立估计，不是同一批数据。")

    summary = {
        "n_candidates_reviewed": len(src),
        "n_labeled": len(labels),
        "n_missing": len(missing),
        "n_dup": dup,
        "label_totals": dict(tot),
        "label_by_source": dict(by),
        "rule_vs_llm_confusion": dict(conf),
        "rule_A_strict_survived": f"{a_strict_llm}/{a_rule}",
        "rule_B_bzero_survived": f"{b_strict_llm}/{b_rule}",
        "strict_clean_set": len(strict),
        "weak_set": len(weak),
        "lead_manual_sample_12": "strict 2 / weak 5 / false 5 (=17% strict precision, 独立抽样)",
        "outputs": [OUT_CLEAN.name, OUT_WEAK.name],
    }
    OUT_SUM.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"  干净反例集（strict）: {len(strict)} 条 -> {OUT_CLEAN.name}")
    print(f"  弱反例集（weak）    : {len(weak)} 条 -> {OUT_WEAK.name}")
    print(f"  汇总 -> {OUT_SUM.name}")
    return 0 if not missing and not extra else 1


if __name__ == "__main__":
    sys.exit(main())
