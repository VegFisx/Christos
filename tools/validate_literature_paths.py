"""文献对照（第 87 轮）：产物一致 + 路径一致。

口径（用户 2026-11-04 m00873）：

- **产物层一致**：文献报道的目标产物在枚举结果里出现（InChIKey 连接层，忽略立体）。
- **路径层一致**：文献报道的中间体**确实能变成目标产物**，即
  `种子 →(第1轮) 中间体 →(从中间体再跑一轮) 目标`。只是"同一轮候选里也出现过"不算。

为什么不用「一次跑 2~3 轮再回溯」：一轮 = 9770 条模板 × 每一对底物，
第一轮后底物数上百，第二轮就是上百万次模板匹配（实测 14 分钟跑不完一个案例）。
而引擎的轮语义是「本轮底物 = 上一轮新增分子」，所以
`从中间体单独起跑一轮` 与 `全量第二轮里该中间体的那一部分` 是同一批规则作用，
只是剥离了组合爆炸。这叫**两步验证**，报告里必须按这个口径写。

用法：

    python tools\\validate_literature_paths.py

输出 `reports/literature_paths_20261104.json` + 控制台一张表。
"""

import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import query_base as qb            # noqa: E402
import reaction_paths as rp        # noqa: E402
import validate_literature_conversions as V   # noqa: E402  （复用 CASES / fetch / canon）

DB = "file:D:/TCMAI/tcm.db?mode=ro"
OUT_JSON = ROOT / "reports" / "literature_paths_20261104.json"


def _paozhi_ids():
    """炮制档要显式传入证据规则 id 列表 —— 与生产路径一致。

    为什么必须传（2026-11-04 第 91 轮实测）：`SmartReactEngine._load_curated_templates()`
    里有一句 ``if self.curated_rule_ids is None and r.get("paozhi_only"): continue``，
    即**不传 id 就一条炮制专属规则都不会加载**。第一版验证脚本只传了
    ``use_curated_templates=True``，于是 `demethylation_n_001` 从来没跑过，
    槟榔碱那条被误判成「产物对、反应族错」。生产路径
    `integration/tcmai_bridge/chemreact.py:1037-1038` 传的是
    ``use_base_templates=_paozhi_base`` + ``curated_rule_ids=_paozhi_ids``。
    """
    import json
    try:
        data = json.loads((ROOT / "rules" / "paozhi_evidence.json")
                          .read_text(encoding="utf-8"))
        return tuple(str(r.get("id")) for r in (data.get("rules") or [])
                     if r.get("id"))
    except Exception:
        return ()


def run_once(seed, cond_name="煎煮"):
    """单底物跑一轮。成本 = 1 个底物 × 模板库，秒级。"""
    _paozhi = str(cond_name or "").startswith("炮制")
    spec = qb.RunSpec(
        seeds=[seed],
        cond_name=cond_name,
        rounds=1,
        max_pairs=1,
        max_products_per_pair=64,
        use_curated_templates=True,
        strict_redox_gate=True,
        # 炮制档与生产路径对齐：只跑证据规则，基础模板库不参与
        curated_rule_ids=(_paozhi_ids() if _paozhi else ()),
        use_base_templates=(not _paozhi),
    )
    t0 = time.time()
    inv = qb.build_inventory(spec, score=False, use_cache=False)
    # 含伴生产物：双底物规则常把另一半（往往正是文献关心的脱酯骨架）放进 co_products
    return rp.expand_co_products(rp.hops_from_paths(inv.paths)), round(time.time() - t0, 1)


def _hit(hops, canon_target, prefer_rules=()):
    """找产物命中。优先取「反应族符合文献预期」的那一跳，避免拿错规则充数。"""
    prefer = set(prefer_rules or ())
    fallback = None
    for h in hops:
        try:
            if V.canon(h.product) != canon_target:
                continue
        except Exception:
            continue
        if h.rule in prefer:
            return h
        if fallback is None:
            fallback = h
    return fallback


