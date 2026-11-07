# -*- coding: utf-8 -*-
r"""第十三轮：从 ORD 抽【反例候选】—— 严格正则 + 原始证据，宁少勿滥。

背景（探针 1/2 实测，已写进报告）：
  - ORD protobuf 里**没有**任何"没反应/失败"专用字段（DESCRIPTOR 逐字段看过）。
  - conversion 字段在这份数据里**从没被填过**（0/100,000）-> 用不了。
  - yield==0 命中 61/100,000，但**全是假反例**：details=CALCULATEDPERCENTYIELD（计算收率 0），
    真实 PERCENTYIELD 是 27.5% / 25.0%。-> 必须按 details 区分。
  - 自由文本（notes.procedure_details）里**确实有真反例**，但极稀：
    "No reaction occurred so the reaction…" / "no conversion to the desired product" /
    "did not react with N-methylpyr…"。
    宽松词（trace / decompos / not observed / unsuccessful）几乎全是噪声 -> 本脚本剔除。

口径（写死，避免重测）：
  采样范围：全量 1,771,032 条（流式读，不 fetchall）
  正例 vs 反例：ORD 记录默认是"做过的反应"= 正例候选；
                只有 notes 命中【严格否定短语】的记录才进反例候选。
  抽取字段：reaction_id / CXSMILES / 命中短语 / notes 上下文 / 条件（温度、溶剂）/ 收率测量
  每条记录去重（同一 reaction_id 只留一条）。

用法: python extract_negative_examples.py [N]      # N 默认全量
输出: reports/negative_examples.jsonl + reports/negative_examples_summary.json
"""
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
OUT_JSONL = STAGE / "reports" / "negative_examples.jsonl"
OUT_Y0 = STAGE / "reports" / "negative_yield_zero.jsonl"
OUT_Y0V2 = STAGE / "reports" / "negative_yield_zero_v2.jsonl"
OUT_SUM = STAGE / "reports" / "negative_examples_summary.json"

# 严格短语：每条都要求"否定 + 反应/转化/产物"同现，避免 trace/decompos 这类噪声
PATTERNS = [
    ("no_reaction", re.compile(r"no reaction (?:occurred|was observed|took place|was seen)", re.I)),
    ("no_conversion", re.compile(r"no (?:appreciable |detectable )?conversion", re.I)),
    ("did_not_react", re.compile(r"did(?: not|n't) react", re.I)),
    ("failed_to_react_or_give", re.compile(
        r"failed to (?:react|give|generate|produce|yield|form)", re.I)),
    ("no_product_formed", re.compile(
        r"no (?:desired )?product (?:was )?(?:formed|observed|detected|isolated)", re.I)),
    ("sm_recovered", re.compile(
        r"(?:starting material|sm) (?:was )?(?:recovered|unchanged|remained unreacted)", re.I)),
    ("reaction_did_not_proceed", re.compile(
        r"reaction did not (?:proceed|occur|take place|go)", re.I)),
    ("unreacted_remaining", re.compile(r"(?:remained|was|were) unreacted", re.I)),
    ("not_consumed", re.compile(r"not consumed", re.I)),
]

CHUNK = 5000


def notes_text(rxn):
    n = rxn.notes
    if not n or not n.ListFields():
        return ""
    return " ".join(v for f in n.DESCRIPTOR.fields
                    if isinstance(v := getattr(n, f.name), str) and v)


def cxsmiles(rxn):
    return next((i.value for i in rxn.identifiers
                 if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES
                 and i.value), None)


def _enum_name(msg, field_name):
    """把枚举字段的数值转成名字（units=1 这种要写成 CELSIUS 才有意义）。"""
    try:
        fd = msg.DESCRIPTOR.fields_by_name.get(field_name)
        if fd is not None and fd.enum_type is not None:
            return fd.enum_type.values_by_number[getattr(msg, field_name)].name
    except Exception:
        pass
    return None


def temp_C(rxn):
    try:
        t = rxn.conditions.temperature
        if not t.ListFields():
            return None
        for key in ("setpoint", "value"):
            if t.HasField(key):
                sub = getattr(t, key)
                v = getattr(sub, "value", sub)
                units = None
                if hasattr(sub, "units"):
                    units = _enum_name(sub, "units") or getattr(sub, "units", None)
                return {"value": v, "units": units}
    except Exception:
        return None
    return None


def solvents(rxn):
    out = []
    try:
        for s in rxn.conditions.solvents:
            nm = s.name or (s.compound.identifiers[0].value if s.compound.identifiers else "")
            if nm:
                out.append(str(nm))
    except Exception:
        pass
    return out


