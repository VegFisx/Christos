# -*- coding: utf-8 -*-
r"""★ 第十八轮：用 ORD（真实文献反应）测条件门控的【误杀率】（false negative）★

背景
----
HTE 上我们实测的是【假阳性 94.9%】（引擎对真实失败条件也说能反应）。
反方向从没测过：**真实文献里确实发生了的反应（ORD 里每条都有收率），
我们的条件门控会不会把它判零？**
ORD 每条都是真实做过、有收率的反应 -> 正好当「真·会发生」的标尺。

数据源（只读，别人刚产出，不重造）
----------------------------------
  chemreact-staging\reports\ord_condition_dataset\shard_0000..0177.parquet
      178 个分片，共 925,943 行（+ 同名 .stats.json）
      schema 见 tools\ord_condition_dataset.py 的 ROW_SCHEMA（本脚本只读，不改它）

★ 口径（写死，先定再测）★
--------------------------
抽样：
  - duckdb `read_parquet('shard_*.parquet') USING SAMPLE --limit ROWS (reservoir, --seed)`
    -> **按【行】在 178 个分片上均匀抽**（不是按片抽），固定 seed 可复现；
       输出 meta.sample.id_hash = sorted(reaction_id) 的 sha1，便于验证可复现性。
  - --limit 的含义 = **抽多少行**（不是评测多少条）；过滤后剩多少条如实报告。

入评测集（按此顺序判定，互斥，先命中先计数）：
  1 fail_product_missing      记录产物为空（product_smiles 空）
  2 fail_product_unparsable   产物 SMILES RDKit 解析不了
  3 fail_no_reactant_smiles   role=REACTANT 的成分一个 SMILES 都没有
  4 fail_reactants_lt2        REACTANT 成分 < 2
  5 fail_reactants_gt2        REACTANT 成分 > 2（这类不能判"哪一对"，会污染口径）
  6 fail_reactant_unparsable  任一 REACTANT SMILES 解析不了
  7 dup_skipped               与已入集记录同 (产物, 排序后底物集) -> 去重
  -> 剩下的才是评测集（qualified）
  ★ REACTANT 数从 `reactant_smiles_components`（分号分隔）数，不是 reactants_n
    （reactants_n = CXSMILES 左侧全部片段数，含被标成其它角色的，口径不同，单列对照计数）。

条件构造（每条记录）：conditions.model.Conditions
  - temperature：用记录 temperature_C（KELVIN/FAHRENHEIT 已由上游换算）。
    ★ 温度缺失的行【不当 0 ℃】：单独一组 S_notemp，用引擎默认温度 100 ℃ 跑，
      并在报告里写明这是【推断】选择（不是记录的真实温度）；
      S_temp = 有温度子集，S_all = 全部。
    ★ setpoint=0 ℃ 是真实冰浴（上游已核 procedure 原文），按 0 ℃ 传入，另单列 S_ice。
  - solvent：取 solvent_names 第一个；缺则 solvent_source=='cxsmiles_agents' 时用该
    agents 串；再缺则 'organic'。【推断】选择。注：cond_activation() 里溶剂只能【降权到
    0.6】不能判零，故溶剂写法不影响命中/判零（见下）。
  - catalyst：ORD 催化剂名按关键词归到 model.CATALYSTS 的 5 类（metal/acid/base/
    enzyme/light），归不上记 None。【推断】建模选择。
    ★【实测·代码审查】cond_activation() 里 'catalyst' 出现 0 次 -> 该字段对本次
      指标无任何影响（grep core\smartreact_engine.py "catalyst" = 0 命中）。
  - reagents：ORD 该数据集 REACTANT/SOLVENT/CATALYST 之外【没有 REAGENT 角色】
      （上游报告：reagent 可得率 0%），故一律传空元组 -> 必需试剂门控走
      「条件里没写试剂时不检查」分支（不判零）。这是本口径的重要限制，报告里写明。

三个固定配置（显式传参，不依赖默认值）：
  A_纯模板库     use_extra_templates=False, gate_conditions=False
  B_模板库加门控 use_extra_templates=False, gate_conditions=True
  C_当前默认     use_extra_templates=True,  gate_conditions=True

每条记录：core.smartreact_engine.SmartReactEngine.step(comps, cond, round_no=1)
  命中（hit）= 记录里的产物（canon_plain 归一）出现在输出产物 SMILES 集合里。
  判零（gated_zero）=
      ① 引擎自带计数：step() 后 eng.stats["gated_zero_total"] > 0
      ② ★ 判零率主口径：A 有产物 而 B 无产物（A/B 模板集完全相同、只差门控开关，
         所以这个差就是"门控把那对的枚举结果全判零了"）——不依赖引擎计数器语义。
      ③ 交叉校验：eng.stats["gated_zero_total"] > 0 且 len(out)==0。

四个要报的数（绝对数 + 百分比）：
  1 命中率
  2 门控判零率
  3 ★ 误杀率 = B 命中率相对 A 命中率的下降 =(hitA - hitB)/hitA
  4 C 相对 A/B 的变化

用法
----
  python tools\ord_gate_falsenegative.py --limit 50                     # 冒烟
  python tools\ord_gate_falsenegative.py --limit 3000 --seed 20261013   # 正式
  python tools\ord_gate_falsenegative.py --limit 3000 --configs A,B

只读：不写 ord-data/、不写 D:\TCMAI\、不改 core\* 与 tools\hte_*.py 等被点名文件。
输出：reports\ord_gate_falsenegative.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules",
           STAGE / "libs", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb                                     # noqa: E402
from rdkit import Chem, RDLogger                  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import mapped_chem as mc                          # noqa: E402  （canon_plain 单一真相）
from model import Conditions                      # noqa: E402
from engine import Compound                       # noqa: E402
from smartreact_engine import SmartReactEngine    # noqa: E402

SHARDS = STAGE / "reports" / "ord_condition_dataset"
SHARD_TOTAL = 178          # 分片数（上游报告实测：178 片 / 925,943 行）
ROWS_TOTAL = 925943
DEFAULT_OUT = STAGE / "reports" / "ord_gate_falsenegative.json"

# 抽样本用到的列（只读）
COLS = ("reaction_id, reactants, reactants_n, reactant_smiles_components, "
        "product, product_smiles, yield_percent, temperature_C, temperature_source, "
        "solvent_names, solvent_smiles, solvent_source, catalyst_names, catalyst_smiles")

# ---------------------------------------------------------------- 三配置
ALL_CONFIGS = {
    "A_纯模板库":     dict(use_extra_templates=False, gate_conditions=False),
    "B_模板库加门控": dict(use_extra_templates=False, gate_conditions=True),
    "C_当前默认":     dict(use_extra_templates=True,  gate_conditions=True),
}
CFG_SHORT = {"A": "A_纯模板库", "B": "B_模板库加门控", "C": "C_当前默认"}

FAIL_KEYS = ["fail_product_missing", "fail_product_unparsable",
             "fail_no_reactant_smiles", "fail_reactants_lt2",
             "fail_reactants_gt2", "fail_reactant_unparsable", "dup_skipped"]
SUBSETS = ["S_all", "S_temp", "S_notemp", "S_ice"]

# ---------------------------------------------------------------- 催化剂归类
_METAL_TOKENS = ("pd", "pt", "ni", "cu", "fe", "rh", "ir", "ru", "co", "mn", "zn",
                 "ag", "au", "ti", "zr", "mo", "w", "cr", "v", "sn", "al", "mg",
                 "ca", "in", "bi", "sb", "la", "ce", "yb", "sc", "hf", "re", "os",
                 "cd", "hg", "li", "na", "k", "cs", "ba", "sr", "y", "nb", "ta")
_ACID_TOKENS = ("hcl", "hydrochloric", "h2so4", "sulfuric", "hno3", "nitric",
                "tsOH".lower(), "tosic", "toluenesulfonic", "acetic", "acoh", "tfa",
                "trifluoroacetic", "phosphoric", "h3po4", "acid", "amberlyst",
                "zeolite", "silica", "alumina", "hbf4", "hclo4")
_BASE_TOKENS = ("naoh", "koh", "lioh", "cs2co3", "k2co3", "na2co3", "li2co3",
                "csf", "kf", "kotbu", "tbuok", "naotbu", "nah", "lda", "lihmds",
                "dbu", "dabco", "dmap", "triethylamine", "et3n", "dipea", "pyridine",
                "hydroxide", "carbonate", "bicarbonate", "phosphate", "amine",
                "guanidine", "amidine", "morpholine", "piperidine", "aniline")
_ENZYME_TOKENS = ("enzyme", "lipase", "esterase", "protease", "amylase", "cellulase",
                  "ketoreductase", "transaminase", "aldolase", "p450", "cal-b",
                  "novozyme", "whole cell", "adh-", "nad(p)", "atp")
_LIGHT_TOKENS = ("hv", "light", "photo", "irradiat", "led", "solar", "uv")


def catalyst_class(name: str):
    """ORD 催化剂名 -> model.CATALYSTS 的粗类别。【推断】关键词归类，不是实测值。"""
    if not name:
        return None
    s = str(name).strip().lower()
    if not s:
        return None
    for t in _ENZYME_TOKENS:
        if t in s:
            return "enzyme"
    for t in _LIGHT_TOKENS:
        if t in s:
            return "light"
    for t in _ACID_TOKENS:
        if t in s:
            return "acid"
    for t in _BASE_TOKENS:
        if t in s:
            return "base"
    # 金属：按元素符号做词边界匹配（"Pd(OAc)2" -> Pd；避免 "Al" 撞进普通词里）
    import re
    for sym in (t.capitalize() for t in sorted(set(_METAL_TOKENS), key=len, reverse=True)):
        if re.search(r"(?<![A-Za-z])" + re.escape(sym) + r"(?![a-z])", name):
            return "metal"
    return None


# ---------------------------------------------------------------- 抽样
def draw_sample(limit: int, seed: int, verbose: bool = True):
    glob = (SHARDS / "shard_*.parquet").as_posix()
    con = duckdb.connect()
    con.execute("SET memory_limit='2000MB'")
    con.execute("SET threads=2")
    t0 = time.time()
    rows = con.execute(
        f"SELECT filename, {COLS} FROM read_parquet('{glob}', filename=true) "
        f"USING SAMPLE {limit} ROWS (reservoir, {seed})").fetchall()
    con.close()
    names = ["filename"] + [c.strip() for c in COLS.split(",")]
    recs = [dict(zip(names, r)) for r in rows]
    shard_files = Counter(Path(str(r["filename"])).name for r in recs)
    ids = sorted(str(r["reaction_id"]) for r in recs)
    id_hash = hashlib.sha1("\n".join(ids).encode("utf-8")).hexdigest()
    if verbose:
        print(f"[sample] reservoir 抽 {len(recs)} 行  seed={seed}  "
              f"{time.time()-t0:.1f}s  id_hash={id_hash[:12]}  "
              f"覆盖分片 {len(shard_files)}/{SHARD_TOTAL}  "
              f"（最集中一片 {max(shard_files.values()) if shard_files else 0} 行）")
    return recs, id_hash, {"n_shards_covered": len(shard_files),
                           "max_rows_in_one_shard": (max(shard_files.values())
                                                     if shard_files else 0),
                           "rows_per_shard_top5": shard_files.most_common(5)}


def print_raw(recs, n=5, width=260):
    print("=" * 100)
    print(f"① 原始记录（抽到的前 {min(n, len(recs))} 条，未做任何加工）")
    print("=" * 100)
    for i, r in enumerate(recs[:n]):
        print(f"--- [{i}] reaction_id={r['reaction_id']}")
        for k in ("reactants", "reactants_n", "reactant_smiles_components",
                  "product", "product_smiles", "temperature_C", "temperature_source",
                  "solvent_names", "solvent_smiles", "solvent_source",
                  "catalyst_names", "yield_percent"):
            v = r.get(k)
            s = "None" if v is None else str(v)
            if len(s) > width:
                s = s[:width] + f"…(+{len(s)-width})"
            print(f"      {k:<28} {s}")
    print()


# ---------------------------------------------------------------- 过滤 / 条件
def classify(rec, seen_keys, no_dedup=False):
    """返回 (status, payload)。status='ok' 时 payload=(reacs, prod_canon, key)。"""
    prod = rec.get("product_smiles")
    if not prod or not str(prod).strip():
        return "fail_product_missing", None
    prod_canon = mc.canon_plain(str(prod))
    if prod_canon is None:
        return "fail_product_unparsable", None
    raw = rec.get("reactant_smiles_components") or ""
    reacs = [s.strip() for s in str(raw).split(";") if s.strip()]
    if not reacs:
        return "fail_no_reactant_smiles", None
    if len(reacs) < 2:
        return "fail_reactants_lt2", None
    if len(reacs) > 2:
        return "fail_reactants_gt2", None
    canons = [mc.canon_plain(s) for s in reacs]
    if any(c is None for c in canons):
        return "fail_reactant_unparsable", None
    if not no_dedup:
        key = (prod_canon, tuple(sorted(canons)))
        if key in seen_keys:
            return "dup_skipped", None
        seen_keys.add(key)
    return "ok", (reacs, prod_canon)


def build_cond(rec, notemp_temp: float = 100.0):
    """记录条件 -> Conditions。【推断】缺失温度用 notemp_temp（默认 = 引擎默认 100 ℃，不当 0 ℃）。"""
    t = rec.get("temperature_C")
    has_t = t is not None
    temp = float(t) if has_t else float(notemp_temp)
    sol = None
    sn = rec.get("solvent_names")
    if sn:
        sol = str(sn).split(";")[0].strip() or None
    if not sol and (rec.get("solvent_source") == "cxsmiles_agents"):
        sol = rec.get("solvent_smiles")
    if not sol:
        sol = "organic"                          # 【推断】
    cat = catalyst_class(rec.get("catalyst_names"))
    cond = Conditions(solvent=str(sol), temperature=temp, catalyst=cat, reagents=())
    return cond, has_t, temp, cat


def subsets_of(rec, has_t):
    """返回该记录要计入的子集列表。S_ice ⊂ S_temp ⊂ S_all（S_notemp 与 S_temp 互斥）。"""
    if not has_t:
        return ["S_notemp", "S_all"]
    out = ["S_temp", "S_all"]
    if abs(float(rec["temperature_C"])) < 1e-9:
        out.append("S_ice")          # 真实冰浴（0 ℃），单列一组
    return out


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description="ORD 门控误杀率（false negative）测量")
    ap.add_argument("--limit", type=int, default=3000, help="抽多少行（按行均匀抽）")
    ap.add_argument("--seed", type=int, default=20261013, help="reservoir 抽样种子")
    ap.add_argument("--notemp-temp", type=float, default=100.0,
                    help="温度缺失时给 Conditions 的温度（℃）。默认 100 = 引擎默认值；"
                         "★ 这不是记录的真实温度，只作缺省，报告里必须写明")
    ap.add_argument("--configs", type=str, default="A,B,C",
                    help="跑哪些配置，逗号分隔：A/B/C")
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    ap.add_argument("--show-raw", type=int, default=5, help="先打印几条原始记录")
    ap.add_argument("--no-dedup", action="store_true", help="不做 (产物,底物集) 去重")
    args = ap.parse_args()

    cfg_keys = []
    for tok in args.configs.split(","):
        tok = tok.strip()
        if not tok:
            continue
        full = CFG_SHORT.get(tok.upper(), tok if tok in ALL_CONFIGS else None)
        if full is None:
            raise SystemExit(f"--configs 里有无法识别的配置：{tok!r}"
                             f"（可用 A/B/C 或 {list(ALL_CONFIGS)}）")
        if full not in cfg_keys:
            cfg_keys.append(full)

    t_start = time.time()
    print("#" * 100)
    print("# ORD 门控误杀率（false negative）")
    print(f"# limit={args.limit}  seed={args.seed}  配置={cfg_keys}  "
          f"去重={not args.no_dedup}")
    print("#" * 100)
    print()

    recs, id_hash, shard_hint = draw_sample(args.limit, args.seed)
    print_raw(recs, n=args.show_raw)

    # ---- 过滤 ----
    fail = Counter()
    qualified = []
    seen_keys = set()
    t2 = Counter()
    for r in recs:
        st, payload = classify(r, seen_keys, no_dedup=args.no_dedup)
        if st != "ok":
            fail[st] += 1
            continue
        reacs, prod_canon = payload
        t2["lhs_n_ne_2"] += 1 if (r.get("reactants_n") or 0) != 2 else 0
        t2["two_same_smiles"] += 1 if len({mc.canon_plain(x) for x in reacs}) < 2 else 0
        qualified.append((r, reacs, prod_canon))

    print("=" * 100)
    print(f"② 过滤 / 失败分类（抽到 {len(recs)} 行）")
    print("=" * 100)
    for k in FAIL_KEYS:
        print(f"   {k:<30} {fail[k]:>7}  {fail[k]/max(1,len(recs))*100:6.2f}%")
    print(f"   {'入评测集 qualified':<30} {len(qualified):>7}  "
          f"{len(qualified)/max(1,len(recs))*100:6.2f}%")
    print(f"   [附] qualified 中 CXSMILES 左侧片段数 != 2 的：{t2['lhs_n_ne_2']}")
    print(f"   [附] qualified 中两个 REACTANT 是同一分子的：{t2['two_same_smiles']}")
    print()

    if not qualified:
        raise SystemExit("评测集为空，先加大 --limit 再跑。")

    # ---- 引擎 ----
    print("=" * 100)
    print("③ 构造引擎（显式传参，不依赖默认值）")
    print("=" * 100)
    engines = {}
    for k in cfg_keys:
        kw = ALL_CONFIGS[k]
        t0 = time.time()
        eng = SmartReactEngine(verbose=False, **kw)
        engines[k] = eng
        n_extra = len(getattr(eng, "extra_templates", []) or [])
        print(f"   {k:<16} {kw}  自抽模板 {n_extra} 条  "
              f"条件表 {len(getattr(eng, 'cond_table', {}) or {})} 类  "
              f"({time.time()-t0:.1f}s)")
    print()

    # ---- 评测 ----
    stats = {k: {s: Counter() for s in SUBSETS} for k in cfg_keys}
    detail = []
    gate_zero_types = Counter()
    exc_msgs = Counter()
    t0 = time.time()
    n_done = 0
    for idx, (r, reacs, prod_canon) in enumerate(qualified):
        cond, has_t, temp, cat = build_cond(r, args.notemp_temp)
        subs_ = subsets_of(r, has_t)
        comps = [Compound(smiles=s, name=f"ORD_R{i+1}", herb="ORD")
                 for i, s in enumerate(reacs)]
        row = {"rid": str(r["reaction_id"]), "T": (None if not has_t else float(temp)),
               "y": r.get("yield_percent"), "sub": subs_[0], "cat": cat}
        per = {}
        for k in cfg_keys:
            eng = engines[k]
            eng.gate_stats = {}
            n_kept, hit, gz, exc = None, None, None, None
            try:
                prods = eng.step(comps, cond, round_no=1)
                got = {mc.canon_plain(p.smiles) for p in prods} - {None}
                n_kept = len(prods)
                hit = prod_canon in got
                gz = int(eng.stats.get("gated_zero_total", 0))
                for t, c in (eng.stats.get("gated_zero_by_type", {}) or {}).items():
                    gate_zero_types[t] += int(c)
            except Exception as ex:
                exc = f"{type(ex).__name__}: {ex}"[:200]
                exc_msgs[exc] += 1
            per[k] = {"kept": n_kept, "hit": hit, "gz": gz, "exc": exc}
        # ★ 主判零口径：A 有产物 & B 无产物（A/B 模板集相同，只差门控开关）
        a, b = per.get("A_纯模板库"), per.get("B_模板库加门控")
        zero_ab = bool(a and b and a["kept"] and b["kept"] == 0)
        for k in cfg_keys:
            p = per[k]
            for s_ in subs_:
                c = stats[k][s_]
                c["n"] += 1
                if p["exc"] is not None:
                    c["exception"] += 1
                    continue
                c["ok"] += 1
                if p["hit"]:
                    c["hit"] += 1
                if p["kept"] == 0:
                    c["kept0"] += 1
                if p["gz"]:
                    c["gated_any"] += 1
                    if p["kept"] == 0:
                        c["gated_all_counter"] += 1
                if zero_ab and k == "B_模板库加门控":
                    c["gated_all_ab"] += 1
        row.update({f"kept_{k[0]}": per[k]["kept"] for k in cfg_keys})
        row.update({f"hit_{k[0]}": per[k]["hit"] for k in cfg_keys})
        row.update({f"gz_{k[0]}": per[k]["gz"] for k in cfg_keys})
        row["exc"] = {k: per[k]["exc"] for k in cfg_keys if per[k]["exc"]}
        detail.append(row)

        n_done += 1
        if n_done % 200 == 0:
            print(f"   ... 已评测 {n_done}/{len(qualified)}  "
                  f"{time.time()-t0:.0f}s", flush=True)

    print(f"\n   评测完成：{len(qualified)} 条，耗时 {time.time()-t0:.1f}s\n")

    # ---- 汇总打印 ----
    def pct(x, n):
        return f"{(x/n*100):6.2f}%" if n else "   n/a"

    print("=" * 100)
    print("④ 三配置对比（分母 = 各子集评测条数）")
    print("=" * 100)
    for s in SUBSETS:
        n_ref = stats[cfg_keys[0]][s].get("n", 0)
        if not n_ref:
            continue
        print(f"\n  【{s}】n={n_ref}"
              + ("（有温度子集；S_ice 是它的子集）" if s == "S_temp" else "")
              + ("（温度缺失，用缺省温度 "
                 f"{args.notemp_temp:g} ℃ 跑 —【推断】）" if s == "S_notemp" else ""))
        print(f"    {'配置':<16}{'命中':>7}{'命中率':>9}{'判零(AB口径)':>14}"
              f"{'判零(计数器)':>14}{'保留0产物':>10}{'异常':>6}")
        for k in cfg_keys:
            c = stats[k][s]
            nn = c.get("n", 0)
            ab = c.get("gated_all_ab")
            ab_s = (f"{ab:>8}" + pct(ab, nn)) if ab is not None else f"{'—':>8}{'':>6}"
            print(f"    {k:<16}{c.get('hit',0):>7}{pct(c.get('hit',0),nn):>9}"
                  f"{ab_s}"
                  f"{c.get('gated_all_counter',0):>8}{pct(c.get('gated_all_counter',0),nn):>6}"
                  f"{c.get('kept0',0):>10}{c.get('exception',0):>6}")
        if "A_纯模板库" in cfg_keys and "B_模板库加门控" in cfg_keys:
            ha = stats["A_纯模板库"][s].get("hit", 0)
            hb = stats["B_模板库加门控"][s].get("hit", 0)
            print(f"    ★ 误杀率 = (A命中 {ha} - B命中 {hb}) / A命中 {ha} = "
                  f"{(ha-hb)/ha*100:.2f}%" if ha else "    ★ 误杀率：A 命中 0，无法计算")
            if "C_当前默认" in cfg_keys:
                hc = stats["C_当前默认"][s].get("hit", 0)
                print(f"      C 命中 {hc}；C 相对 A {hc-ha:+d} 条，相对 B {hc-hb:+d} 条")

    print()
    print("=" * 100)
    print("⑤ 被门控判零的枚举结果所属反应类型（B/C 两个开了门控的配置累加，跨记录）")
    print("=" * 100)
    if gate_zero_types:
        for t, c in gate_zero_types.most_common(15):
            print(f"   {t:<40} {c}")
    else:
        print("   （无：所选配置里没有任何枚举结果被门控判零）")

    print()
    print("=" * 100)
    print("⑥ step 抛异常分类计数")
    print("=" * 100)
    if exc_msgs:
        for m, c in exc_msgs.most_common(20):
            print(f"   {c:>6}  {m}")
    else:
        print("   （无异常）")

    ex = [d for d in detail
          if d.get("hit_A") and d.get("hit_B") is False]
    print()
    print("=" * 100)
    print(f"⑦ ★ 误杀实例（A 命中 而 B 未命中）共 {len(ex)} 条，列前 10 条")
    print("=" * 100)
    for d in ex[:10]:
        print(f"   {d['rid']}  T={d['T']}  y={d['y']}  keptB={d['kept_B']}  "
              f"gzB={d['gz_B']}  子集={d['sub']}")
    if not ex:
        print("   （无）")

    # ---- A/B 命中集是不是【逐条完全相同】（比"命中率相同"强，排除对消） ----
    ab_check = {}
    if "A_纯模板库" in cfg_keys and "B_模板库加门控" in cfg_keys:
        ha_set = {d["rid"] for d in detail if d.get("hit_A")}
        hb_set = {d["rid"] for d in detail if d.get("hit_B")}
        ab_check = {"hit_set_identical_AB": ha_set == hb_set,
                    "n_A_only": len(ha_set - hb_set), "n_B_only": len(hb_set - ha_set),
                    "n_AB_common": len(ha_set & hb_set)}
        print()
        print("=" * 100)
        print("⑧ A/B 命中集逐条比对（B 的输出必然是 A 的子集：同模板、门控只会删结果）")
        print("=" * 100)
        print(f"   命中集完全相同: {ab_check['hit_set_identical_AB']}   "
              f"仅 A 命中: {ab_check['n_A_only']}   仅 B 命中: {ab_check['n_B_only']}   "
              f"共有: {ab_check['n_AB_common']}")

    # ---- JSON ----
    out = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "script": "tools/ord_gate_falsenegative.py",
            "data_source": str(SHARDS / "shard_*.parquet"),
            "n_shards": SHARD_TOTAL,
            "rows_total": ROWS_TOTAL,
            "sampling": (f"duckdb read_parquet(glob) USING SAMPLE {args.limit} ROWS "
                         f"(reservoir, {args.seed}) —— 按【行】在 178 个分片上均匀抽，"
                         f"非按片抽；id_hash = sorted(reaction_id) 的 sha1"),
            "seed": args.seed,
            "limit_rows_drawn": args.limit,
            "notemp_default_C": args.notemp_temp,
            "dedup": not args.no_dedup,
            "configs": {k: ALL_CONFIGS[k] for k in cfg_keys},
            "subset_defs": {
                "S_temp": "temperature_C 非空（28.46% 可得率）",
                "S_notemp": "temperature_C 缺失 -> Conditions.temperature="
                            f"{args.notemp_temp:g}（缺省值，不是记录的真实温度）",
                "S_ice": "temperature_C == 0 ℃（上游核实为真实冰浴），S_temp 的子集",
                "S_all": "S_temp + S_notemp",
            },
            "hit_def": "记录产物 canon_plain 出现在 step() 返回产物 SMILES 集合里",
            "hit_rate_denominator": "该子集的评测记录数 n（含 step 抛异常的那几条；异常数单列）",
            "gate_zero_def": {
                "gated_all_ab": "★主口径：A 有产物 而 B 无产物（A/B 模板集相同，仅门控开关不同）",
                "gated_all_counter": "eng.stats['gated_zero_total']>0 且该次 step 返回 0 个产物",
                "gated_any": "eng.stats['gated_zero_total']>0",
            },
            "limitations": [
                "只取 role=REACTANT 恰好 2 个的记录 -> 排除了把碱/硼酸也标成 REACTANT 的反应",
                "ORD 该数据集没有 REAGENT 角色（可得率 0%）-> reagents 全为空 -> 必需试剂门控"
                "走「没写试剂不检查」分支，本次测不到该门控的误杀",
                "catalyst 字段被 cond_activation() 忽略（grep 0 命中）-> 催化剂归类不影响指标",
                "溶剂在 cond_activation() 里只能降权到 0.6 -> 不影响命中/判零",
                f"温度缺失（占 qualified 的多数）时缺省温度 {args.notemp_temp:g} ℃ 是【推断】选择，"
                "它本身会影响判零（敏感性见报告）",
            ],
        },
        "sample": {
            "n_rows_drawn": len(recs),
            "id_hash_sha1": id_hash,
            "shard_coverage": shard_hint,
        },
        "classification": {
            "n_drawn": len(recs),
            **{k: fail[k] for k in FAIL_KEYS},
            "qualified": len(qualified),
            "aux_lhs_n_ne_2_in_qualified": t2["lhs_n_ne_2"],
            "aux_two_same_smiles_in_qualified": t2["two_same_smiles"],
        },
        "per_config": {
            k: {s: {kk: vv for kk, vv in stats[k][s].items()} for s in SUBSETS
                if stats[k][s].get("n")} for k in cfg_keys
        },
        "falsenegative": {},
        "ab_hitset_check": ab_check,
        "gate_zero_by_type": dict(gate_zero_types.most_common(50)),
        "step_exceptions": dict(exc_msgs),
        "records": detail,
    }
    fn = out["falsenegative"]
    for s in SUBSETS:
        rec = {}
        for k in cfg_keys:
            c = stats[k][s]
            n = c.get("n", 0)
            rec[k] = {"n": n, "hit": c.get("hit", 0),
                      "hit_rate": round(c.get("hit", 0) / n, 6) if n else None,
                      "gated_all_ab": c.get("gated_all_ab", 0),
                      "gated_all_counter": c.get("gated_all_counter", 0),
                      "kept0": c.get("kept0", 0),
                      "exception": c.get("exception", 0)}
        if "A_纯模板库" in cfg_keys and "B_模板库加门控" in cfg_keys:
            ha = stats["A_纯模板库"][s].get("hit", 0)
            hb = stats["B_模板库加门控"][s].get("hit", 0)
            rec["gated_all_AB"] = stats["B_模板库加门控"][s].get("gated_all_ab", 0)
            rec["falseneg_rate_AB"] = (round((ha - hb) / ha, 6) if ha else None)
            rec["falseneg_n_AB"] = ha - hb
            if "C_当前默认" in cfg_keys:
                hc = stats["C_当前默认"][s].get("hit", 0)
                rec["C_vs_A_n"] = hc - ha
                rec["C_vs_B_n"] = hc - hb
        fn[s] = rec
    fn["examples_A_hit_B_miss"] = [
        {"rid": d["rid"], "T": d["T"], "yield_percent": d["y"], "subset": d["sub"],
         "kept_A": d.get("kept_A"), "kept_B": d.get("kept_B"), "gz_B": d.get("gz_B")}
        for d in ex[:50]]

    outp = Path(args.out)
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {outp}  ({outp.stat().st_size/1024:.0f} KB)  总耗时 "
          f"{time.time()-t_start:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