def run_case(cur, case):
    row = {"key": case["key"], "label_zh": case.get("label_zh", ""),
           "literature_path": case.get("literature_path", "")}
    sub, prod = V.fetch(cur, case["substrate"]), V.fetch(cur, case["product"])
    if not sub or not prod:
        row["status"] = "missing_in_db"
        row["missing"] = case["substrate"] if not sub else case["product"]
        return row

    seed = (sub[0], sub[1], "tcm.db:literature-validation")
    ct = V.canon(prod[1])
    exp = list(case.get("expected_rules") or [])
    hops1, sec1 = run_once(seed)
    row["seconds_round1"] = sec1
    row["n_round1_products"] = len({h.product for h in hops1})

    direct = _hit(hops1, ct, exp)
    chain = []
    if direct is not None:
        chain = [rp.Hop(product=direct.product, source=sub[1], rule=direct.rule,
                        round="1", product_formula=direct.product_formula,
                        source_name=sub[0], activation=direct.activation)]
        row["route"] = "seed_to_target_in_round1"

    inter_rows = []
    for name in case.get("intermediates", []):
        rec = V.fetch(cur, name)
        if rec is None:
            inter_rows.append({"name": name, "status": "not_in_local_db",
                               "required": bool(case.get("intermediate_required"))})
            continue
        ci = V.canon(rec[1])
        in_r1 = _hit(hops1, ci)          # 中间体是不是第一轮就能生成
        hops2, sec2 = run_once((rec[0], rec[1], "tcm.db:literature-intermediate"))
        onward = _hit(hops2, ct, exp)     # 从中间体能不能到目标
        item = {
            "name": rec[0],
            "required": bool(case.get("intermediate_required")),
            "status": ("chain_ok" if (in_r1 is not None and onward is not None) else
                       ("observed_only" if in_r1 is not None else
                        ("not_observed" if onward is not None else "absent"))),
            "in_round1": in_r1 is not None,
            "intermediate_to_target": onward is not None,
            "onward_rule": onward.rule if onward is not None else "",
            "seconds_round2": sec2,
        }
        inter_rows.append(item)
        if chain and item["status"] == "chain_ok":
            # 把第一步换成「种子→中间体→目标」的真链
            h1 = rp.Hop(product=in_r1.product, source=sub[1], rule=in_r1.rule, round="1",
                        product_formula=in_r1.product_formula, source_name=sub[0])
            h2 = rp.Hop(product=onward.product, source=rec[1], rule=onward.rule, round="2",
                        product_formula=onward.product_formula, source_name=rec[0])
            chain = [h1, h2]
            row["route"] = "seed_to_intermediate_to_target"
        elif not chain and item["status"] == "chain_ok":
            h1 = rp.Hop(product=in_r1.product, source=sub[1], rule=in_r1.rule, round="1",
                        product_formula=in_r1.product_formula, source_name=sub[0])
            h2 = rp.Hop(product=onward.product, source=rec[1], rule=onward.rule, round="2",
                        product_formula=onward.product_formula, source_name=rec[0])
            chain = [h1, h2]
            row["route"] = "seed_to_intermediate_to_target"

    row["intermediates"] = inter_rows
    row["product_hit"] = bool(direct is not None or any(
        i["status"] in ("chain_ok", "observed_only") for i in inter_rows))
    exp_matched = sorted({h.rule for h in chain} & set(case.get("expected_rules", [])))
    row["expected_rules_matched"] = exp_matched
    row["rule_family_ok"] = bool(exp_matched)
    if chain and not row["rule_family_ok"]:
        row["rule_used"] = sorted({h.rule for h in chain})
        row["rule_expected"] = list(case.get("expected_rules", []))

    req = [i for i in inter_rows if i.get("required")]
    if not row["product_hit"]:
        row["status"] = "product_miss"
    elif not row["rule_family_ok"]:
        # 产物对、规则族不对 —— 不能算一致
        row["status"] = "partial"
    elif req and not all(i["status"] == "chain_ok" for i in req):
        row["status"] = "partial"
    else:
        row["status"] = "consistent"

    if chain:
        rule_names = rp.load_rule_names(ROOT / "rules" / "rules.json")
        labels = {h.product: (h.product_formula or rp.formula_of(h.product)) for h in chain}
        row["chain_text"] = rp.render_chain(chain, rule_names=rule_names, labels=labels)
    else:
        row["chain_text"] = ""
    return row


def main() -> int:
    cur = sqlite3.connect(DB, uri=True).cursor()
    rows = []
    for case in V.CASES:
        t0 = time.time()
        print("  ... %s" % case["label_zh"], flush=True)
        rows.append(run_case(cur, case))
        print("      %.1fs -> %s" % (time.time() - t0, rows[-1].get("status")), flush=True)

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "validation_type": "retrospective literature comparison: product + path (two-step)",
        "condition": "煎煮 (100 C / 60 min / pH 6.5)",
        "protocol": "种子单轮枚举 + 从文献中间体单独起跑一轮；不用全量多轮枚举（成本爆炸）",
        "note": "路径层判定『文献中间体能否变成目标产物』；不涉及收率/动力学/立体化学。",
        "cases": rows,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n%-24s %-8s %-12s %s" % ("case", "product", "status", "intermediates"))
    for r in rows:
        inter = ", ".join("%s:%s" % (i["name"][:26], i["status"]) for i in r.get("intermediates", [])) or "-"
        print("%-24s %-8s %-12s %s" % (r["key"][:24],
                                       "hit" if r.get("product_hit") else "miss",
                                       r.get("status", ""), inter))
    print("\n写出：%s\n" % OUT_JSON)
    for r in rows:
        if r.get("chain_text"):
            print("[%s] %s" % (r["key"], r["chain_text"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
