"""在同一批「全映射反应」上跑模板引擎，给学习型反应中心一个对照基线。

为什么需要这个：
    第 146 轮训出的中心模型报「产物完全命中 27.9%」，但那个数字没有同类可比对象——
    模板路线在 ORD 子集上从没被这样量过。没有对照，27.9% 既不能说明好也不能说明差。

口径（三条都要一致，否则对比无意义）：
    1. 样本：`reports/center_dataset_mapped.jsonl` 前 N 条里的**测试半区**（rid 哈希为奇数），
       与 `tools/train_center_model.py` 用同一个切分函数，保证模型没见过这些反应。
    2. 产物比较：抹掉映射号 → 拆碎片 → 各自 sanitize → 排序拼回，与训练脚本的 canon_set 同一实现。
    3. 条件：一律用「煎煮」档（水 / 100 °C / 60 min / pH 6.5 / 空气），与论文基准同口径。

输出三档，逐条都要能对上：
    recall     真产物出现在候选列表里的比例（模板路线强项）
    top1       真产物排第一的比例
    set_eq     候选集合与「记录产物」完全相等（只有一条产物时才可能，最严）

用法：
    python tools/bench_center_vs_template.py 500
    CHEMCREACT_BENCH_CLI_CONFIG=1 python tools/bench_center_vs_template.py 500
"""

import hashlib
import json
import os
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_HERE = Path(__file__).resolve().parent
STAGE = _HERE.parent
for _p in (STAGE, STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs", _HERE):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DATA = STAGE / "reports" / (os.environ.get("CENTER_DATASET") or "center_dataset_mapped.jsonl")


def _h(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


def canon_set(smi: str) -> str:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return ""
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    try:
        Chem.SanitizeMol(m)
    except Exception:
        return ""
    outs = []
    for frag in Chem.GetMolFrags(m, asMols=True, sanitizeFrags=False):
        try:
            Chem.SanitizeMol(frag)
            outs.append(Chem.MolToSmiles(frag))
        except Exception:
            return ""
    return ".".join(sorted(outs))


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    rows = []
    with open(DATA, encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
            if len(rows) >= 20000:
                break
    te = [r for r in rows if _h(r["rid"]) % 2 == 1][:n]
    print(f"测试样本 {len(te)} 条（来自 {len(rows)} 条的前 20,000 条，测试半区）")

    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    kw = {}
    if os.environ.get("CHEMCREACT_BENCH_EXTRA_LIMIT"):
        kw["extra_template_limit"] = int(os.environ["CHEMCREACT_BENCH_EXTRA_LIMIT"])
    if os.environ.get("CHEMCREACT_BENCH_EXTRA_MIN_SUPPORT"):
        kw["extra_template_min_support"] = int(os.environ["CHEMCREACT_BENCH_EXTRA_MIN_SUPPORT"])
    if os.environ.get("CHEMCREACT_BENCH_MONO_LIMIT"):
        kw["mono_template_limit"] = int(os.environ["CHEMCREACT_BENCH_MONO_LIMIT"])
    if os.environ.get("CHEMCREACT_BENCH_CLI_CONFIG"):
        kw["use_curated_templates"] = True
        kw["strict_redox_gate"] = True
    eng = SmartReactEngine(**kw)
    cond = T.get_template("煎煮")

    hit = top1 = set_eq = err = 0
    ranks = []
    for r in te:
        parts = [s for s in r["smiles_r"].split(".") if s]
        comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)") for j, s in enumerate(parts)]
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception:
            err += 1
            continue
        got = sorted({canon_set(getattr(p, "smiles", "")) for p in prods} - {""})
        want = canon_set(r["smiles_p"])
        if not want:
            err += 1
            continue
        if want in got:
            hit += 1
            ranks.append(got.index(want) + 1)
            if got.index(want) == 0:
                top1 += 1
        if len(got) == 1 and got[0] == want:
            set_eq += 1

    total = max(1, len(te))
    print(f"模板引擎：recall {hit}/{total} = {100.0*hit/total:.1f}% · "
          f"top-1 {top1}/{total} = {100.0*top1/total:.1f}% · "
          f"集合恰好相等 {set_eq}/{total} = {100.0*set_eq/total:.1f}% · 报错 {err}")
    if ranks:
        ranks.sort()
        print(f"命中时的位次：中位 {ranks[len(ranks)//2]} · p90 {ranks[int(len(ranks)*0.9)]} · 最大 {ranks[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
