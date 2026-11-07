"""炮制文献对照（第 88 轮）：产物一致 + 路径一致，走炮制条件。

口径（比第 87 轮更严）：
    一个案例只有同时满足下面三条，才算 ``consistent``：
    1. 产物结构对（InChIKey 前 14 位一致，忽略立体）；
    2. 反应族对（命中的规则属于文献说的那类反应，如「酯水解」不是「酯氨解」）；
    3. 不是分子式级碰巧命中。

    产物对但反应族不对 → ``product_only``；只有分子式对 → ``formula_only``。

验证协议沿用第 87 轮的「两步法」：
    种子单轮 → 目标没出现时，用文献点名的中间体单独再跑一轮。
    （引擎的「轮」语义是「本轮底物 = 上一轮新增分子」，所以中间体单跑一轮
     等价于全量第二轮里该中间体那一部分，避开组合爆炸。）

结构一律取自 tcm.db（只读 URI），不手写 SMILES。

用法：

    python tools\\validate_paozhi_paths.py

输出 ``reports/paozhi_paths_20261104.json`` + 控制台表。
案例来源：``reports/paozhi_simulation_literature_20261031.md`` §4.1/§4.2。
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

import reaction_paths as rp              # noqa: E402
import validate_literature_conversions as V   # noqa: E402
from validate_literature_paths import run_once  # noqa: E402  两步验证的第一步

DB = "file:D:/TCMAI/tcm.db?mode=ro"
OUT_JSON = ROOT / "reports" / "paozhi_paths_20261104.json"

# (标签, 种子 ingredient_id, 条件档, [(目标标签, 匹配方式, 值, 文献预期的规则族前缀)], 桥接中间体 id)
# 匹配方式："key" 用 tcm.db 的 ingredient_id 取 InChIKey；"formula" 只能用分子式。
CASES = [
    ("ginsenoside_Rb1", "HBIN027729", "炮制·蒸制", [
        ("Rg3", "key", "HBIN003457", ("hydrolysis_glycoside",)),
        ("Rg5", "key", "HBIN027756", ("elimination_dehydration", "dehydration")),
        ("Rk1", "key", "HBIN027782", ("elimination_dehydration", "dehydration")),
    ], "HBIN003457"),            # 文献：Rb1 → Rg3 → Rg5/Rk1
    ("arecoline", "HBIN016699", "炮制·炒焦", [
        # 文献 A3：槟榔碱 → 去甲槟榔碱 是「N-脱甲基」，不是酯水解（两者分子式同为 C7H11NO2）
        # 2026-11-04 第 91 轮：目标改成 InChIKey。库里有 Guvacoline = HBIN028561
        # （C7H11NO2 / DYPLDWLIOGXSSE-UHFFFAOYSA-N）→ 目标用 ingredient_id，结构层可以判。
        ("norarecoline", "key", "HBIN028561", ("demethylation",)),
    ], ""),
    ("CATR", "HBIN019719", "炮制·炒黄", [
        # 文献 A4：苍耳子砂炒是「加热脱羧」；ATR 骨架库里没有条目 → 只能分子式级
        ("ATR 骨架", "formula", "C30H46O16S2", ("decarboxylation",)),
    ], ""),
    ("JNB", "HBIN031562", "炮制·醋炙", [
        # 文献 A2：狼毒醋制是内酯/环氧开环；C20H28O5 库里 20 个同分异构
        ("JNB 开环酸", "formula", "C20H28O5", ("hydrolysis_lactone", "hydrolysis_epoxide", "epoxide")),
    ], ""),
    # 附子：双酯型生物碱 → 单酯型（炮制减毒）。文献 C2：酯水解（hydrolysis_ester_001）。
    ("aconitine", "HBIN014582", "炮制·蒸制", [
        ("benzoylaconine", "key", "HBIN017810", ("hydrolysis_ester",)),
    ], ""),
    # 何首乌：二苯乙烯苷 → 苷元（水解第一阶段）。库里没有精确命名的
    # 「2,3,5,4'-四羟基二苯乙烯」，C14H12O4 有 20 个同分异构 → 只能分子式级。
    ("THSG", "HBIN003908", "炮制·蒸制", [
        ("THSG 苷元", "formula", "C14H12O4", ("hydrolysis_glycoside",)),
    ], ""),
]


def db_row(cur, iid):
    cur.execute("SELECT ingredient_id, name_en, formula, smiles, inchi_key "
                "FROM compounds WHERE ingredient_id=?", (iid,))
    return cur.fetchone()


def match_target(hops, kind, value, prefixes=()):
    """返回命中的 Hop（伴生产物也算，因为它们同样是反应产物）。

    ``formula`` 匹配会有多个候选（同分异构），此时**优先取反应族符合文献的那个**，
    否则会误判成「规则族不对」——2026-11-04 第一版就踩了这个坑。
    """
    if kind == "formula":
        cands = [h for h in hops
                 if h.product_formula and h.product_formula.upper() == value.upper()]
        if not cands:
            return None
        for h in cands:
            if any(family_ok(x, prefixes) for x in rules_of(h)):
                return h
        return cands[0]
    want = value[:14].upper()
    hits = []
    for h in hops:
        try:
            if V.full_inchikey(h.product)[:14].upper() == want:
                hits.append(h)
        except Exception:
            continue
    if not hits:
        return None
    for h in hits:                      # 同一结构可能由多条规则给出，优先取文献预期那一族
        if any(family_ok(x, prefixes) for x in rules_of(h)):
            return h
    return hits[0]


def rules_of(h):
    """这一跳对应的全部规则：主规则 + 去重时被丢掉但同样能给出它的规则。"""
    out = [h.rule] if h.rule else []
    for x in (getattr(h, "alt_rules", "") or "").split(","):
        x = x.strip()
        if x and x not in out:
            out.append(x)
    return out


def family_ok(rule_id, prefixes):
    if not prefixes:
        return True
    rid = (rule_id or "").lower()
    return any(rid.startswith(p.lower()) or p.lower() in rid for p in prefixes)


def _judge(hit, kind, prefixes):
    """把一次命中翻成 (status, 说明)。"""
    ok_family = any(family_ok(x, prefixes) for x in rules_of(hit))
    level = "structure" if kind == "key" else "formula"
    item = {
        "rule": hit.rule, "rules_all": rules_of(hit), "product_formula": hit.product_formula,
        "co_product": bool(hit.co), "match_level": level,
        "rule_family_ok": ok_family,
    }
    if not ok_family:
        item["status"] = "product_only"
        item["why"] = "产物对，但反应族是 %s，文献预期 %s" % (hit.rule, "/".join(prefixes))
    elif level == "formula":
        item["status"] = "formula_only"
        item["why"] = "只有分子式命中（同分异构未区分）"
    else:
        item["status"] = "consistent"
    return item


def run_case(cur, tag, seed_id, cond, targets, bridge_id):
    row = {"tag": tag, "seed_id": seed_id, "condition": cond}
    seed = db_row(cur, seed_id)
    if not seed or not seed[3]:
        row["status"] = "no_seed"
        row["note"] = "tcm.db 里没有这个成分的结构，不能做对照"
        return row
    row["seed_name"] = seed[1]
    row["seed_formula"] = seed[2]

    hops1, sec1 = run_once((seed[1], seed[3], "tcm.db:paozhi-literature"), cond_name=cond)
    row["seconds_round1"] = sec1
    row["n_round1"] = len({h.product for h in hops1})

    resolved = []
    for label, kind, val, prefixes in targets:
        if kind == "key":
            t = db_row(cur, val)
            if not t or not t[4]:
                resolved.append((label, kind, "", prefixes))
                continue
            resolved.append((label, kind, t[4][:14].upper(), prefixes))
        else:
            resolved.append((label, kind, val, prefixes))

    results = []
    need_bridge = []
    for label, kind, val, prefixes in resolved:
        if not val:
            results.append({"target": label, "status": "target_not_in_db"})
            continue
        hit = match_target(hops1, kind, val, prefixes)
        if hit is not None:
            item = _judge(hit, kind, prefixes)
            item["target"] = label
            item["round"] = 1
            results.append(item)
        else:
            need_bridge.append((label, kind, val, prefixes))
            results.append({"target": label, "status": "pending_round2"})

    if need_bridge and bridge_id:
        bridge = db_row(cur, bridge_id)
        if bridge and bridge[3]:
            row["bridge_name"] = bridge[1]
            hops2, sec2 = run_once((bridge[1], bridge[3], "tcm.db:paozhi-bridge"),
                                   cond_name=cond)
            row["seconds_round2"] = sec2
            for item in results:
                if item["status"] != "pending_round2":
                    continue
                label = item["target"]
                kind, val, prefixes = next((k, v, p) for (lab, k, v, p) in resolved if lab == label)
                hit = match_target(hops2, kind, val, prefixes)
                if hit is None:
                    item["status"] = "miss"
                else:
                    new = _judge(hit, kind, prefixes)
                    new["target"] = label
                    new["round"] = 2
                    new["via"] = bridge[1]
                    item.clear()
                    item.update(new)
    for item in results:
        if item["status"] == "pending_round2":
            item["status"] = "miss"

    row["targets"] = results
    ok = [r for r in results if r["status"] != "miss" and r["status"] != "target_not_in_db"]
    row["n_consistent"] = len([r for r in results if r["status"] == "consistent"])
    row["n_products_ok"] = len(ok)
    if not results:
        row["status"] = "no_target"
    elif row["n_consistent"] == len(results):
        row["status"] = "consistent"
    elif ok:
        row["status"] = "partial"
    else:
        row["status"] = "miss"
    return row


def main() -> int:
    cur = sqlite3.connect(DB, uri=True).cursor()
    rows = []
    for tag, seed_id, cond, targets, bridge_id in CASES:
        t0 = time.time()
        print("  ... %s (%s, %s)" % (tag, seed_id, cond), flush=True)
        rows.append(run_case(cur, tag, seed_id, cond, targets, bridge_id))
        print("      %.1fs -> %s" % (time.time() - t0, rows[-1].get("status")), flush=True)

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "validation_type": "retrospective paozhi literature comparison: product + path + rule family",
        "protocol": "种子单轮（炮制档）+ 文献中间体单独再跑一轮；结构全部只读取自 tcm.db",
        "criteria": {
            "consistent": "产物结构一致（InChIKey 前 14 位）+ 反应族符合文献",
            "formula_only": "只有分子式命中，同分异构未区分",
            "product_only": "产物对，但反应族与文献不符",
            "miss": "没生成该产物",
        },
        "cases": rows,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n%-18s %-12s %-10s %s" % ("case", "condition", "status", "targets"))
    for r in rows:
        tg = ", ".join("%s:%s" % (t["target"], t["status"]) for t in r.get("targets", [])) \
            or r.get("note", "-")
        print("%-18s %-12s %-10s %s" % (r["tag"], r.get("condition", ""), r.get("status", ""), tg))
    print("\n写出：%s" % OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
