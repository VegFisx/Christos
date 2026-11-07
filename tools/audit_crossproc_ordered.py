# -*- coding: utf-8 -*-
r"""
跨进程审计 · 升级版：比对【有序输出】，不只是集合
====================================================

★ 为什么必须升级

  第 26 轮的跨进程审计用的是 `sha256("\n".join(sorted(set)))` ——
  只比对【集合】，**抓不到输出顺序的差异**。

  但用户看到的是一份【有序清单】：
    · 产物按分数排序（Top-20 / Top-N 展示）
    · 来源追溯里的"来自哪个成分"
  顺序错了，用户拿到的结论就不同。

★ 本次比对 5 个层面

  ① engine.step       产物【有序序列】
  ② cascade           级联产物【有序序列】+ 轮次
  ③ find_final_products 兼容层输出【有序序列】
  ④ 多样性排序 Top-20  【有序序列】
  ⑤ 条件激活的规则顺序

每个层面都在【独立子进程】里跑，比对 SHA256。
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import textwrap
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PY = r"D:\TCMAI\venv\Scripts\python.exe"
N = 5
if "--n" in sys.argv:
    try:
        N = max(2, int(sys.argv[sys.argv.index("--n") + 1]))
    except (IndexError, ValueError):
        pass

DRIVER = STAGE / "tools" / "_ordered_probe.py"

DRIVER_SRC = textwrap.dedent(r'''
    # -*- coding: utf-8 -*-
    import hashlib, json, sys
    from pathlib import Path
    STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
    sys.path.insert(0, r"D:\TCMAI\src")
    sys.path.insert(0, str(STAGE / "api"))
    for d in ("core","conditions","rules","libs","sources"):
        p = STAGE/d
        if p.is_dir(): sys.path.insert(0, str(p))
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.error"); RDLogger.DisableLog("rdApp.warning")
    from engine import Compound, get_mol, load_engine
    from cascade import cascade
    import templates as T
    from activator import active_rules
    import compat
    from tcm_ro import use_readonly; use_readonly()
    from db_utils import find_compounds

    def canon(s):
        m = Chem.MolFromSmiles(s) if s else None
        return Chem.MolToSmiles(m) if m else None

    eng, rules, profs = load_engine()
    cond = T.get_template("煎煮")
    import os
    QUICK = os.environ.get("DSH_QUICK") == "1"
    HERBS = ("甘草",) if QUICK else ("甘草","附子")
    PER = 8 if QUICK else 12
    comps = []
    for h in HERBS:
        for r in find_compounds(h, limit=PER):
            comps.append(dict(r))
    subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
            for c in comps if get_mol(c["smiles"])]

    out = {}

    # ① step：有序序列（含分数、来源、规则）
    ps = eng.step(subs, cond, 0.15, round_no=1)
    seq = [f"{p.smiles}|{p.rule_id}|{p.source_smiles}|{p.score:.10f}" for p in ps]
    out["step_order"] = hashlib.sha256("\n".join(seq).encode()).hexdigest()[:16]
    out["step_n"] = len(seq)

    # ② cascade：有序序列 + 轮次
    r2 = cascade(eng, subs, cond, max_rounds=4, min_new=8, frontier_limit=30)
    cseq = [f"{p.smiles}|{p.rule_id}|{p.round}|{p.score:.10f}" for p in r2.products]
    out["cascade_order"] = hashlib.sha256("\n".join(cseq).encode()).hexdigest()[:16]
    out["cascade_n"] = len(cseq)
    out["cascade_rounds"] = r2.rounds

    # ③ 兼容层
    pr = compat.predict_reactions(comps)
    pseq = [f"{p['smiles']}|{p['rxn']}|{p['from_compound']}|{p['mw']}" for p in pr]
    out["predict_order"] = hashlib.sha256("\n".join(pseq).encode()).hexdigest()[:16]
    out["predict_n"] = len(pseq)

    # ④ 多样性排序 Top-20（模拟前端）
    main = [p for p in r2.products if not p.is_byproduct]
    import types
    from predict import PredictionResult
    shell = types.SimpleNamespace(products=main)
    top = PredictionResult.diverse_ranking(shell, top=20)
    tseq = [f"{p.smiles}|{p.rule_id}" for p in top]
    out["top20_order"] = hashlib.sha256("\n".join(tseq).encode()).hexdigest()[:16]
    out["top20_n"] = len(tseq)

    # ⑤ 激活规则顺序
    act = active_rules(rules, profs, cond, 0.15)
    aseq = [f"{r['id']}|{s:.10f}" for r, s, _w in act]
    out["active_order"] = hashlib.sha256("\n".join(aseq).encode()).hexdigest()[:16]
    out["active_n"] = len(aseq)

    print("PROBE " + json.dumps(out, ensure_ascii=False))
''')


def run_probe(env_extra=None):
    import os
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([PY, "-X", "utf8", str(DRIVER)],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    line = next((l for l in r.stdout.splitlines() if l.startswith("PROBE ")), None)
    if line is None:
        return None, (r.stdout[-500:] + "\n" + r.stderr[-500:])
    import json
    return json.loads(line[6:]), None


def main() -> int:
    DRIVER.write_text(DRIVER_SRC, encoding="utf-8")
    print("=" * 96)
    print(f"跨进程审计 · 有序输出（{N} 次独立进程，不固定 PYTHONHASHSEED）")
    print("=" * 96)

    results = []
    for i in range(N):
        d, err = run_probe()
        if d is None:
            print(f"  第{i+1}次 失败:\n{err}")
            return 1
        results.append(d)
        print(f"  第{i+1}次: step={d['step_order']}({d['step_n']}) "
              f"cascade={d['cascade_order']}({d['cascade_n']}) "
              f"top20={d['top20_order']}")

    KEYS = ["step_order", "cascade_order", "predict_order",
            "top20_order", "active_order"]
    print()
    print("=" * 96)
    print("逐层面判定")
    print("=" * 96)
    allok = True
    for k in KEYS:
        vals = {r[k] for r in results}
        ok = len(vals) == 1
        allok &= ok
        print(f"  {'✓' if ok else '✗'} {k:<18} {len(vals)} 种   {results[0][k]}")

    print()
    print("  数量层面（应全一致）：")
    for k in ("step_n", "cascade_n", "cascade_rounds", "predict_n",
              "top20_n", "active_n"):
        vals = {r[k] for r in results}
        ok = len(vals) == 1
        allok &= ok
        print(f"  {'✓' if ok else '✗'} {k:<18} {sorted(vals)}")

    print()
    print("=" * 96)
    print(f"结果：{'全部一致（跨进程 + 有序）' if allok else '★存在跨进程差异★'}")
    print("=" * 96)
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
