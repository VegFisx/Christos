# -*- coding: utf-8 -*-
"""立体异构判断：对着**真实产物**查「反应没碰到的手性中心有没有保住」。

和 ``rules/stereo.py`` 的关系
----------------------------
``rules/stereo.py`` 是**离线规则体检**：拿库里的底物 × 每条规则，问「这条规则会不会丢手性」。
这个脚本换了个方向：拿**一次真实运行**的台账，逐跳问
「这一跳该保住的手性中心，产物里还在不在」。

判据（沿用 ``rules/stereo.py`` 的判据，不另立一套）
--------------------------------------------------
一条规则的作用范围 = SMARTS 里带原子映射号的原子。
  · 落在作用范围内的手性中心：反应就在它身上发生，消失是对的
  · 落在作用范围**之外**的（旁观中心）：不该动，丢了就是问题

所以逐跳判断需要三样东西：底物、产物、规则 SMARTS。
台账里有前两样，SMARTS 从 ``rules/rules.json`` 按规则名反查。

输出五档
--------
  ok            旁观手性中心全在
  partial       产物指定的手性中心比旁观中心少，但没到 0
  lost_all      产物一个指定手性中心都没有（信息整层丢了）
  no_src_stereo 底物本来就没有指定手性中心（无从判断）
  unknown       规则 SMARTS 对不上 / 双反应物 / 解析失败（明确报，不静默）

用法
----
    python tools\\judge_stereo_hops.py <输出目录或台账.csv> [--top 12] [-o report.json]

要跑「带立体化学」的预测，先设环境变量：

    $env:CHEMCREACT_STEREO_CANON = "1"

默认这个开关是**关**的 —— 关掉时产物 SMILES 里没有任何立体标记，
此时这个脚本会几乎全是 ``no_src_stereo``/``lost_all``，那是开关造成的，不是规则问题。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "rules", ROOT / "libs", ROOT / "tools"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger          # noqa: E402
from rdkit.Chem import AllChem            # noqa: E402

RDLogger.DisableLog("rdApp.*")


def load_rule_smarts(path=None):
    """id -> (name, smarts)，name 也建索引（台账里存的是规则名）。"""
    path = Path(path) if path else ROOT / "rules" / "rules.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data.get("rules", data) if isinstance(data, dict) else data
    by_id, by_name = {}, {}
    for r in rules:
        rid, name, smarts = r.get("id"), r.get("name"), r.get("smarts")
        if not smarts:
            continue
        by_id[rid] = (name, smarts)
        if name:
            by_name[name] = (rid, smarts)
    return by_id, by_name


def specified_centers(mol):
    try:
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
        return {int(i): str(t) for i, t in
                Chem.FindMolChiralCenters(mol, includeUnassigned=False,
                                          useLegacyImplementation=False)}
    except Exception:
        return {}


def spectators_of(smarts, mol):
    """返回 (在作用范围内被触及的原子集合, 与底物匹配的原子数)；失败返回 (None, 0)。

    双反应物规则返回 (None, -1) —— 逐跳判断只支持单反应物规则。
    """
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
        if rxn is None:
            return None, 0
        n_tpl = rxn.GetNumReactantTemplates()
        if n_tpl not in (1, 2):
            return None, -1
        patts = [rxn.GetReactantTemplate(k) for k in range(n_tpl)]
    except Exception:
        return None, 0
    # 双反应物规则：台账只记了其中一侧的底物，所以「哪一侧模板能匹配上就用哪一侧」
    tok = 0
    best = None
    for patt in patts:
        matched = mol.GetSubstructMatch(patt)
        tok += 1
        if not matched:
            continue
        touched = {mol_idx for patt_idx, mol_idx in enumerate(matched)
                   if patt.GetAtomWithIdx(patt_idx).GetAtomMapNum()}
        if best is None:
            best = touched
        else:
            best |= touched
    if best is None:
        return None, 0
    return best, 1


def prod_center_count(row, m_prod):
    """产物侧的指定手性中心数 = 主产物 + co_products 各片段。

    ★ 这一步不能省：水解 / 断裂类反应会把分子拆成两片，
      主产物那一行往往只是其中一片，只数它会把「另一片上的手性中心」误判成丢失。
      ``rules/stereo.py`` 的头部注释里记过同一个坑（当时是逐个片段比，全误报）。
    """
    total = len(specified_centers(m_prod))
    for frag in (row.get("co_products") or "").split("|"):
        frag = frag.strip()
        if not frag:
            continue
        m = Chem.MolFromSmiles(frag)
        if m is not None:
            total += len(specified_centers(m))
    return total


def judge_hop(row, byname):
    src = row.get("source_smiles") or ""
    prod = row.get("product_smiles") or ""
    rule = row.get("rule_name") or ""
    m_src = Chem.MolFromSmiles(src)
    m_prod = Chem.MolFromSmiles(prod)
    if m_src is None or m_prod is None:
        return "unknown", {"why": "SMILES 解析失败"}
    c_src = specified_centers(m_src)
    n_prod = prod_center_count(row, m_prod)
    if not c_src:
        return "no_src_stereo", {"src_centers": 0, "prod_centers": n_prod}
    smarts = ""
    how = ""
    if rule in byname:
        smarts = byname[rule][1]
        how = "rules.json"
    else:
        # ★ 第八十九轮：mined 模板产物。台账以前只记类别名（mined_extra / mined_mono），
        #   现在引擎把命中的模板 SMARTS 写进 template_smarts 列，就能直接算作用范围。
        ts = (row.get("template_smarts") or "").strip()
        if ts:
            smarts = ts
            how = "template_smarts"
    if not smarts:
        return "unknown", {"why": "规则不在 rules.json，且台账没有 template_smarts：%s" % rule,
                          "src_centers": len(c_src), "prod_centers": n_prod}
    touched, nmatch = spectators_of(smarts, m_src)
    if touched is None:
        why = "反应模板数不是 1/2" if nmatch == -1 else "SMARTS 未匹配上底物（来源 %s）" % how
        return "unknown", {"why": why, "src_centers": len(c_src),
                          "prod_centers": n_prod}
    spec = {i for i in c_src if i not in touched}
    n_spec = len(spec)
    detail = {"src_centers": len(c_src), "spectators": n_spec,
              "prod_centers": n_prod, "in_scope": len(c_src) - n_spec}
    if n_spec == 0:
        return "ok", detail          # 底物的手性中心都在作用范围内 → 无可旁观
    if n_prod >= n_spec:
        return "ok", detail
    return ("lost_all" if n_prod == 0 else "partial"), detail


def pick_csv(target: Path) -> Path:
    if target.is_file():
        return target
    cands = sorted(target.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        raise SystemExit("目录里没有 *.csv 台账：%s" % target)
    return cands[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="逐跳立体异构判断")
    ap.add_argument("target", help="输出目录，或直接的台账 csv 路径")
    ap.add_argument("--rules", default=None, help="rules.json 路径")
    ap.add_argument("--top", type=int, default=12, help="按规则列前 N 条")
    ap.add_argument("-o", "--out", default=None, help="把明细写成 JSON")
    args = ap.parse_args(argv)

    csv_path = pick_csv(Path(args.target))
    byid, byname = load_rule_smarts(args.rules)
    byname = dict(byname)              # 台账里 rule_name 存的是规则 id，两个键都认
    byname.update(byid)

    counts = Counter()
    by_rule = defaultdict(Counter)
    examples = defaultdict(list)
    n_rows = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            n_rows += 1
            verdict, detail = judge_hop(row, byname)
            counts[verdict] += 1
            key = row.get("rule_name") or "?"
            by_rule[key][verdict] += 1
            if verdict in ("partial", "lost_all") and len(examples[key]) < 2:
                examples[key].append({
                    "product": (row.get("product_smiles") or "")[:80],
                    "source": (row.get("source_smiles") or "")[:80],
                    "detail": detail,
                })

    judged = n_rows - counts["no_src_stereo"] - counts["unknown"]
    print("台账：%s" % csv_path)
    print("逐跳 %d 条（其中可判 %d 条）\n" % (n_rows, judged))
    order = ["ok", "partial", "lost_all", "no_src_stereo", "unknown"]
    label = {"ok": "保住", "partial": "部分丢失", "lost_all": "整层丢失",
             "no_src_stereo": "底物无手性", "unknown": "无法判断"}
    for k in order:
        if counts[k]:
            print("  %-14s %6d" % (label[k], counts[k]))

    print("\n按规则（只看可判的）：")
    ranked = sorted(by_rule.items(),
                    key=lambda kv: (kv[1]["lost_all"] + kv[1]["partial"]), reverse=True)
    for rule, c in ranked[:args.top]:
        bad = c["lost_all"] + c["partial"]
        if not bad:
            continue
        print("  %-38s 丢失 %4d / 可判 %4d  (整层 %d, 部分 %d)"
              % (rule, bad, c["ok"] + bad, c["lost_all"], c["partial"]))
        for ex in examples[rule]:
            print("      例：旁观 %s 个 → 产物指定 %s 个 | %s"
                  % (ex["detail"].get("spectators"), ex["detail"].get("prod_centers"),
                     ex["product"][:46]))

    if args.out:
        payload = {
            "csv": str(csv_path),
            "n_rows": n_rows,
            "counts": dict(counts),
            "by_rule": {k: dict(v) for k, v in by_rule.items()},
            "examples": dict(examples),
        }
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print("\n明细写出：%s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