def yields(rxn):
    out = []
    for oc in rxn.outcomes:
        for prod in oc.products:
            for m in prod.measurements:
                if m.type != reaction_pb2.ProductMeasurement.YIELD:
                    continue
                for key in ("percentage", "float_value"):
                    if m.HasField(key):
                        out.append({"kind": key, "value": getattr(m, key).value,
                                    "details": m.details[:40] if m.details else ""})
    return out


# 结构标识符类型（有 = 这个"产物"是真分子；没有 = 多半是洗脱剂/溶剂名）
_STRUCT_ID_TYPES = tuple(
    t for t in (getattr(reaction_pb2.CompoundIdentifier, n, None)
                for n in ("SMILES", "CXSMILES", "INCHI", "INCHI_KEY"))
    if t is not None)


def yields_by_product(rxn):
    """[(产物是否有结构标识符, [该产物的收率测量...])]

    ★ 为什么需要（子代理实测发现）★
    B 路"真实 PERCENTYIELD==0"里绝大多数是**解析伪影**：
    那条 0% 挂在 identifier 只有名字、且名字是层析洗脱剂的 product 实体上
    （"EtOAc—hexanes" / "ethyl acetate petrol" / "MeOH NH3"），
    真正的 title compound 那条 product 的 measurements 是空的；
    0% 的文本来源是梯度写法 "(0% to 60% EtOAc-hexanes)"。
    所以 v2 口径：**0% 必须挂在有结构标识符的产物上**才算候选。
    """
    out = []
    for oc in rxn.outcomes:
        for prod in oc.products:
            has_struct = any(i.type in _STRUCT_ID_TYPES and i.value
                             for i in prod.identifiers)
            ms = []
            for m in prod.measurements:
                if m.type != reaction_pb2.ProductMeasurement.YIELD:
                    continue
                for key in ("percentage", "float_value"):
                    if m.HasField(key):
                        ms.append({"kind": key, "value": getattr(m, key).value,
                                   "details": m.details[:40] if m.details else ""})
            if ms:
                names = [i.value[:40] for i in prod.identifiers
                         if i.type == reaction_pb2.CompoundIdentifier.NAME and i.value]
                out.append({"has_struct_id": has_struct, "names": names, "yields": ms})
    return out


