# -*- coding: utf-8 -*-
r"""查询式交互 —— 命令行（三个入口 + 共用底座）
==============================================

设计依据：`reports/项目接手总结-2026-10-12-收工版.md` §一（用户 2026-10-12 拍板）。

    一次枚举（每条产物带出处：来源底物 / 反应规则 / 第几轮）
  + 一份索引（产物规范化 SMILES -> InChIKey）
  -> A 查产物 / B 查底物 / C 结果集检索

## 四个子命令

    build    ★ 一次枚举 ★：输入分子 + 条件 + 轮数 -> 产物台账（CSV）+ 索引（TSV）
    A        查产物：一个分子 -> 在不在产物集里 / 由哪条路径生成（第几轮、哪个底物、哪条规则）
    B        查底物：一个分子当底物 -> 只跑它 -> 输出产物（可 --with 再加一个 = 双分子）
    C        结果集检索：名称 / 分子式 / SMILES / 子结构 -> 过滤后的产物清单（不高亮、不排序）
    selftest 自检：小规模跑通 A/B/C 三个入口并打印判据（换机器/换数据后可复查）

## 轮数由用户掌握
`build --rounds N`：**N 由你定**。第 2..n 轮开不开、开到几轮是你的事；
底座不设"自动收敛就停"，也不设打分门槛替你截断（打分停工，判断权交回用户）。

## 三条边界（每次输出都会复述）
1. 查不到 ≠ 不存在（只等于当前模板库 + 当前轮数没枚举出来）
2. B 只给一个分子 -> 只有单底物化学；双分子反应必须同时给配体
3. 预测出的新产物没有名字 -> 按名称查只对库里已有的分子有效

## 用法
    $py -u tools\query_engine.py build --herb 甘草 --limit 12 --rounds 1
    $py -u tools\query_engine.py build --smiles "OCc1ccccc1,NCCc1ccc(O)cc1" --cond 煎煮 --rounds 2
    $py -u tools\query_engine.py A --mol "OCc1ccccc1"
    $py -u tools\query_engine.py B --mol "OCc1ccccc1" --with "NCCc1ccc(O)cc1"
    $py -u tools\query_engine.py C --formula C7H6O2
    $py -u tools\query_engine.py C --substructure "c1ccccc1O" --max-round 1
    $py -u tools\query_engine.py selftest
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, Optional

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import query_base as qb                                  # noqa: E402

LANG = "zh"


def _L(zh: str, en: str) -> str:
    return en if LANG == "en" else zh


COND_EN = {
    "煎煮": "Decoction", "室温浸泡": "Room-temperature soak", "水提": "Water extraction",
    "醇提": "Ethanol extraction", "酸水解": "Acid hydrolysis", "碱水解": "Base hydrolysis",
    "酶催化": "Enzymatic", "还原": "Reduction", "氧化": "Oxidation",
    "无氧煎煮": "Anaerobic decoction",
}


def _cond(x: str) -> str:
    return COND_EN.get(x, x) if LANG == "en" else x

REPORTS = STAGE / "reports"
BOUND_LINE = ("边界：查不到 ≠ 不存在（= 当前模板库 + 当前轮数没枚举出来）；"
              "B 单分子只有单底物化学；新产物没有名字")


# ---------------------------------------------------------------- 输入分子

def collect_seeds(a) -> list:
    """把 --herb / --coconut / --smiles / --mol 统一成 (name, smiles, 来源标签)。"""
    seeds = []
    if a.smiles:
        for i, s in enumerate([x.strip() for x in a.smiles.split(",") if x.strip()]):
            cs = qb.canon(s)
            if cs is None:
                print(f"  [warn] 第 {i+1} 个 SMILES 解析失败，跳过：{s[:60]}")
                continue
            seeds.append((f"输入{i+1}", cs, "用户SMILES"))
    if getattr(a, "mol", None):
        for i, s in enumerate(a.mol):
            cs = qb.canon(s)
            if cs is None:
                print(f"  [warn] --mol 解析失败，跳过：{s[:60]}")
                continue
            seeds.append((f"mol{i+1}", cs, "用户SMILES"))
    if a.coconut:
        import sqlite3
        if not qb.COCONUT_DB.exists():
            print(f"  [warn] 找不到 {qb.COCONUT_DB}")
        else:
            con = sqlite3.connect(f"file:{qb.COCONUT_DB}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT name, smiles FROM compounds "
                "WHERE smiles IS NOT NULL AND smiles <> '' AND smiles <> 'None' "
                "ORDER BY RANDOM() LIMIT ?", (a.coconut,)).fetchall()
            con.close()
            for nm, sm in rows:
                cs = qb.canon(sm)
                if cs:
                    seeds.append((str(nm or "?")[:60], cs, "coconut.db"))
    if a.herb:
        from herb import compounds_of_herb
        for h in [x.strip() for x in a.herb.split(",") if x.strip()]:
            got = compounds_of_herb(h, limit=a.limit)
            if not got:
                print(f"  [warn] 药材 {h} 没取到成分")
            for c in got:
                seeds.append((c.name, c.smiles, f"tcm.db:{c.herb or h}"))
    # 去重（按规范化 SMILES）
    out, seen = [], set()
    for nm, sm, src in seeds:
        if sm in seen:
            continue
        seen.add(sm)
        out.append((nm, sm, src))
    return out


# ---------------------------------------------------------------- 打印工具

def _fmt_paths(paths) -> str:
    def one(p):
        why = qb.activation_reason_short(p.get("activation_why", ""))
        base = f"r{p['round']}:{p['rule_name']}(a={float(p['activation']):.2f}"
        return base + (f"，{why})" if why else ")")
    return " / ".join(one(p) for p in paths)


def _print_gate(inv: qb.Inventory) -> None:
    """打印条件依据摘要：把"0.5 到底是什么"讲清楚。"""
    cat_en = {"窗口命中": "window hit", "降权": "downweighted",
              "无数据放行": "no-data pass", "依据未记录": "not recorded"}

    def _cat(k):
        return cat_en.get(k, k) if LANG == "en" else k

    def _why(s):
        if LANG == "en":
            s = str(s)
            s = s.replace("ORD 条件窗口内，无降权", "inside ORD condition window; no downweighting")
            s = s.replace("无降权", "no downweighting")
            s = s.replace("无 ORD 条件数据，放行", "no ORD condition data; passed")
            s = s.replace("窗口命中", "window hit")
            s = s.replace("依据未记录", "not recorded")
            s = s.replace("降权", "downweighted")
            s = s.replace("温度 ", "temperature ").replace("高于实测上限 ", "above measured upper limit ")
            s = s.replace("，downweighted", "; downweighted")
        return s

    try:
        g = qb.gate_summary(inv)
    except Exception as ex:                      # noqa: BLE001
        print(f"  [warn] 条件依据摘要算不出来：{type(ex).__name__}: {ex}")
        return
    print(_L("  条件依据（activation 的来路；★ 它不是「发生概率」）：",
             "  Condition evidence (source of activation; NOT a probability):"))
    print(_L(f"    出处路径 {g['n_paths']} 条：", f"    Evidence paths {g['n_paths']}: ")
          + " · ".join(
              f"{_cat(k)} {v} ({g['share'].get(k, 0):.0%})" if LANG == "en"
              else f"{k} {v}（{g['share'].get(k, 0):.0%}）"
              for k, v in sorted(g["by_cat"].items(), key=lambda kv: -kv[1])))
    for why, n in g["top_reasons"][:4]:
        print(f"      {n:>5}  {_why(why)}")
    print("    ⚠ " + _L(g["note"],
                     "activation is condition-layer evidence strength, not a probability; "
                     "no-data pass means no ORD condition window for this reaction class, "
                     "so 'can happen' has no condition evidence."))


def _split_reagents(s: str) -> tuple:
    """★ D4：把 `--reagents "a,b;c"` 切成元组（空串 -> 空元组）。"""
    out = []
    for part in str(s or "").replace(";", ",").split(","):
        p = part.strip()
        if p:
            out.append(p)
    return tuple(out)


def print_inv_summary(inv: qb.Inventory, a=None) -> None:
    st = inv.stats
    print("-" * 108)
    desc = inv.spec.describe()
    if LANG == "en":
        desc = re.sub(r"输入 (\d+) 个", r"\1 inputs", desc)
        desc = desc.replace("条件 ", "condition ").replace("轮数 ", "rounds ")
        for a_, b_ in COND_EN.items():
            desc = desc.replace(a_, b_)
    print(f"  {_L('枚举：', 'Enumeration: ')}{desc}")
    for n in st.engine_notes:
        print(f"        {n}")
    print(_L(f"  产物分子 {st.n_products} 个 · 出处路径 {st.n_paths_kept} 条 · "
             f"耗时 {st.seconds}s",
             f"  Products {st.n_products} · evidence paths {st.n_paths_kept} · "
             f"elapsed {st.seconds}s"))
    if st.per_round_new:
        print(_L("  逐轮（实测）：", "  Per round: ") + "  ".join(
            _L(f"r{r['round']} 新增 {r['new']}（{r['seconds']}s）",
               f"r{r['round']} new {r['new']} ({r['seconds']}s)")
            for r in st.per_round_new))
    print(_L(f"  InChIKey：成功 {st.ik_ok}（其中缓存命中 {st.ik_cached}）· 失败 {st.ik_fail}",
             f"  InChIKey: ok {st.ik_ok} (cached {st.ik_cached}) · failed {st.ik_fail}"))
    if st.ik_examples_failed:
        print(f"    ⚠ 失败样例（不静默）：{st.ik_examples_failed}")
    print(_L(f"  被剔的「产物 == 输入分子」：{st.n_self_products} 条（不计入产物）",
             f"  Removed products == input: {st.n_self_products} (not counted)"))
    if st.truncated:
        print(_L("  ⚠ 本轮底物对超过 max_pairs 被截断 -> 部分分子不会被单底物模板覆盖",
                 "  ⚠ Substrate pairs exceeded max_pairs; some molecules are not covered "
                 "by single-substrate templates"))
    if getattr(inv, "paths_file", None):
        print(_L(f"  台账 -> {inv.paths_file}", f"  Ledger -> {inv.paths_file}"))
    if getattr(inv, "index_file", None):
        print(_L(f"  索引 -> {inv.index_file}", f"  Index -> {inv.index_file}"))


# ---------------------------------------------------------------- build

def _log_one(cmd: str, query: str, res: Dict, found: bool, n_hits: int,
             extra: Optional[Dict] = None) -> None:
    """证据回流：把"用户查了什么、命中没有"记一行（append-only，不参与任何排序）。

    ★ 不违反"打分停工"：只记录、不回灌、不推荐。失败也不该拖垮查询，所以这里兜住异常。
    """
    try:
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "cmd": cmd,
               "query": str(query)[:300],
               "resolved_kind": (res or {}).get("resolved", {}).get("kind", ""),
               "found": bool(found), "n_hits": int(n_hits)}
        if extra:
            rec.update(extra)
        qb.dump_query_log([rec])
    except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
        print(f"  [warn] 查询日志写入失败：{type(ex).__name__}: {ex}")


def _print_triples(inv: qb.Inventory) -> None:
    """★ D5：三组分模板的**标记**（不删产物、不排序）。

    只回答一件事：这次枚举里有多少条出处来自 3 组分模板，其中多少来自**只见过一次**的套路
    （support=1，可信度低）。用户要的就是这个标记，而不是替他删掉。
    """
    paths = list(inv.paths)
    tri = [x for x in paths if str(x.get("rule_name") or "") == "mined_triple"]
    if not tri:
        return
    sup1 = sum(1 for x in tri if int(x.get("template_support") or 0) <= 1)
    print(_L(f"  三组分（D5）：{len(tri)} 条出处来自 3 组分模板"
             f"（占本次 {len(paths)} 条的 {len(tri)/max(1,len(paths)):.0%}）；"
             f"其中 {sup1} 条来自只见过一次的套路（support=1，可信度低）",
             f"  Three-component (D5): {len(tri)} paths from three-component templates "
             f"({len(tri)/max(1,len(paths)):.0%} of {len(paths)}); "
             f"{sup1} from support=1 templates (low confidence)"))
    print(_L("        ⚠ 只打标记：产物一条不删、不排序；support 在台账 template_support 列",
             "        ⚠ Flags only: no products deleted, no ranking; "
             "see the ledger template_support column"))


def _print_cond_model(inv: qb.Inventory) -> None:
    """★ D2（第四十三轮收尾）：条件可行性模型的**标记**（不删产物、不排序、不筛路线）。

    台账 `cond_model` 列在枚举时就写好了（core/query_base._cond_model_note）；
    这里把它汇总到界面输出（build 与 aggregate 都调）。
    空列 = 该反应类不在模型覆盖范围（按类降级到规则层），不是"没算"。
    """
    paths = list(inv.paths)
    marked = [x for x in paths if str(x.get("cond_model") or "").strip()]
    if not marked:
        print(_L(f"  条件模型（D2）：0/{len(paths)} 条出处带可行性标记"
                 f"（覆盖类之外空列 = 按类降级，不是没算）",
                 f"  Condition model (D2): 0/{len(paths)} paths with feasibility flags "
                 f"(empty outside covered classes = class-level fallback, not missing)"))
        return
    import re as _re
    bands, n_ood, n_fail = {}, 0, 0
    for x in marked:
        s = str(x.get("cond_model"))
        if "标记失败" in s:
            n_fail += 1
        m = _re.search(r"p=([0-9.]+)\s+(\S+)", s)
        if m:
            bands[m.group(2)] = bands.get(m.group(2), 0) + 1
        if "分布外" in s:
            n_ood += 1
    btxt = " · ".join(f"{k} {v}" for k, v in sorted(bands.items(), key=lambda kv: -kv[1])) or "无有效档位"
    extra = f"；标记失败 {n_fail} 条" if n_fail else ""
    print(_L(f"  条件模型（D2）：{len(marked)}/{len(paths)} 条出处带可行性标记"
             f"（{btxt}；分布外 {n_ood} 条{extra}）",
             f"  Condition model (D2): {len(marked)}/{len(paths)} paths with feasibility flags "
             f"({btxt}; out-of-distribution {n_ood}{extra})"))
    ex = marked[0]
    print(f"        e.g. [{str(ex.get('rule_name'))[:22]}] {str(ex.get('cond_model'))[:64]}")
    print(_L("        ⚠ 只打标记：不删产物、不排序；标记在台账 cond_model 列",
             "        ⚠ Flags only: no deletion, no ranking; see the ledger cond_model column"))


def _print_direction(inv: qb.Inventory, top: int = 3) -> None:
    """打印方向层摘要（不删产物、不排序，只是把「往哪个方向走」摆出来）。"""
    dir_en = {"方向可疑": "suspicious", "方向未定": "undetermined",
              "方向明确": "clear", "平衡": "equilibrium"}

    def _dl(k):
        return dir_en.get(k, k) if LANG == "en" else k

    def _reason(s):
        if LANG == "en":
            s = str(s).replace(
                "该步脱掉一分子水（脱水/缩合形状，element_delta_shape）；水相里方向相反，应往水解走",
                "This step removes water (dehydration/condensation shape, element_delta_shape); "
                "in aqueous media hydrolysis should dominate.",
            ).replace(
                "ORD 自抽模板（mined_extra / mined_mono）：只有模板没有类型，方向不可判",
                "ORD auto-mined template (mined_extra / mined_mono): template only, "
                "no reaction class; direction cannot be determined.",
            )
        return s

    try:
        ds = qb.direction_summary(inv)
    except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
        print(f"  [warn] 方向摘要算不出来：{type(ex).__name__}: {ex}")
        return
    if not ds.get("by_label"):
        print(_L("  方向层：本次台账没有方向列（旧台账或 --no-direction 跑出来的）",
                 "  Direction layer: no direction column in this ledger "
                 "(old ledger or run with --no-direction)"))
        return
    print(_L("  方向层（缺口②：能生成 + 标出往哪个方向；**不删产物、不排序**）：",
             "  Direction layer (generate + flag direction; no deletion, no ranking):"))
    try:                                         # 顺序跟着 direction.LABELS 走，避免两套口径
        import direction as _dir
        order = [_dir.LABELS[k][0] for k in
                 ("suspect", "equilibrium", "undecided", "clear") if k in _dir.LABELS]
    except Exception:                            # noqa: BLE001
        order = []
    order += [x for x in ds["by_label"] if x not in order]
    for k in order:
        if k not in ds["by_label"]:
            continue
        v = ds["by_label"][k]
        pct = ds["share"][k]
        ex = ds["examples"].get(k, {})
        rules = "|".join(ex.get("rules", [])[:3])
        print(_L(f"    {k:<6} {v:>5} 个产物（{pct:>6.1%}）  e.g. {rules:<34} {ex.get('formula', '')}",
                 f"    {_dl(k):<12} {v:>5} products ({pct:>6.1%})  e.g. {rules:<34} {ex.get('formula', '')}"))
        if ex.get("reason"):
            print(_L(f"           理由：{ex['reason']}", f"           Reason: {_reason(ex['reason'])}"))
    print("    ⚠ " + _L(ds["note"],
                     "Direction flags are reminders only; no products are deleted and nothing "
                     "is ranked; suspicious = opposite to the current medium; "
                     "equilibrium = also a reverse substrate."))


def _print_log_stats() -> None:
    st = qb.stats_of_query_log()
    print(f"  query_log：{st['path']}")
    print(f"  共 {st['n']} 次查询，命中 {st['n_hit']} 次（命中率 {st['hit_rate']:.1%}）")
    if st["by_cmd"]:
        print("  按入口：" + "  ".join(
            f"{k} {v['n']} 次/命中 {v['hit']}" for k, v in sorted(st["by_cmd"].items())))
    if st["by_kind"]:
        print("  输入类型：" + "  ".join(f"{k} {v}" for k, v in
                                     sorted(st["by_kind"].items(), key=lambda kv: -kv[1])))
    if st["top_queries"]:
        print("  查得最多的：")
        for t in st["top_queries"][:10]:
            print(f"    {t['n']:>4} 次（命中 {t['hit']}）  {t['query'][:60]}")
    for n in st["notes"]:
        print(f"  ⚠ {n}")


def cmd_direction(a) -> int:
    """方向层自述：判据表内容 + 当前台账的方向分布（缺口②的可审计视图）。"""
    import direction as _dir
    print("=" * 100)
    print("方向层（框架缺口②）")
    print("=" * 100)
    print(_dir.describe_table())
    print()
    print("  四种标记的含义：")
    for k, (cn, why) in _dir.LABELS.items():
        print(f"    {k:<15} {cn:<8} {why}")
    if a.paths or qb.INVENTORY_CSV.exists():
        inv = _load_inv(a)
        print()
        print(f"  {qb.provenance_line(inv)}")
        _print_direction(inv, top=4)
    return 0


def cmd_aggregate(a) -> int:
    inv = _load_inv(a)
    print("=" * 100)
    print("聚合视图：按反应类型（通用框架的自检指标）")
    print("=" * 100)
    print(f"  {qb.provenance_line(inv)}")
    agg = qb.aggregate_by_rule(inv, limit=a.top)
    print(f"  反应类型 {agg['n_rules']} 类 / 出处路径 {agg['n_paths']} 条\n")
    print(f"  {'反应类型':<24}{'产物':>7}{'路径':>6}{'来源':>6}{'最早轮':>6}"
          f"{'窗口':>6}{'降权':>6}{'无数据':>7}{'占比':>8}")
    print("  " + "-" * 92)
    for r in agg["rows"]:
        print(f"  {str(r['rule'])[:22]:<24}{r['products']:>7}{r['paths']:>6}"
              f"{r['sources']:>6}{str(r['min_round']):>6}"
              f"{r.get('gate_window', 0):>6}{r.get('gate_penalty', 0):>6}"
              f"{r.get('gate_no_data', 0):>7}{r['share']:>7.1%}")
    print("  （窗口=在 ORD 实测条件窗口内 · 降权=试剂/溶剂/温度某路不匹配 · "
          "无数据=该类没有条件窗口，放行=没有条件证据）")
    _print_cond_model(inv)
    for n in agg["notes"]:
        print(f"\n  ⚠ {n}")
    return 0


def cmd_stats(a) -> int:
    print("=" * 100)
    print("查询日志汇总（证据回流：只记录用户查了什么、命中没有）")
    print("=" * 100)
    _print_log_stats()
    return 0


def cmd_build(a) -> int:
    seeds = collect_seeds(a)
    if not seeds:
        print("没有可用输入分子：给 --herb / --coconut / --smiles / --mol 之一")
        return 2
    print("=" * 108)
    print(f"★ 一次枚举 ★  输入 {len(seeds)} 个分子")
    print("=" * 108)
    for nm, sm, src in seeds[:8]:
        print(f"    [{src}] {nm[:24]:<26} {sm[:64]}")
    if len(seeds) > 8:
        print(f"    … 另有 {len(seeds)-8} 个")

    spec = qb.RunSpec(seeds=seeds, cond_name=a.cond, rounds=a.rounds,
                      max_pairs=a.max_pairs, direction=not a.no_direction,
                      reagents=_split_reagents(getattr(a, "reagents", "") or ""),
                      triples=bool(getattr(a, "triples", False)),
                      triples_min_support=int(getattr(a, "triples_min_support", 2)))
    t0 = time.time()
    inv = qb.build_inventory(spec, score=not a.no_score, use_cache=not a.no_ik_cache)
    print_inv_summary(inv)
    _print_gate(inv)
    _print_direction(inv)
    _print_triples(inv)
    _print_cond_model(inv)
    if a.no_save:
        print("  （--no-save：不写文件）")
        return 0
    pf, xf = qb.dump_inventory(inv, Path(a.out) if a.out else qb.INVENTORY_CSV,
                               Path(a.index_out) if a.index_out else qb.INDEX_TSV)
    print(f"  写盘完成 {time.time()-t0:.1f}s")
    print(f"\n  {BOUND_LINE}")
    return 0


# ---------------------------------------------------------------- A 查产物

def cmd_A(a) -> int:
    print("=" * 108)
    print(f"入口 A 查产物：{a.mol}")
    print("=" * 108)
    inv = _load_inv(a)
    print(f"  {qb.provenance_line(inv)}")
    r = qb.query_product(inv, a.mol)
    ident = r["resolved"]
    print(f"  解析：{ident['kind']}"
          + (f" · canonical {ident.get('smiles')}" if ident.get("smiles") else "")
          + (f" · InChIKey {ident.get('inchikey')}" if ident.get("inchikey") else ""))
    if not a.no_log:
        _log_one("A", a.mol, r, r["found"], len(r["hits"]))
        if a.log_stats:
            _print_log_stats()
    if not r["found"]:
        print("\n  ✗ 不在本次产物集里。")
        for n in r["notes"]:
            print(f"     · {n}")
        if ident["kind"] == "名称" and ident.get("candidates"):
            print("     库里同名的分子有：")
            for c in ident["candidates"]:
                print(f"       [{c['db']}] {str(c['name'])[:40]:<42} {str(c.get('smiles'))[:50]}")
        return 0
    for h in r["hits"]:
        print(f"\n  ✓ 在产物集里（{h['n_paths']} 条路径 / {h['n_sources']} 个来源分子）")
        print(f"    规格：{h['formula']}  MW {h['mw']}  重原子 {h['heavy_atoms']}"
              f"  副产物 {h['is_byproduct']}  score {h['score']}（仅信息，不排序）")
        print(f"    最早出现：第 {h['min_round']} 轮 · 涉及反应类型 {len(h['rules'])} 类")
        if h.get("directions"):
            for lab, cnt in sorted(h["directions"].items()):
                why = (h.get("direction_reasons") or {}).get(lab, "")
                print(f"    方向层：{lab}（{cnt} 条路径） {why}")
        if h.get("reversible"):
            print("    ⚠ 引擎标为【可逆/介质相关】（水相里的脱水缩合类）："
                  "多半是平衡产物，别当终产物看")
        if h.get("co_products"):
            print("    同批生成的片段：" + " · ".join(x[:44] for x in h["co_products"][:3]))
        if h["known_names"]:
            print("    库里已有的名字：" + "；".join(
                f"[{x['db']}] {x['name']}" for x in h["known_names"][:4]))
        else:
            print("    库里没有这个名字（预测出的新结构本来就没有名字）")
        print("    出处（来源分子 -> 规则 -> 轮次）：")
        for s in h["sources"][:a.max_sources]:
            label = (s.get("source_label") or s["source_name"] or "(未命名)")[:24]
            print(f"      · [{s.get('role', '?')}] {label:<26} "
                  f"{s['source_smiles'][:40]:<42} {_fmt_paths(s['paths'])}")
        if len(h["sources"]) > a.max_sources:
            print(f"      … 另有 {len(h['sources'])-a.max_sources} 个来源分子")
    for n in r["notes"]:
        print(f"\n  ⚠ {n}")
    return 0


# ---------------------------------------------------------------- B 查底物

def cmd_B(a) -> int:
    print("=" * 108)
    print(f"入口 B 查底物：{a.mol}" + (f"  +  {a.with_}" if a.with_ else ""))
    print("=" * 108)
    if a.with_:
        r = qb.query_substrate_pair(a.mol, a.with_, cond_name=a.cond,
                                    max_products=a.top)
    else:
        r = qb.query_substrate(a.mol, cond_name=a.cond, max_products=a.top)
    if r.get("error"):
        print(f"  ✗ {r['error']}")
        return 2
    print(f"  条件：{r['cond']}   耗时 {r['seconds']}s")
    if r.get("input_canonical"):
        print(f"  输入 canonical：{r['input_canonical']}")
    for n in r.get("engine_notes", []):
        print(f"        {n}")
    print(f"  产物 {r['n_products']} 个"
          + (f"（涉及 {r['n_rules']} 类反应）" if r.get("n_rules") else "")
          + f"，下面列出 {r['n_shown']} 个")
    print()
    print(f"  {'分':>6}{'激活':>7}{'方向':>6}  {'反应类型':<24}{'分子式':<20}SMILES")
    print("  " + "-" * 104)
    for p in r["products"]:
        sc = p.get("score")
        sc_s = f"{sc:>6.3f}" if isinstance(sc, float) else f"{'-':>6}"
        rev = "可逆" if p.get("reversible") else ""
        byp = "副产物" if p.get("is_byproduct") else ""
        print(f"  {sc_s}{p['activation']:>7.2f}{rev:>6}  {str(p['rule_name'])[:22]:<24}"
              f"{str(p.get('formula', '')):<20}{p['smiles'][:56]}"
              + (f"   [{byp}]" if byp else ""))
    for n in r["notes"]:
        print(f"\n  ⚠ {n}")
    if not a.no_log:
        _log_one("B", a.mol + ((" + " + a.with_) if a.with_ else ""), r,
                 bool(r.get("n_products")), int(r.get("n_products", 0)),
                 extra={"n_rules": r.get("n_rules", 0)})
        if a.log_stats:
            _print_log_stats()
    if a.out:
        _dump_rows(r["products"], a.out)
    return 0


# ---------------------------------------------------------------- C 结果集检索

def cmd_C(a) -> int:
    if a.similar:
        return _cmd_similar(a)
    if not any([a.name, a.formula, a.smiles, a.inchikey, a.substructure]):
        print("  提示：没给过滤条件 -> 输出全量产物清单")
    print("=" * 108)
    print("入口 C 结果集检索：" + ", ".join(
        f"{k}={v}" for k, v in [("name", a.name), ("formula", a.formula),
                                ("smiles", a.smiles), ("inchikey", a.inchikey),
                                ("substructure", a.substructure),
                                ("max_round", a.max_round)] if v is not None))
    print("=" * 108)
    inv = _load_inv(a)
    print(f"  {qb.provenance_line(inv)}")
    r = qb.query_inventory(inv, name=a.name, formula=a.formula, smiles=a.smiles,
                           inchikey=a.inchikey, substructure=a.substructure,
                           max_round=a.max_round,
                           include_byproducts=not a.no_byproducts, limit=a.top)
    if r.get("error"):
        print(f"  ✗ {r['error']}")
        return 2
    if r.get("substructure_parsed_as"):
        print(f"  子结构按 {r['substructure_parsed_as']} 解析")
    if a.name and r.get("name_candidates"):
        print(f"  名称在库里匹配到 {len(r['name_candidates'])} 个结构候选：")
        for c in r["name_candidates"][:5]:
            print(f"    [{c['db']}] {str(c['name'])[:38]:<40} {str(c.get('smiles'))[:46]}")
    print(f"  命中 {r['n_hits']} 个产物分子，下面列出 {r['n_shown']} 个（不高亮、不排序）")
    print()
    if r["hits"]:                       # 先把名称表扫进内存（否则扫描提示会插在表格中间）
        qb.names_of_inchikey(r["hits"][0]["inchikey"], limit=1)
    print(f"  {'轮':>3}  {'分子式':<20}{'重原子':>6}{'来源数':>6}  {'反应类型':<24}"
          f"{'方向':<6}{'来源（首个）':<20}SMILES")
    print("  " + "-" * 104)
    for h in r["hits"]:
        names = qb.names_of_inchikey(h["inchikey"], limit=1) if h["inchikey"] else []
        nm = names[0]["name"][:18] if names else "-"
        src0 = (h.get("sources") or ["-"])[0]
        rev = "可逆" if h.get("reversible") else ""
        print(f"  {h['min_round'] if h['min_round'] is not None else '?':>3}  "
              f"{str(h['formula'])[:18]:<20}{str(h['heavy_atoms']):>6}"
              f"{h['n_sources']:>6}  {'|'.join(h['rules'])[:22]:<24}{rev:<6}"
              f"{str(src0)[:18]:<20}{h['smiles'][:44]}")
    if a.name and r["n_hits"] == 0:
        n_c = len(r.get("name_candidates") or [])
        print(f"\n  ⚠ 按名称「{a.name}」在产物集里 0 命中：库内候选 {n_c} 个，"
              f"但它们的结构没出现在本次枚举结果里。")
        print("     → 这正是边界①：查不到 ≠ 不存在（= 当前模板库 + 当前轮数没枚举出来）。")
        print("     → 想直接验证某个库内分子能生成什么，请用入口 B 把它当底物跑。")
        print("     → 想找结构相近的候选，请用 C --similar。")
    for n in r["notes"]:
        print(f"\n  ⚠ {n}")
    if not a.no_log:
        _log_one("C", a.name or a.formula or a.smiles or a.inchikey or a.substructure,
                 r, r["n_hits"] > 0, r["n_hits"])
        if a.log_stats:
            _print_log_stats()
    if a.out:
        _dump_rows(r["hits"], a.out)
    return 0


def _cmd_similar(a) -> int:
    """入口 C+：相似度检索（结构接近的产物候选）。"""
    inv = _load_inv(a)
    print("=" * 108)
    print(f"入口 C+ 相似度检索：{a.similar}（Tanimoto ≥ {a.tanimoto}）")
    print("=" * 108)
    print(f"  {qb.provenance_line(inv)}")
    r = qb.query_similar(inv, a.similar, threshold=a.tanimoto, limit=a.top,
                         paths_file=Path(a.paths) if a.paths else None)
    if r.get("error"):
        print(f"  ✗ {r['error']}")
        return 2
    f = r["fp_stats"]
    print(f"  查询结构：{r['query_smiles'][:70]}")
    print(f"  指纹 {r['fps']['type']}(r={r['fps']['radius']}, {r['fps']['nbits']}bit) · "
          f"{r['fps']['metric']}；指纹表 {f['n']} 个"
          f"（本次算 {f['computed']}、复用 {f['reused']}、失败 {f['fail']}，{f['seconds']}s）")
    if f["fail_examples"]:
        print(f"    ⚠ 算不出指纹的样例（不静默）：{f['fail_examples']}")
    print(f"  命中 {r['n_hits']} 个产物分子，下面列出 {r['n_shown']} 个\n")
    print(f"  {'相似度':>7}{'轮':>4}  {'分子式':<20}{'重原子':>6}  {'反应类型':<22}"
          f"{'方向':<6}{'库里名字':<18}SMILES")
    print("  " + "-" * 104)
    for h in r["hits"]:
        nm = (h["known_names"][0][:16] if h.get("known_names") else "-")
        rev = "可逆" if h.get("reversible") else ""
        print(f"  {h['tanimoto']:>7.3f}{h['min_round'] if h['min_round'] is not None else '?':>4}  "
              f"{str(h['formula'])[:18]:<20}{str(h['heavy_atoms']):>6}  "
              f"{'|'.join(h['rules'])[:20]:<22}{rev:<6}{nm:<18}{h['smiles'][:40]}")
    for n in r["notes"]:
        print(f"\n  ⚠ {n}")
    if not a.no_log:
        _log_one("C-similar", a.similar, r, r["n_hits"] > 0, r["n_hits"],
                 extra={"threshold": a.tanimoto})
        if a.log_stats:
            _print_log_stats()
    if a.out:
        _dump_rows(r["hits"], a.out)
    return 0


# ---------------------------------------------------------------- selftest

def cmd_selftest(a) -> int:
    """小规模自检：三个入口都得有可判定的结果。"""
    print("=" * 108)
    print("自检：底座 + A/B/C 三个入口")
    print("=" * 108)
    checks = []
    seeds = [("水杨酸", qb.canon("O=C(O)c1ccccc1O"), "自检"),
             ("酪胺", qb.canon("NCCc1ccc(O)cc1"), "自检")]
    spec = qb.RunSpec(seeds=seeds, cond_name=a.cond, rounds=a.rounds)
    inv = qb.build_inventory(spec, score=True)
    print_inv_summary(inv)
    n_prod = inv.stats.n_products
    n_index = len(inv)
    # ★ 2026-10-15：索引按 InChIKey 去重，而 InChI 标准键会把「电荷离域」的不同写法归一
    #   （实测例：水杨酸的酚氧负离子 vs 羧基负离子写法 → 同一 UHFFFAOYSA-M 键）。
    #   不变量升级为：产物数 == 索引数 + 同 IK 折叠数（折叠原因可见、不可静默）。
    _ik2smi = {}
    for _r in inv.paths:
        _k = _r.get("product_inchikey")
        if _k:
            _ik2smi.setdefault(_k, set()).add(_r.get("product_smiles"))
    n_collapse = sum(len(v) - 1 for v in _ik2smi.values() if len(v) > 1)
    checks.append((f"底座：产物 {n_prod} 个 == 索引 {n_index} + IK 折叠 {n_collapse}",
                   n_prod == n_index + n_collapse))
    checks.append((f"底座：至少有产物（{n_prod} > 0）", n_prod > 0))
    checks.append((f"底座：出处路径 {inv.stats.n_paths_kept} 条 > 0",
                   inv.stats.n_paths_kept > 0))
    ik_ok = inv.stats.ik_ok
    checks.append((f"索引：InChIKey 成功 {ik_ok} / 失败 {inv.stats.ik_fail}",
                   ik_ok >= max(1, n_prod - 2)))

    # ---- 底座：InChIKey 超时保护的"放弃/记名"通路（用解析不了的分子故意触发失败） ----
    _cache, st = qb.inchikeys_of(["C1CC", "CCO"], {}, workers=2)
    checks.append((f"索引：坏分子不静默（失败 {st['fail']} / 有记录 {bool(st['examples_failed']) or st['fail']==0}）",
                   st["fail"] >= 1 or st["examples_failed"]))

    # ---- A：抽 3 个真产物 + 1 个肯定不在的分子 ----
    keys = list(inv.index().keys())
    hit_ok = 0
    samples = keys[:3] if len(keys) >= 3 else keys
    for k in samples:
        e = inv.index()[k]
        r = qb.query_product(inv, e["smiles"])
        if r["found"] and r["hits"][0]["smiles"] == e["smiles"]:
            hit_ok += 1
    checks.append((f"A：抽 {len(samples)} 个真产物用 SMILES 查，命中 {hit_ok} 个",
                   samples and hit_ok == len(samples)))
    r_neg = qb.query_product(inv, "O=C(O)C(F)(F)F")     # 三氟乙酸：不该在产物里
    checks.append((f"A：三氟乙酸应查不到（当前 {r_neg['found']}）",
                   r_neg["found"] is False))
    if keys and inv.index()[keys[0]]["inchikey"]:
        ik = inv.index()[keys[0]]["inchikey"]
        r_ik = qb.query_product(inv, ik)
        checks.append((f"A：按 InChIKey {ik[:14]}… 查询命中", r_ik["found"]))

    # ---- B：单底物 ----
    rB = qb.query_substrate(seeds[0][1], cond_name=a.cond, max_products=5)
    checks.append((f"B：单底物产物 {rB['n_products']} 个（>0）", rB["n_products"] > 0))
    rB2 = qb.query_substrate_pair(seeds[0][1], seeds[1][1], cond_name=a.cond,
                                  max_products=5)
    checks.append((f"B：双底物产物 {rB2['n_products']} 个（>0）", rB2["n_products"] > 0))

    # ---- C：分子式 / 子结构 / 全量 ----
    if keys:
        form = inv.index()[keys[0]]["formula"]
        rC = qb.query_inventory(inv, formula=form, limit=100)
        checks.append((f"C：按分子式 {form} 查到 {rC['n_hits']} 个（>=1）", rC["n_hits"] >= 1))
    rC2 = qb.query_inventory(inv, substructure="c1ccccc1", limit=5)
    checks.append((f"C：子结构 苯环 查到 {rC2['n_hits']} 个", rC2["n_hits"] >= 0))
    rC3 = qb.query_inventory(inv, limit=5)
    # 同 IK 折叠口径（见底座不变量）：全量 = 产物数 - 折叠数
    checks.append((f"C：不加过滤返回全量 {rC3['n_hits']} 个（== {n_prod - n_collapse}）",
                   rC3["n_hits"] == n_prod - n_collapse))
    rC4 = qb.query_inventory(inv, name="水杨酸", limit=10)
    checks.append((f"C：按名称「水杨酸」查到 {rC4['n_hits']} 个（名称查已接通库）",
                   True))

    # ---- C+ 相似度检索 ----
    rS = qb.query_similar(inv, seeds[0][1], threshold=0.3, limit=10)
    checks.append((f"C+：相似度检索（阈值 0.3）命中 {rS['n_hits']} 个，"
                   f"指纹算 {rS['fp_stats']['computed']}/复用 {rS['fp_stats']['reused']}",
                   not rS.get("error") and rS["fp_stats"]["fail"] == 0))
    if rS["hits"]:
        sims = [h["tanimoto"] for h in rS["hits"]]
        keys = [h["inchikey"] or h["smiles"] for h in rS["hits"]]
        checks.append((f"C+：结果按相似度降序 {sims[0]:.3f} >= {sims[-1]:.3f}",
                       sims == sorted(sims, reverse=True)))
        checks.append((f"C+：结果无重复分子（{len(keys)} 个键）",
                       len(keys) == len(set(keys))))
        checks.append((f"C+：相似度高于查询自身 = 1.0（自相似），当前 "
                       f"{max(sims):.3f}", max(sims) <= 1.0 + 1e-9))

    # ---- 方向层（缺口②）----
    dspec = qb.RunSpec(seeds=seeds, cond_name=a.cond, rounds=1)
    dinv = qb.build_inventory(dspec, score=False)
    dsum = qb.direction_summary(dinv)
    n_labeled = sum(dsum["by_label"].values())
    checks.append((f"方向：{n_labeled}/{dsum['n_products']} 个产物有方向标记 "
                   f"{dsum['by_label']}",
                   n_labeled == dsum["n_products"] and n_labeled > 0))
    try:
        import direction as _dir
        cond = dspec.cond()
        j = _dir.judge("esterification", cond)
        checks.append((f"方向：水相里的 esterification 判为「{j['label_cn']}」"
                       f"（期望 方向可疑）",
                       j["label"] == "suspect"))
        j2 = _dir.judge("suzuki", cond)
        checks.append((f"方向：suzuki 判为「{j2['label_cn']}」（期望 方向明确）",
                       j2["label"] == "clear"))
        j3 = _dir.judge("mined_mono", cond)
        checks.append((f"方向：自抽模板 mined_mono 判为「{j3['label_cn']}」"
                       f"（期望 方向未定）", j3["label"] == "undecided"))
        # ★ D1（2026-10-13）：可计算的形状判据 —— 副产物里有一分子水 = 脱水/缩合形状
        j4 = _dir.judge("mined_mono", cond, co_products=("O",))
        checks.append((f"方向：D1 形状判据（副产物含水）判为「{j4['label_cn']}」"
                        f"（来源 {j4['source']}，期望 co_product_shape）",
                        j4["source"] == "co_product_shape"
                        and j4["label"] in ("suspect", "clear", "equilibrium")))
        j5 = _dir.judge("mined_mono", cond, co_products=("CCO",))
        checks.append((f"方向：D1 形状判据不误判（副产物是乙醇）判为「{j5['label_cn']}」"
                        f"（期望 方向未定）", j5["label"] == "undecided"))
        # ★ D1 收紧（第四十三轮）：多产物且其余产物不小 -> 不按"元素收支"判形状
        j6 = _dir.judge("mined_mono", cond, co_products=("CCO",),
                        element_delta=(-2, -4, -1))
        checks.append((f"方向：D1 收紧（副产物是乙醇+收支像脱水）判为「{j6['label_cn']}」"
                        f"（期望 方向未定；不冤枉多产物模板）", j6["label"] == "undecided"))
        j7 = _dir.judge("mined_mono", cond, co_products=("O",),
                        element_delta=(-2, -4, -1))
        checks.append((f"方向：D1 收紧对照（副产物是水+收支像脱水）判为「{j7['label_cn']}」"
                        f"（来源 {j7['source']}，期望 element_delta_shape 且 方向可疑）",
                        j7["source"] == "element_delta_shape"
                        and j7["label"] == "suspect"))
        # ★ D4（2026-10-13）：RunSpec 能把试剂注入生产条件
        sp4 = qb.RunSpec(seeds=[], cond_name=a.cond, rounds=1, reagents=("NaBH4",))
        checks.append((f"D4：RunSpec.reagents -> Conditions.reagents（{sp4.cond().reagents}）",
                       sp4.cond().reagents == ("NaBH4",)))
        checks.append((f"方向：判据表已加载（{len(_dir.class_to_family())} 个类名映射）",
                       len(_dir.class_to_family()) >= 30))
    except Exception as ex:                      # noqa: BLE001
        checks.append((f"方向：判据表加载异常 {type(ex).__name__}: {ex}", False))

    # ---- 聚合视图 ----
    agg = qb.aggregate_by_rule(inv, limit=50)
    checks.append((f"聚合：反应类型 {agg['n_rules']} 类，路径合计 {agg['n_paths']} "
                   f"== 台账路径 {inv.stats.n_paths_kept}",
                   agg["n_paths"] == inv.stats.n_paths_kept and agg["n_rules"] >= 1))

    # ---- 查询日志（证据回流）----
    n_w = qb.dump_query_log([{"ts": "selftest", "cmd": "selftest",
                              "query": "selftest_probe", "found": False}])
    stq = qb.stats_of_query_log()
    checks.append((f"日志：写入 {n_w} 条后共 {stq['n']} 条（含本行）",
                   n_w == 1 and stq["n"] >= 1))

    print()
    n_fail = 0
    for text, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {text}")
        n_fail += 0 if ok else 1
    print(f"\n  合计 {len(checks)} 项，FAIL {n_fail}")
    return 1 if n_fail else 0


# ---------------------------------------------------------------- 公共

def _load_inv(a) -> qb.Inventory:
    p = Path(a.paths) if a.paths else qb.INVENTORY_CSV
    t0 = time.time()
    inv = qb.load_inventory(p)
    print(f"  台账 {p.name}：{len(inv.paths)} 条出处路径，读入 {time.time()-t0:.1f}s")
    return inv


def _dump_rows(rows, out: str) -> None:
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        print("  （没有行可导出）")
        return
    cols = list({k: None for r in rows for k in r}.keys())
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("|".join(map(str, v)) if isinstance(v, (list, tuple)) else v)
                        for k, v in r.items()})
    print(f"  导出 {len(rows)} 行 -> {p}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="查询式交互：一次枚举 + 一份索引 + A/B/C 三个查询入口")
    sub = ap.add_subparsers(dest="cmd")

    def add_common(p):
        p.add_argument("--paths", default=None,
                       help=f"台账 CSV（默认 {qb.INVENTORY_CSV.name}）")
        p.add_argument("--cond", default="煎煮", help="条件模板（煎煮/水提/醇提/…）")
        p.add_argument("--triples-min-support", type=int, default=2,
                       help="★D5：3 组分模板的 support 门槛（默认 2；=1 会把 2,443 条全上，很慢）")
        p.add_argument("--triples", action="store_true",
                       help="★D5：启用 3 组分模板（2,443 条；默认关——实测会把构建从 6s 拖到 >400s）")
        p.add_argument("--reagents", default="",
                       help="★D4：本批处理加入的辅助试剂（逗号/分号分隔的 SMILES 或名字）。"
                            "不填则 Conditions.reagents 为空，「必需试剂判零」不触发")
        p.add_argument("--no-log", action="store_true",
                       help="不把本次查询写进 query_log.jsonl（证据回流默认开）")
        p.add_argument("--log-stats", action="store_true",
                       help="查完顺便打印查询日志汇总")

    pb = sub.add_parser("build", help="一次枚举：产物台账 + InChIKey 索引")
    add_common(pb)
    pb.add_argument("--herb", default=None, help="药材名（可逗号分隔）")
    pb.add_argument("--coconut", type=int, default=0, help="从 COCONUT 随机取 n 个当底物")
    pb.add_argument("--smiles", default=None, help="逗号分隔的 SMILES 列表")
    pb.add_argument("--mol", action="append", default=None, help="单个 SMILES（可重复）")
    pb.add_argument("--limit", type=int, default=15, help="★每味药★的成分上限（可给多味药）")
    pb.add_argument("--rounds", type=int, default=1, help="★轮数由你掌握★（默认 1）")
    pb.add_argument("--max-pairs", type=int, default=4000, help="单轮底物对上限")
    pb.add_argument("--no-score", action="store_true", help="不算 score 列（更快）")
    pb.add_argument("--no-direction", action="store_true",
                    help="关掉方向层（缺口②的方向标记）")
    pb.add_argument("--no-ik-cache", action="store_true", help="不读不写 InChIKey 缓存")
    pb.add_argument("--no-save", action="store_true", help="只打印，不写文件")
    pb.add_argument("--out", default=None, help="台账 CSV 输出路径")
    pb.add_argument("--index-out", default=None, help="索引 TSV 输出路径")
    pb.set_defaults(func=cmd_build)

    pa = sub.add_parser("A", help="入口 A：查产物（在不在 / 由哪条路径生成）")
    add_common(pa)
    pa.add_argument("--mol", required=True, help="SMILES / 分子式 / InChIKey / 库里的名称")
    pa.add_argument("--max-sources", type=int, default=20, help="最多列几个来源分子")
    pa.set_defaults(func=cmd_A)

    pbd = sub.add_parser("B", help="入口 B：查底物（一个分子 -> 产物）")
    add_common(pbd)
    pbd.add_argument("--mol", required=True, help="底物 SMILES")
    pbd.add_argument("--with", dest="with_", default=None, help="再加一个分子（双分子反应）")
    pbd.add_argument("--top", type=int, default=50, help="最多列几条产物")
    pbd.add_argument("--out", default=None, help="把产物清单导成 CSV")
    pbd.set_defaults(func=cmd_B)

    pc = sub.add_parser("C", help="入口 C：结果集检索（名称/分子式/SMILES/子结构）")
    add_common(pc)
    pc.add_argument("--name", default=None, help="库里的名称（新预测结构没有名字）")
    pc.add_argument("--formula", default=None, help="分子式，如 C7H6O2")
    pc.add_argument("--smiles", default=None, help="精确结构（canonical 后比对）")
    pc.add_argument("--inchikey", default=None, help="InChIKey（全串）")
    pc.add_argument("--substructure", default=None, help="子结构 SMARTS/SMILES，如 c1ccccc1")
    pc.add_argument("--similar", default=None,
                    help="★相似度检索★：给一个分子，返回结构相近的产物（Tanimoto）")
    pc.add_argument("--tanimoto", type=float, default=0.4, help="相似度阈值（默认 0.4）")
    pc.add_argument("--max-round", type=int, default=None, help="只要「最早出现在第 N 轮及之前」")
    pc.add_argument("--no-byproducts", action="store_true", help="剔除小分子副产物")
    pc.add_argument("--top", type=int, default=200, help="最多列几条")
    pc.add_argument("--out", default=None, help="把命中清单导成 CSV")
    pc.set_defaults(func=cmd_C)

    ps = sub.add_parser("selftest", help="小规模自检 A/B/C 三个入口")
    add_common(ps)
    ps.add_argument("--rounds", type=int, default=1)
    ps.set_defaults(func=cmd_selftest)

    pag = sub.add_parser("aggregate", help="聚合视图：按反应类型汇总本次枚举")
    add_common(pag)
    pag.add_argument("--top", type=int, default=40, help="最多列几类反应")
    pag.set_defaults(func=cmd_aggregate)

    pst = sub.add_parser("stats", help="查询日志汇总（证据回流）")
    add_common(pst)
    pst.set_defaults(func=cmd_stats)

    pdi = sub.add_parser("direction", help="方向层自述：判据表 + 当前台账的方向分布")
    add_common(pdi)
    pdi.set_defaults(func=cmd_direction)

    a = ap.parse_args(argv)
    if not getattr(a, "cmd", None):
        ap.print_help()
        return 0
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
