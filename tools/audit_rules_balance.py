# -*- coding: utf-8 -*-
"""规则行为审计：在 73 条反应级用例上跑经典引擎，检查配平/自身产物/期望产物。

判据：
  · balance_dropped 增加 > 0 -> 规则按声明配不平（经典引擎守卫会丢产物）
  · 产物包含底物本身 -> 自身反应/空转
  · 期望产物缺失 -> 规则没在用例上工作

注意：经典引擎有原子守恒守卫，smartreact 路径没有；本审计用经典引擎的守卫
把「按 co_reagents/byproducts 声明配不平」的规则找出来。
"""
from __future__ import annotations

import sys
from collections import defaultdict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = r"D:\ProgramData\DSHNS\chemreact-staging"
for p in (ROOT + r"\core", ROOT + r"\tools", ROOT + r"\conditions",
          ROOT + r"\libs", ROOT + r"\rules"):
    if p not in sys.path:
        sys.path.insert(0, p)

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import test_reaction_cases as TRC  # noqa: E402
from engine import Compound  # noqa: E402


def main() -> int:
    rows = []
    for c in TRC.CASES:
        if c.get("kind") != "rule":
            continue
        rid = c.get("rule")
        r = TRC.by_id.get(rid)
        if r is None:
            rows.append((rid, "NO_RULE", 0, False, False))
            continue
        try:
            smi = TRC.mol_of(c["smiles"])
            mol = Chem.MolFromSmiles(smi)
        except Exception as ex:
            rows.append((rid, "BAD_SMILES:%s" % type(ex).__name__, 0, False, False))
            continue
        if mol is None:
            rows.append((rid, "BAD_SMILES", 0, False, False))
            continue
        cond = TRC.T.get_template(c.get("conditions") or "煎煮")
        if not getattr(cond, "template", ""):
            from dataclasses import replace as _dc
            cond = _dc(cond, template=str(c.get("conditions") or "煎煮"))
        act = {rr["id"]: s for rr, s, _ in TRC.active_rules(
            TRC.rules, TRC.profiles, cond)}
        score = act.get(rid)
        if score is None:
            rows.append((rid, "INACTIVE", 0, False, False))
            continue
        before = int(getattr(TRC.engine, "balance_dropped", 0) or 0)
        try:
            prods = TRC.engine.apply_rule(
                r, Compound(smiles=smi, name=c.get("name", "case"), herb="test"),
                score, 1, cond)
        except Exception as ex:
            rows.append((rid, "RUN_FAIL:%s" % type(ex).__name__, 0, False, False))
            continue
        after = int(getattr(TRC.engine, "balance_dropped", 0) or 0)
        got = {TRC.canon(p.smiles) for p in prods if p.smiles}
        got.discard(None)
        want = {TRC.canon(TRC.mol_of(s)) for s in (c.get("expect_any") or [])}
        want.discard(None)
        identity = TRC.canon(smi) in got
        hit = bool(want & got)
        rows.append((rid, "ok", after - before, identity, hit))

    by_rule = defaultdict(list)
    for rid, note, drop, ident, hit in rows:
        by_rule[rid].append((note, drop, ident, hit))

    bad = []
    for rid, items in by_rule.items():
        drops = sum(x[1] for x in items)
        ident = any(x[2] for x in items)
        miss = any(not x[3] and x[0] == "ok" for x in items)
        notes = sorted({x[0] for x in items if x[0] != "ok"})
        if drops or ident or miss or notes:
            bad.append((rid, drops, ident, miss, notes))

    print("规则用例 %d 条，覆盖规则 %d 条" % (len(rows), len(by_rule)))
    if not bad:
        print("行为审计：0 条异常（配平/自身/期望产物全部通过）")
        return 0
    print("异常规则 %d 条：" % len(bad))
    for rid, drops, ident, miss, notes in sorted(bad):
        flags = []
        if drops:
            flags.append("配平丢弃 %d" % drops)
        if ident:
            flags.append("产物含底物自身")
        if miss:
            flags.append("期望产物缺失")
        if notes:
            flags.append(",".join(notes))
        print("  %-42s %s" % (rid, " · ".join(flags)))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
