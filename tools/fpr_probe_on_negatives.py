# -*- coding: utf-8 -*-
r"""第十三轮：在 17 条【干净反例】上量第一个假阳性率数据点。

口径（写死，别事后改）：
  样本 = reports/negative_clean.jsonl（子代理逐条复核后仅剩的 17 条"反应确实没发生"）
  做法 = 取该 ORD 记录的 CXSMILES 反应物（去原子映射）当输入，
         用正向引擎（**关掉条件门控**，只看"这些底物放在一起会不会生成它"）跑一轮，
         看是否预测出**文献说没生成的那个产物**。
  假阳性 = 引擎预测出了它（文献说没发生）。
  ⚠ 局限（写清楚）：样本只有 17 条、且彼此反应类型/条件都不同；
    不带条件门控 -> 测的是"形式预测"而非"条件正确性"。
    所以这是**第一个数据点，不是统计意义上的 FPR**。

用法: python fpr_probe_on_negatives.py
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
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "tools"):
    sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

from engine import Compound  # noqa: E402
from smartreact_engine import SmartReactEngine  # noqa: E402

CLEAN = STAGE / "reports" / "negative_clean.jsonl"


def canon(smi):
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m, isomericSmiles=False)


def main():
    recs = [json.loads(l) for l in CLEAN.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"样本：{len(recs)} 条干净反例（reports/negative_clean.jsonl）")
    eng = SmartReactEngine(gate_conditions=False)
    tally = Counter()
    rows = []
    for r in recs:
        rid = r["reaction_id"]
        cx = (r.get("cxsmiles") or "").split("|", 1)[0]
        parts = cx.split(">")
        if len(parts) != 3:
            tally["CXSMILES段数异常"] += 1
            continue
        lhs, _agents, rhs = parts
        rs = [p for p in lhs.split(".") if p.strip()]
        ps = [p for p in rhs.split(".") if p.strip()]
        r_canon = [c for c in (canon(x) for x in rs) if c]
        p_canon = {c for c in (canon(x) for x in ps) if c}
        if len(r_canon) < 2 or not p_canon:
            tally["输入不足(反应物<2或无产物)"] += 1
            continue
        comps = [Compound(smiles=s, name=f"r{i}", herb="neg") for i, s in enumerate(r_canon)]
        try:
            prods = eng.step(comps, None)
        except Exception as e:
            tally[f"引擎异常:{type(e).__name__}"] += 1
            continue
        got = {canon(p.smiles) for p in prods if p.smiles}
        got.discard(None)
        hit = sorted(p_canon & got)
        # ★ 对照：引擎在这批反应物上到底有没有产出任何候选？★
        #   若 n_any == 0，说明"没预测出那个产物"只是因为没规则可用，
        #   这个 0% 假阳性率是【无信息】的，不能当好消息。
        n_any = len(got)
        if hit:
            tally["假阳性(预测出该产物)"] += 1
            rows.append((rid, "FP", hit[0][:60], r.get("source"), n_any))
        else:
            tally["未预测出(不算假阳性)"] += 1
            tally["其中_引擎本来就没产出任何候选"] += 1 if n_any == 0 else 0
            rows.append((rid, "ok", f"引擎候选产物 {n_any} 个", r.get("source"), n_any))
    print()
    print("=" * 96)
    print("结果")
    print("=" * 96)
    n_eval = tally["假阳性(预测出该产物)"] + tally["未预测出(不算假阳性)"]
    for k in ("假阳性(预测出该产物)", "未预测出(不算假阳性)", "输入不足(反应物<2或无产物)",
              "CXSMILES段数异常", "其中_引擎本来就没产出任何候选"):
        if tally.get(k):
            print(f"  {k:<28} {tally[k]:>3}")
    for k, v in tally.items():
        if k.startswith("引擎异常"):
            print(f"  {k:<28} {v:>3}")
    print()
    for rid, tag, smi, src, n_any in rows:
        print(f"    {tag:<3} {rid}  ({src})  引擎候选 {n_any:>3}  {smi}")
    print()
    if n_eval:
        print(f"  可评估 {n_eval} 条；假阳性 {tally['假阳性(预测出该产物)']} 条 "
              f"= {tally['假阳性(预测出该产物)']/n_eval:.0%}")
        with_any = n_eval - tally["其中_引擎本来就没产出任何候选"]
        print(f"  其中【引擎产出了至少一个候选产物】的只有 {with_any}/{n_eval} 条")
        if with_any:
            print(f"  在有效分母（{with_any} 条）上，假阳性 = "
                  f"{tally['假阳性(预测出该产物)']}/{with_any}")
        else:
            print("  !! 全部 17 条引擎都没有产出任何候选 -> 这个 0% 假阳性率【无信息】，"
                  "不能当'引擎不会误报'的证据")
    print("  ⚠ 这是第一个数据点，不是统计意义上的假阳性率（样本 17 条、不带条件门控）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