def main():
    n_cap = int(sys.argv[1]) if len(sys.argv) > 1 else None
    t0 = time.time()
    con = duckdb.connect()
    con.execute("SET memory_limit='1200MB'")
    con.execute("SET threads=2")
    sql = f"SELECT reaction FROM read_parquet('{BIG.as_posix()}')"
    if n_cap:
        sql += f" LIMIT {n_cap}"
    cur = con.execute(sql)

    stat = Counter()
    pat_hits = Counter()
    seen_ids = set()
    y0_ids = set()
    real_percent_zero = 0
    calc_percent_zero = 0
    n_written = 0
    n_y0 = 0
    n_y0_v2 = 0
    f = open(OUT_JSONL, "w", encoding="utf-8")
    f0 = open(OUT_Y0, "w", encoding="utf-8")
    f0v2 = open(OUT_Y0V2, "w", encoding="utf-8")
    while True:
        rows = cur.fetchmany(CHUNK)
        if not rows:
            break
        for (blob,) in rows:
            stat["扫描条数"] += 1
            rxn = reaction_pb2.Reaction()
            try:
                rxn.ParseFromString(blob)
            except Exception:
                stat["protobuf失败"] += 1
                continue
            rid = rxn.reaction_id or f"<无id:{stat['扫描条数']}>"
            # ---- 路线 B：真实 PERCENTYIELD == 0（必须排除 CALCULATEDPERCENTYIELD）----
            ys = yields(rxn)
            real_zero = [y for y in ys if y["kind"] == "percentage" and y["value"] == 0
                         and "CALCULATED" not in y["details"].upper()]
            for y in ys:
                if y["kind"] == "percentage" and y["value"] == 0:
                    if "CALCULATED" in y["details"].upper():
                        calc_percent_zero += 1
                    else:
                        real_percent_zero += 1
            # v2 口径：0% 必须挂在【有结构标识符】的产物上（否则是洗脱剂伪影）
            v2_zero = []
            for p in yields_by_product(rxn):
                if not p["has_struct_id"]:
                    if any(y["kind"] == "percentage" and y["value"] == 0
                           and "CALCULATED" not in y["details"].upper()
                           for y in p["yields"]):
                        stat["B_伪影(0%挂在无结构产物上)"] += 1
                    continue
                bad = [y for y in p["yields"]
                       if y["kind"] == "percentage" and y["value"] == 0
                       and "CALCULATED" not in y["details"].upper()]
                if bad:
                    v2_zero.append({"has_struct_id": True, "names": p["names"],
                                    "yields": p["yields"]})
            if real_zero:
                y0_ids.add(rid)
                f0.write(json.dumps({
                    "reaction_id": rid,
                    "cxsmiles": cxsmiles(rxn),
                    "real_percent_yield_zero": real_zero,
                    "all_yields": ys,
                    "temperature": temp_C(rxn),
                    "notes_head": notes_text(rxn)[:400],
                    "v2_valid": bool(v2_zero),
                }, ensure_ascii=False) + "\n")
                n_y0 += 1
            if v2_zero:
                n_y0_v2 += 1
                f0v2.write(json.dumps({
                    "reaction_id": rid,
                    "cxsmiles": cxsmiles(rxn),
                    "zero_on_structured_product": v2_zero,
                    "all_yields": ys,
                    "temperature": temp_C(rxn),
                    "notes_head": notes_text(rxn)[:400],
                }, ensure_ascii=False) + "\n")
            # ---- 路线 A：notes 命中严格否定短语 ----
            txt = notes_text(rxn)
            if not txt:
                stat["notes为空"] += 1
                continue
            matched = []
            for tag, pat in PATTERNS:
                if pat.search(txt):
                    matched.append(tag)
                    pat_hits[tag] += 1
            if not matched:
                continue
            stat["命中严格短语的记录"] += 1
            if rid in seen_ids:
                stat["重复id跳过"] += 1
                continue
            seen_ids.add(rid)
            ctxs = []
            for tag in matched:
                pat = dict(PATTERNS)[tag]
                m = pat.search(txt)
                ctxs.append({"pattern": tag,
                             "context": txt[max(0, m.start() - 150):m.end() + 150]})
            rec = {
                "reaction_id": rid,
                "cxsmiles": cxsmiles(rxn),
                "matched": matched,
                "contexts": ctxs,
                "temperature": temp_C(rxn),
                "solvents": solvents(rxn),
                "yields": ys,
                "notes_head": txt[:400],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_written += 1
        if stat["扫描条数"] % 200000 < CHUNK:
            print(f"  {stat['扫描条数']:,} 条  文本候选 {n_written}  "
                  f"0%收率候选 {n_y0}  {time.time()-t0:.0f}s", flush=True)
    f.close()
    f0.close()
    f0v2.close()

    summary = {
        "scratch": "反例候选抽取（路线 A：notes 严格短语；路线 B：真实 PERCENTYIELD==0；B-v2：0% 必须挂在有结构标识符的产物上）",
        "n_scanned": stat["扫描条数"],
        "n_notes_empty": stat["notes为空"],
        "A_text_candidates": n_written,
        "B_yield_zero_candidates": n_y0,
        "B_v2_zero_on_structured_product": n_y0_v2,
        "B_artifact_zero_on_unstructured_product": stat["B_伪影(0%挂在无结构产物上)"],
        "A_and_B_overlap": len(seen_ids & y0_ids),
        "n_dup_id_skipped": stat["重复id跳过"],
        "pattern_hits": dict(pat_hits),
        "yield_percentage_zero_real": real_percent_zero,
        "yield_percentage_zero_calculated": calc_percent_zero,
        "seconds": round(time.time() - t0, 1),
        "outputs": [OUT_JSONL.name, OUT_Y0.name, OUT_Y0V2.name],
    }
    OUT_SUM.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=" * 96)
    print(f"扫描 {stat['扫描条数']:,} 条，用时 {time.time()-t0:.0f}s")
    print("=" * 96)
    print(f"  notes 为空的记录        {stat['notes为空']:,}")
    print(f"  A 文本候选（严格短语）   {n_written:,}  -> {OUT_JSONL.name}")
    print(f"  B 0% 收率候选（真收率）  {n_y0:,}  -> {OUT_Y0.name}")
    print(f"  B-v2 0% 挂在有结构产物上 {n_y0_v2:,}  -> {OUT_Y0V2.name}"
          f"   （伪影 = 0% 挂在无结构标识符的\"产物\"上："
          f"{stat['B_伪影(0%挂在无结构产物上)']:,} 条）")
    print(f"  A ∩ B（两边都命中）      {len(seen_ids & y0_ids):,}")
    print()
    print("  按短语拆开（一条记录可命中多条）：")
    for tag, n in pat_hits.most_common():
        print(f"    {tag:<26} {n:,}")
    print()
    print("  收率口径核实（percentage == 0）：")
    print(f"    真实 PERCENTYIELD == 0     {real_percent_zero:,}")
    print(f"    CALCULATEDPERCENTYIELD == 0 {calc_percent_zero:,}  <- 探针 2 证明这类是假反例")
    return 0


if __name__ == "__main__":
    sys.exit(main())
