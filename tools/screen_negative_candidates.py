# -*- coding: utf-8 -*-
r"""第十三轮：反例候选【规则筛选】——先把明显的假阳性剔掉，再交人工/LLM 复核。

动机（实测）：人工复核 12 条里 5 条是假阳性，且集中在两类可规则化的模式：
  ① 后处理语境：'until no product was observed in the water layer' / 'extracted … until no product'
  ② 组分未消耗：'some of the zinc powder remained unreacted' / '14.0 grams of methanol was unreacted'
  ③ 弱反例（不是反例但有用）：'did not go to completion' / 'some starting material recovered' /
     补加试剂后才推进。

口径（写死）：
  strict = 明确"反应没发生/没有转化/没生成产物"，且上下文不是后处理、不是组分未消耗
  weak   = 部分转化 / 未完成 / 原料回收（可与产物共存）
  false  = 后处理语境、组分未消耗、或其实成功了
  B 路：真实 PERCENTYIELD==0 且**全部收率都为 0** -> b_zero（候选）；有非零收率 -> false

用法: python screen_negative_candidates.py
输出: reports/neg_screened_{strict,weak,false}.jsonl + reports/neg_screen_summary.json
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
A_IN = STAGE / "reports" / "negative_examples.jsonl"
B_IN = STAGE / "reports" / "negative_yield_zero.jsonl"
OUT = {k: STAGE / "reports" / f"neg_screened_{k}.jsonl" for k in ("strict", "weak", "false", "b_zero")}
SUMMARY = STAGE / "reports" / "neg_screen_summary.json"

WORKUP = re.compile(
    r"layer|extract|washed|wash |backwash|discard|filtrat|filtrate|chromatograph|elut|"
    r"quench|concentrat|partition|dried over|residue was", re.I)
WEAK = re.compile(
    r"did not go to completion|not complete|incomplete|partial|"
    r"some (?:of the )?starting material|starting material (?:was )?(?:recovered|remained|left)|"
    r"recovered|remaining solution|unreacted starting", re.I)
COMPONENT_UNREACTED = re.compile(
    r"([A-Za-z0-9\(\)\[\]\-]{3,40})\s+(?:powder\s+)?(?:was|were|remains?|remained)\s+unreacted",
    re.I)
SPARED = re.compile(r"starting material|sm\b", re.I)


def load(p):
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def label_a(rec):
    """返回 (label, why)。"""
    pats = set(rec.get("matched") or [])
    ctxs = [c.get("context", "") for c in (rec.get("contexts") or [])]
    ctx = " ".join(ctxs)
    # ③ 弱反例：先说清"没完成/部分/回收"，因为这些短语本身也含否定词
    if WEAK.search(ctx):
        return "weak", "部分转化/未完成/原料回收"
    # ② 组分未消耗（不是"反应没发生"）
    m = COMPONENT_UNREACTED.search(ctx)
    if m and not SPARED.search(m.group(0)):
        return "false", f"组分未消耗: {m.group(0)[:40]}"
    # ① 后处理语境
    if WORKUP.search(ctx):
        return "false", "后处理/萃取/纯化语境"
    if pats & {"no_reaction", "no_conversion", "did_not_react",
               "failed_to_react_or_give", "reaction_did_not_proceed"}:
        return "strict", "明确否定短语"
    if "no_product_formed" in pats:
        return "strict", "明确无产物"
    if "sm_recovered" in pats:
        return "weak", "原料回收"
    if "not_consumed" in pats:
        return "false", "组分未消耗"
    if "unreacted_remaining" in pats:
        return "false", "未消耗（非反应失败）"
    return "false", "无法判定"


def label_b(rec):
    vals = [y["value"] for y in (rec.get("all_yields") or []) if y["kind"] == "percentage"]
    if vals and max(vals) == 0:
        return "b_zero", "真实收率全为 0"
    return "false", f"存在非零收率 {max(vals) if vals else None}"


def main():
    A, B = load(A_IN), load(B_IN)
    files = {k: open(v, "w", encoding="utf-8") for k, v in OUT.items()}
    tally = Counter()
    why = Counter()
    try:
        for r in A:
            lab, w = label_a(r)
            tally[f"A:{lab}"] += 1
            why[f"A:{lab}:{w[:26]}"] += 1
            files[lab].write(json.dumps({**r, "label": lab, "label_why": w},
                                        ensure_ascii=False) + "\n")
        for r in B:
            lab, w = label_b(r)
            tally[f"B:{lab}"] += 1
            why[f"B:{lab}"] += 1
            files[lab].write(json.dumps({**r, "label": lab, "label_why": w},
                                        ensure_ascii=False) + "\n")
    finally:
        for f in files.values():
            f.close()

    summary = {"A_total": len(A), "B_total": len(B), "tally": dict(tally),
               "why": dict(why.most_common(24))}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 96)
    print(f"规则筛选：A 路 {len(A)} 条 / B 路 {len(B)} 条")
    print("=" * 96)
    for k in sorted(tally):
        print(f"  {k:<16} {tally[k]:>5}")
    print()
    print("  判定理由分布（前 12）：")
    for k, v in why.most_common(12):
        print(f"    {k:<44} {v:>5}")
    print()
    print(f"  strict + b_zero = {tally.get('A:strict',0) + tally.get('B:b_zero',0)} 条"
          f"  <- 交人工/LLM 复核的对象")
    print(f"  -> reports/neg_screened_*.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
