# -*- coding: utf-8 -*-
r"""第十七轮：把本地 ORD 全量抽成一张【条件 + 数值收率】训练表。

目标：为「条件感知判据」提供比 HTE（27,497 行）大两个数量级的数据。
数据：chemreact-staging/ord-data/data/11/ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet
      （uspto-grants，1,771,032 条 ORD 记录，**只读，不修改 ord-data 目录**）

================================ 口径（写死，不许事后改）================================
一条 ORD 记录被写进本表，当且仅当同时满足：
  R1. 记录里有 REACTION_CXSMILES 标识，且能按 底物>试剂>产物 拆段（底物侧与产物侧都非空）；
  R2. 产物侧 SMILES 能被 RDKit 解析（mapped_chem.parse_plain 不为 None）；
  R3. 存在 outcomes[*].products[*].measurements[*] 满足：
        type == ProductMeasurementType.YIELD
        且 HasField('percentage') 为真（即给的是**百分比**，不是摩尔/质量）
        且 0 < percentage.value <= 100。
数值收率 yield_percent 的取值优先级（**小样本实测后定死**，见报告「口径修正」）：
  ① details == 'PERCENTYIELD'（论文原文给出的收率）优先；
  ② 没有 ① 时用 details == 'CALCULATEDPERCENTYIELD'；
  ③ 都没有时用其它 details 里数值最大的那一类。
  同一 details 有多个值（多产物）时取【最大值】，视为主产物收率。
  实测依据：1059 对 PERCENTYIELD/CALCULATEDPERCENTYIELD 中 191 对完全相等、
  465 对差 <0.5（四舍五入），但有 171 对差 >=5、最大差 98195
  （CALCULATEDPERCENTYIELD 里有 73011% / 98293% 这类明显由单位/解析 bug 产生的垃圾值）。
  因此「优先原文值」比「取最大」稳。其它细节值记在 yield_alt_percent，供下游按
  |yield_percent - yield_alt_percent| > 0.5 过滤（flag yield_inconsistent）。

不计入本表的（**分开计数、不静默丢弃**，见计数器 fail_*）：
  - 收率只给 amount（摩尔/质量）而没给 percentage        -> fail_yield_non_percentage_only
  - percentage 值不在 (0,100]                           -> fail_yield_out_of_range
    （另分 mild 100<v<=130 与 extreme v>130 两个计数器，量化数据脏的程度）
  - 产物侧压根没有 type==YIELD 的测量                     -> fail_no_yield_measurement
  - 收率只写在 notes.procedure_details 文本里             -> 同 fail_no_yield_measurement
    （本表只取结构化字段，不做文本正则抽收率；这样口径可复现、不含主观判断）

条件字段的口径：
  - temperature_C：优先 conditions.temperature.setpoint（KELVIN/FAHRENHEIT 换算成摄氏），
                   没有 setpoint 时取 conditions.temperature.measurements 的第一个；
                   单位无法识别 -> 记 flag temp_unit_unknown，该行温度为 null。
  - solvent/catalyst/reagent：来自 inputs[*].components[*] 的 reaction_role
                   （SOLVENT / CATALYST / REAGENT）；名字取 identifiers 里第一个 NAME，
                   SMILES 取第一个 SMILES/CXSMILES。
                   若没有任何 SOLVENT 组分，但 CXSMILES 中间段非空 -> 用中间段当溶剂
                   （solvent_source='cxsmiles_agents'，单独计数）。
  - reactants：CXSMILES 底物侧**原样保留**（含原子映射号）；
  - product：CXSMILES 产物侧原样保留（含映射号）；另给 product_smiles（去映射规范化）。
  - reaction_class：本数据集（uspto-grants）的标识里**只有 REACTION_CXSMILES**，
                   没有 REACTION_TYPE，故 reaction_class 基本为空；
                   脚本仍按口径读 REACTION_TYPE 标识与 provenance.reaction_metadata，
                   并单独统计「有 reaction_class 的条数」。
  - source/doi：provenance.doi 与 provenance.patent。

================================== 分片与续跑 ==================================
全量按 parquet 的 row group 切分片（默认 --shard-rows 10000 = 10 个 row group/片，
共 178 片）。每片写一个 <out>/shard_XXXX.parquet（先写 .tmp 再 os.replace，原子落地）
+ 一个 <out>/shard_XXXX.stats.json（计数器随片落地，便于离线合并）。
**续跑判定**：.parquet 与 .stats.json 同时存在 = 该片已完成，跳过。
不传 --resume 时若输出目录已有分片 -> 直接报错退出，避免把两次运行的数据混在一起。
--max-shards K 限制单次运行处理的分片数（用于小步验证 + 验证续跑）。

--limit N 时走**可复现抽样**（复用 tools/forward_template_mining.py 的
  `USING SAMPLE N ROWS (reservoir, seed)` 模式），单文件输出、不切片；
  并在解析前先打印 --show-raw（默认 3）条**完整原始记录**（protobuf TextFormat 原文）。

用法：
  python tools/ord_condition_dataset.py --limit 5000                  # 小样本验证（先打印原始记录）
  python tools/ord_condition_dataset.py --max-shards 2               # 小步跑分片 + 验证续跑
  python tools/ord_condition_dataset.py --resume --workers 6         # 全量（可反复重跑续跑）
  python tools/ord_condition_dataset.py --summary-only               # 只合并分片统计写 summary.json
输出：reports/ord_condition_dataset/  (分片)  +  reports/ord_condition_dataset_summary.json
"""
import argparse
import json
import math
import os
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    sys.path.insert(0, str(_p))

import pyarrow as pa                       # noqa: E402
import pyarrow.parquet as pq               # noqa: E402
from google.protobuf import text_format    # noqa: E402
from ord_schema.proto import reaction_pb2 as R  # noqa: E402
from rdkit import RDLogger                 # noqa: E402

import mapped_chem as mc                   # noqa: E402  （复用 CXSMILES 拆段，不重写）

# RDKit 在解析非法价态时会往 stderr 刷 "Explicit valence ..." 噪音（这些记录已被
# fail_product_unparsable 正常计数），关掉日志以免淹没失败统计。
RDLogger.DisableLog("rdApp.*")

DEFAULT_PARQUET = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
DEFAULT_OUT = STAGE / "reports" / "ord_condition_dataset"
SUMMARY_JSON = STAGE / "reports" / "ord_condition_dataset_summary.json"
PROGRESS_JSON_NAME = "_progress.json"

# ★ 本环境 ord_schema 的枚举不能直接用 EnumTypeWrapper.Name()（ReactionRole 是
#   message 而不是枚举包装器），一律从 field descriptor 的 enum_type 反查名字。
def _enum_num_to_name(msg_descriptor, field_name):
    et = msg_descriptor.fields_by_name[field_name].enum_type
    return {v.number: k for k, v in et.values_by_name.items()}


ROLE_NAME = _enum_num_to_name(R.Compound.DESCRIPTOR, "reaction_role")
TEMP_UNIT_NAME = _enum_num_to_name(R.Temperature.DESCRIPTOR, "units")
TIME_UNIT_NAME = _enum_num_to_name(R.Time.DESCRIPTOR, "units")
IDENT_TYPE_NAME = _enum_num_to_name(R.CompoundIdentifier.DESCRIPTOR, "type")
RXN_IDENT_TYPE_NAME = _enum_num_to_name(R.ReactionIdentifier.DESCRIPTOR, "type")
MEAS_TYPE_NAME = _enum_num_to_name(R.ProductMeasurement.DESCRIPTOR, "type")

TEMPERATURE_BINS = [(-1e9, 0), (0, 25), (25, 50), (50, 80), (80, 120),
                    (120, 200), (200, 1e9)]
TEMPERATURE_BIN_LABELS = ["<=0C", "0-25C", "25-50C", "50-80C", "80-120C",
                          "120-200C", ">200C"]
YIELD_BINS = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50), (50, 60),
              (60, 70), (70, 80), (80, 90), (90, 100)]
YIELD_BIN_LABELS = ["0-10", "10-20", "20-30", "30-40", "40-50", "50-60",
                    "60-70", "70-80", "80-90", "90-100"]

FAIL_KEYS = ["fail_protobuf", "fail_no_cxsmiles", "fail_cxsmiles_split",
             "fail_product_unparsable", "fail_no_outcomes",
             "fail_no_products", "fail_no_yield_measurement",
             "fail_yield_non_percentage_only", "fail_yield_out_of_range"]
FLAG_KEYS = ["no_temperature", "no_solvent", "no_catalyst", "no_reagent",
             "no_doi", "no_patent", "no_reaction_class", "no_reaction_time",
             "no_reactant_names", "temp_unit_unknown", "temperature_zero",
             "product_compound_without_smiles_id", "multi_product",
             "yield_multiple_measurements", "yield_inconsistent"]
AVAIL_KEYS = ["has_temperature", "has_solvent", "has_catalyst", "has_reagent",
              "has_doi", "has_patent", "has_reaction_class", "has_reaction_time",
              "has_reactant_names", "has_product_smiles"]

ROW_SCHEMA = pa.schema([
    ("reaction_id", pa.string()),
    ("reaction_class", pa.string()),
    ("reactants", pa.string()),
    ("reactants_n", pa.int32()),
    ("reactant_names", pa.string()),
    ("reactant_smiles_components", pa.string()),
    ("product", pa.string()),
    ("product_smiles", pa.string()),
    ("yield_percent", pa.float64()),
    ("yield_source_details", pa.string()),
    ("yield_n_measurements", pa.int32()),
    ("yield_alt_percent", pa.float64()),
    ("temperature_C", pa.float64()),
    ("temperature_source", pa.string()),
    ("solvent_names", pa.string()),
    ("solvent_smiles", pa.string()),
    ("solvent_source", pa.string()),
    ("catalyst_names", pa.string()),
    ("catalyst_smiles", pa.string()),
    ("reagent_names", pa.string()),
    ("reagent_smiles", pa.string()),
    ("agents_mapped", pa.string()),
    ("reaction_time_min", pa.float64()),
    ("doi", pa.string()),
    ("patent", pa.string()),
    ("n_outcomes", pa.int32()),
    ("n_products", pa.int32()),
    ("row_group", pa.int32()),
])


# --------------------------------------------------------------------------- #
# 计数器
# --------------------------------------------------------------------------- #
def new_stats():
    return {
        "n_records": 0,
        "rows": 0,
        "fail": {k: 0 for k in FAIL_KEYS},
        "flag": {k: 0 for k in FLAG_KEYS},
        "avail": {k: 0 for k in AVAIL_KEYS},
        "temp_bins": {k: 0 for k in TEMPERATURE_BIN_LABELS},
        "yield_bins": {k: 0 for k in YIELD_BIN_LABELS},
        "temp_units": {},
        "ident_types": {},
        "yield_details": {},
        "yield_chosen_details": {},
        "yield_oor_mild": {},
        "reaction_class": {},
        "reaction_metadata_keys": {},
        "role_counts": {},
        "row_groups": [],
        "elapsed_s": 0.0,
    }


def merge_stats(dst, src):
    dst["n_records"] += src.get("n_records", 0)
    dst["rows"] += src.get("rows", 0)
    for grp in ("fail", "flag", "avail", "temp_bins", "yield_bins"):
        for k, v in src.get(grp, {}).items():
            dst[grp][k] = dst[grp].get(k, 0) + v
    for grp in ("temp_units", "ident_types", "yield_details", "yield_chosen_details",
                "yield_oor_mild", "reaction_class",
                "reaction_metadata_keys", "role_counts"):
        for k, v in src.get(grp, {}).items():
            dst[grp][k] = dst[grp].get(k, 0) + v
    dst["row_groups"] = sorted(set(dst["row_groups"]) | set(src.get("row_groups", [])))
    dst["elapsed_s"] += src.get("elapsed_s", 0.0)
    return dst


def _bin_label(value, bins, labels):
    for (lo, hi), lab in zip(bins, labels):
        if lo < value <= hi:
            return lab
    return labels[0] if value <= bins[0][1] else labels[-1]


# --------------------------------------------------------------------------- #
# 单条记录解析
# --------------------------------------------------------------------------- #
def _ident_idtype_name(i):
    return IDENT_TYPE_NAME.get(i.type, "?")


def _compound_smiles_name(comp):
    smi = name = None
    for i in comp.identifiers:
        if not i.value:
            continue
        tn = _ident_idtype_name(i)
        if smi is None and tn in ("SMILES", "CXSMILES"):
            smi = i.value
        elif name is None and tn == "NAME":
            name = i.value
    return smi, name


def _temp_to_celsius(t, unit_counter):
    uname = TEMP_UNIT_NAME.get(t.units, "?")
    unit_counter[uname] = unit_counter.get(uname, 0) + 1
    v = t.value
    if uname == "CELSIUS":
        return v
    if uname == "KELVIN":
        return v - 273.15
    if uname == "FAHRENHEIT":
        return (v - 32.0) * 5.0 / 9.0
    return None


def _time_to_minutes(t):
    uname = TIME_UNIT_NAME.get(t.units, "?")
    if uname == "MINUTE":
        return t.value
    if uname == "HOUR":
        return t.value * 60.0
    if uname == "SECOND":
        return t.value / 60.0
    if uname == "DAY":
        return t.value * 1440.0
    return None


def extract_record(rid, blob, rg_index, stats):
    """解析一条 ORD 记录。返回 row dict 或 None（None 时已在 stats 里分类计数）。"""
    stats["n_records"] += 1
    rxn = R.Reaction()
    try:
        rxn.ParseFromString(blob)
    except Exception:
        stats["fail"]["fail_protobuf"] += 1
        return None

    for i in rxn.identifiers:
        tn = RXN_IDENT_TYPE_NAME.get(i.type, "?")
        stats["ident_types"][tn] = stats["ident_types"].get(tn, 0) + 1

    # ---- R1: CXSMILES 拆段 ----
    cx = None
    for i in rxn.identifiers:
        if RXN_IDENT_TYPE_NAME.get(i.type) == "REACTION_CXSMILES" and i.value:
            cx = i.value
            break
    if not cx:
        stats["fail"]["fail_no_cxsmiles"] += 1
        return None
    lhs, agents, rhs = mc.split_rxn(cx)
    if not lhs or not rhs:
        stats["fail"]["fail_cxsmiles_split"] += 1
        return None

    # ---- R2: 产物 SMILES 可解析 ----
    if mc.parse_plain(rhs) is None:
        stats["fail"]["fail_product_unparsable"] += 1
        return None

    # ---- 产物/收率 ----
    if not rxn.outcomes:
        stats["fail"]["fail_no_outcomes"] += 1
        return None
    n_products = sum(len(oc.products) for oc in rxn.outcomes)
    if n_products == 0:
        stats["fail"]["fail_no_products"] += 1
        return None
    if n_products > 1:
        stats["flag"]["multi_product"] += 1

    valid = {}          # details -> [合格 percentage 值]
    n_yield_meas = 0
    n_yield_nonpct = 0
    n_yield_oor = 0
    for oc in rxn.outcomes:
        for p in oc.products:
            for m in p.measurements:
                if MEAS_TYPE_NAME.get(m.type) != "YIELD":
                    continue
                n_yield_meas += 1
                if m.HasField("percentage"):
                    v = float(m.percentage.value)
                    if 0.0 < v <= 100.0:
                        key = m.details or ""
                        valid.setdefault(key, []).append(v)
                        stats["yield_details"][key] = stats["yield_details"].get(key, 0) + 1
                    else:
                        n_yield_oor += 1
                        band = "mild_100_130" if 100.0 < v <= 130.0 else \
                               ("extreme_gt130" if v > 130.0 else "le_zero")
                        stats["yield_oor_mild"][band] = \
                            stats["yield_oor_mild"].get(band, 0) + 1
                else:
                    n_yield_nonpct += 1
    if not valid:
        # 归因优先级：完全没 YIELD 测量 > 有 YIELD 但数值越界 > 只有非百分比
        if n_yield_meas == 0:
            stats["fail"]["fail_no_yield_measurement"] += 1
        elif n_yield_oor > 0:
            stats["fail"]["fail_yield_out_of_range"] += 1
        else:
            stats["fail"]["fail_yield_non_percentage_only"] += 1
        return None

    # ★ 口径：PERCENTYIELD（论文原文）> CALCULATEDPERCENTYIELD > 其它（取最大类）
    chosen = None
    for pref in ("PERCENTYIELD", "CALCULATEDPERCENTYIELD"):
        if pref in valid:
            chosen = pref
            break
    if chosen is None:
        chosen = max(valid, key=lambda k: max(valid[k]))
    ymax = max(valid[chosen])
    others = [v for k, lst in valid.items() if k != chosen for v in lst]
    yalt = max(others) if others else None
    stats["yield_chosen_details"][chosen] = \
        stats["yield_chosen_details"].get(chosen, 0) + 1

    # ---- 条件：inputs 组分角色 ----
    role_counts = stats["role_counts"]
    names = {"REACTANT": [], "SOLVENT": [], "CATALYST": [], "REAGENT": []}
    smiles = {"REACTANT": [], "SOLVENT": [], "CATALYST": [], "REAGENT": []}
    for _, inp in rxn.inputs.items():
        for comp in inp.components:
            rname = ROLE_NAME.get(comp.reaction_role, "?")
            role_counts[rname] = role_counts.get(rname, 0) + 1
            if rname in names:
                smi, nm = _compound_smiles_name(comp)
                if nm:
                    names[rname].append(nm)
                if smi:
                    smiles[rname].append(smi)

    solvent_source = ""
    if smiles["SOLVENT"] or names["SOLVENT"]:
        solvent_source = "components"
    elif agents:
        solvent_source = "cxsmiles_agents"
        smiles["SOLVENT"] = [agents]

    # ---- 条件：温度 ----
    temperature_C = None
    temperature_source = None
    tc = rxn.conditions.temperature
    if tc.HasField("setpoint"):
        temperature_C = _temp_to_celsius(tc.setpoint, stats["temp_units"])
        if temperature_C is not None:
            temperature_source = "setpoint"
    if temperature_C is None and tc.measurements:
        for t in tc.measurements:
            temperature_C = _temp_to_celsius(t, stats["temp_units"])
            if temperature_C is not None:
                temperature_source = "measurement"
                break
    if temperature_C is None:
        if tc.HasField("setpoint") or tc.measurements:
            stats["flag"]["temp_unit_unknown"] += 1
        stats["flag"]["no_temperature"] += 1
    else:
        stats["avail"]["has_temperature"] += 1
        stats["temp_bins"][_bin_label(temperature_C, TEMPERATURE_BINS,
                                      TEMPERATURE_BIN_LABELS)] += 1
        if abs(temperature_C) < 1e-9:
            # 【实测】setpoint=0.0 CELSIUS 是真实的冰浴条件（procedure 原文
            # "chilled to 0° C"），不是占位符；单独打标记供下游自行取舍。
            stats["flag"]["temperature_zero"] += 1

    # ---- 条件：反应时间 ----
    reaction_time_min = None
    for oc in rxn.outcomes:
        if oc.HasField("reaction_time"):
            reaction_time_min = _time_to_minutes(oc.reaction_time)
            if reaction_time_min is not None:
                break
    if reaction_time_min is None:
        stats["flag"]["no_reaction_time"] += 1
    else:
        stats["avail"]["has_reaction_time"] += 1

    # ---- reaction_class / metadata ----
    reaction_class = None
    for i in rxn.identifiers:
        if RXN_IDENT_TYPE_NAME.get(i.type) == "REACTION_TYPE" and i.value:
            reaction_class = i.value
            break
    for k, v in rxn.provenance.reaction_metadata.items():
        stats["reaction_metadata_keys"][k] = \
            stats["reaction_metadata_keys"].get(k, 0) + 1
        if reaction_class is None and v:
            reaction_class = v
    if reaction_class:
        stats["avail"]["has_reaction_class"] += 1
        stats["reaction_class"][reaction_class] = \
            stats["reaction_class"].get(reaction_class, 0) + 1
    else:
        stats["flag"]["no_reaction_class"] += 1

    # ---- 缺失标记 ----
    if not (names["SOLVENT"] or smiles["SOLVENT"]):
        stats["flag"]["no_solvent"] += 1
    else:
        stats["avail"]["has_solvent"] += 1
    if not (names["CATALYST"] or smiles["CATALYST"]):
        stats["flag"]["no_catalyst"] += 1
    else:
        stats["avail"]["has_catalyst"] += 1
    if not (names["REAGENT"] or smiles["REAGENT"]):
        stats["flag"]["no_reagent"] += 1
    else:
        stats["avail"]["has_reagent"] += 1
    if not names["REACTANT"]:
        stats["flag"]["no_reactant_names"] += 1
    else:
        stats["avail"]["has_reactant_names"] += 1
    n_no_smi = 0
    for oc in rxn.outcomes:
        for p in oc.products:
            if not any(_ident_idtype_name(i) in ("SMILES", "CXSMILES") and i.value
                       for i in p.identifiers):
                n_no_smi += 1
    if n_no_smi:
        stats["flag"]["product_compound_without_smiles_id"] += n_no_smi

    doi = rxn.provenance.doi or None
    patent = rxn.provenance.patent or None
    if doi:
        stats["avail"]["has_doi"] += 1
    else:
        stats["flag"]["no_doi"] += 1
    if patent:
        stats["avail"]["has_patent"] += 1
    else:
        stats["flag"]["no_patent"] += 1

    product_plain = mc.canon_plain(rhs)
    if product_plain:
        stats["avail"]["has_product_smiles"] += 1

    if len(valid[chosen]) + len(others) > 1:
        stats["flag"]["yield_multiple_measurements"] += 1
        if yalt is not None and abs(ymax - yalt) > 0.5:
            stats["flag"]["yield_inconsistent"] += 1
    stats["yield_bins"][_bin_label(ymax, YIELD_BINS, YIELD_BIN_LABELS)] += 1

    row = {
        "reaction_id": rid,
        "reaction_class": reaction_class,
        "reactants": lhs,
        "reactants_n": len([x for x in lhs.split(".") if x]),
        "reactant_names": ";".join(names["REACTANT"]) or None,
        "reactant_smiles_components": ";".join(smiles["REACTANT"]) or None,
        "product": rhs,
        "product_smiles": product_plain,
        "yield_percent": ymax,
        "yield_source_details": chosen,
        "yield_n_measurements": len(valid[chosen]) + len(others),
        "yield_alt_percent": yalt,
        "temperature_C": temperature_C,
        "temperature_source": temperature_source,
        "solvent_names": ";".join(names["SOLVENT"]) or None,
        "solvent_smiles": ";".join(smiles["SOLVENT"]) or None,
        "solvent_source": solvent_source or None,
        "catalyst_names": ";".join(names["CATALYST"]) or None,
        "catalyst_smiles": ";".join(smiles["CATALYST"]) or None,
        "reagent_names": ";".join(names["REAGENT"]) or None,
        "reagent_smiles": ";".join(smiles["REAGENT"]) or None,
        "agents_mapped": agents or None,
        "reaction_time_min": reaction_time_min,
        "doi": doi,
        "patent": patent,
        "n_outcomes": len(rxn.outcomes),
        "n_products": n_products,
        "row_group": rg_index,
    }
    stats["rows"] += 1
    return row


# --------------------------------------------------------------------------- #
# 落盘
# --------------------------------------------------------------------------- #
def write_parquet_atomic(rows, path):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    table = pa.Table.from_pylist(rows, schema=ROW_SCHEMA)
    pq.write_table(table, str(tmp), compression="zstd")
    os.replace(str(tmp), str(path))


def write_json_atomic(obj, path):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(str(tmp), str(path))


# --------------------------------------------------------------------------- #
# 分片 worker（模块级函数，可被 ProcessPoolExecutor pickle）
# --------------------------------------------------------------------------- #
def process_shard(job):
    shard_idx, rg_indices, parquet_path, out_dir, show_raw = job
    t0 = time.time()
    stats = new_stats()
    stats["row_groups"] = list(rg_indices)
    rows = []
    raw_shown = 0
    pf = pq.ParquetFile(parquet_path)
    for gi in rg_indices:
        tbl = pf.read_row_group(gi, columns=["reaction_id", "reaction"])
        rids = tbl.column("reaction_id").to_pylist()
        blobs = tbl.column("reaction").to_pylist()
        for rid, blob in zip(rids, blobs):
            if show_raw and raw_shown < show_raw:
                try:
                    rxn = R.Reaction()
                    rxn.ParseFromString(blob)
                    print("=" * 72, flush=True)
                    print(f"### 原始记录 {raw_shown + 1}  reaction_id={rid}  "
                          f"row_group={gi}", flush=True)
                    print("=" * 72, flush=True)
                    print(text_format.MessageToString(rxn), flush=True)
                    raw_shown += 1
                except Exception as e:
                    print(f"!!! 原始记录打印失败 {rid}: {type(e).__name__} {e}",
                          flush=True)
                    stats["fail"]["fail_protobuf"] += 0
            row = extract_record(rid, blob, gi, stats)
            if row is not None:
                rows.append(row)
    out_dir = Path(out_dir)
    write_parquet_atomic(rows, out_dir / f"shard_{shard_idx:04d}.parquet")
    stats["elapsed_s"] = round(time.time() - t0, 2)
    stats["shard_idx"] = shard_idx
    write_json_atomic(stats, out_dir / f"shard_{shard_idx:04d}.stats.json")
    return stats


def plan_shards(parquet_path, shard_rows):
    """按 parquet row group 规划分片：返回 [[rg_index, ...], ...]。"""
    pf = pq.ParquetFile(parquet_path)
    md = pf.metadata
    counts = [md.row_group(i).num_rows for i in range(md.num_row_groups)]
    shards, cur, cur_n = [], [], 0
    for gi, n in enumerate(counts):
        if cur and cur_n + n > shard_rows:
            shards.append(cur)
            cur, cur_n = [], 0
        cur.append(gi)
        cur_n += n
    if cur:
        shards.append(cur)
    return shards, counts


# --------------------------------------------------------------------------- #
# 摘要
# --------------------------------------------------------------------------- #
def load_shard_stats(out_dir):
    files = sorted(Path(out_dir).glob("shard_*.stats.json"))
    merged = new_stats()
    n_done = 0
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                s = json.load(fh)
        except Exception as e:
            print(f"!! 统计文件读取失败 {f.name}: {type(e).__name__} {e}", flush=True)
            continue
        merge_stats(merged, s)
        n_done += 1
    return merged, n_done


def verify_shard_files(out_dir, merged):
    """独立核对：直接读每个分片 parquet 的 footer 行数，与 stats 里累计的行数比对。
    （不信任自己写的 stats，防「静默漏写/写坏」。）"""
    out_dir = Path(out_dir)
    files = sorted(out_dir.glob("shard_*.parquet"))
    total = 0
    mismatched = []
    unreadable = []
    for f in files:
        try:
            n = pq.ParquetFile(str(f)).metadata.num_rows
        except Exception as e:
            unreadable.append(f"{f.name}: {type(e).__name__} {e}")
            continue
        total += n
        idx = int(f.stem.split("_")[1])
        st_path = out_dir / f"shard_{idx:04d}.stats.json"
        if st_path.exists():
            try:
                with open(st_path, encoding="utf-8") as fh:
                    st_rows = json.load(fh).get("rows", None)
            except Exception as e:
                unreadable.append(f"{st_path.name}: {type(e).__name__} {e}")
                continue
            if st_rows is not None and st_rows != n:
                mismatched.append({"shard": idx, "parquet_rows": n,
                                   "stats_rows": st_rows})
    tmp_left = [p.name for p in out_dir.glob("*.tmp")]
    return {
        "n_parquet_files": len(files),
        "parquet_rows_total": total,
        "stats_rows_total": merged["rows"],
        "rows_match": total == merged["rows"],
        "mismatched_shards": mismatched[:20],
        "n_mismatched": len(mismatched),
        "unreadable": unreadable[:20],
        "leftover_tmp_files": tmp_left,
    }


def rate(num, den):
    return (num / den) if den else 0.0


def print_summary(merged, n_shards_done, n_shards_total, n_rows_total,
                  extra_lines=()):
    rows = merged["rows"]
    proc = merged["n_records"]
    print("\n" + "=" * 78)
    print("【抽取摘要】")
    print("=" * 78)
    for ln in extra_lines:
        print(ln)
    print(f"  parquet 总记录数            : {n_rows_total}")
    print(f"  本次累计已处理记录          : {proc}")
    print(f"  完成分片                    : {n_shards_done} / {n_shards_total}")
    print(f"  ★ 有数值收率的行（本表行数）: {rows}"
          f"  （占已处理 {rate(rows, proc) * 100:.2f}%）")
    print(f"  HTE 对照 27,497 行 -> 倍数  : {rate(rows, 27497):.1f}x")
    print("-" * 78)
    print("  失败分类（互相独立计数，不静默丢弃）：")
    for k in FAIL_KEYS:
        v = merged["fail"].get(k, 0)
        print(f"    {k:32s} {v:9d}  ({rate(v, proc) * 100:6.2f}% of 已处理)")
    tot_fail = sum(merged["fail"].values())
    print(f"    {'合计丢弃':32s} {tot_fail:9d}")
    print("-" * 78)
    print("  可得率（分母 = 本表行数）：")
    for k in AVAIL_KEYS:
        v = merged["avail"].get(k, 0)
        print(f"    {k:32s} {v:9d}  ({rate(v, rows) * 100:6.2f}%)")
    print("-" * 78)
    print("  行内缺失/标记计数：")
    for k in FLAG_KEYS:
        v = merged["flag"].get(k, 0)
        print(f"    {k:32s} {v:9d}  ({rate(v, rows) * 100:6.2f}%)")
    print("-" * 78)
    print("  温度分布（分母 = 有温度的行）：")
    for lab in TEMPERATURE_BIN_LABELS:
        v = merged["temp_bins"].get(lab, 0)
        print(f"    {lab:12s} {v:9d}  ({rate(v, merged['avail'].get('has_temperature', 0)) * 100:6.2f}%)")
    print(f"  温度单位计数: {merged['temp_units']}")
    print("-" * 78)
    print("  yield 分布（分母 = 本表行数）：")
    for lab in YIELD_BIN_LABELS:
        v = merged["yield_bins"].get(lab, 0)
        print(f"    {lab:12s} {v:9d}  ({rate(v, rows) * 100:6.2f}%)")
    print(f"  yield 测量 details 计数: {dict(Counter(merged['yield_details']).most_common(8))}")
    print(f"  实际选用 details 计数   : {dict(Counter(merged['yield_chosen_details']).most_common(8))}")
    print(f"  越界(丢弃)值分档        : {merged['yield_oor_mild']}"
          f"  （mild = 100<v<=130，extreme = v>130）")
    print("-" * 78)
    print(f"  reaction class 种数        : {len(merged['reaction_class'])}"
          f"  （有 class 的行 {merged['avail'].get('has_reaction_class', 0)}）")
    print(f"    top: {dict(Counter(merged['reaction_class']).most_common(10))}")
    print(f"  标识类型计数: {merged['ident_types']}")
    print(f"  reaction_role 计数: {dict(Counter(merged['role_counts']).most_common(10))}")
    print(f"  provenance.reaction_metadata 键: {merged['reaction_metadata_keys']}")
    print("=" * 78, flush=True)


def write_summary_json(merged, args, n_shards_done, n_shards_total, n_rows_total,
                       complete, progress=None, verify=None):
    rows = merged["rows"]
    proc = merged["n_records"]
    obj = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "complete": bool(complete),
        "parquet": str(getattr(args, "parquet", DEFAULT_PARQUET)),
        "out_dir": str(getattr(args, "out", DEFAULT_OUT)),
        "parquet_total_records": n_rows_total,
        "n_shards_total": n_shards_total,
        "n_shards_done": n_shards_done,
        "n_records_processed": proc,
        "rows_with_numeric_yield": rows,
        "yield_yield_rate_of_processed": round(rate(rows, proc), 6),
        "yield_ratio_vs_hte_27497": round(rate(rows, 27497), 3),
        "shard_rows": getattr(args, "shard_rows", None),
        "fail_counts": merged["fail"],
        "fail_total": sum(merged["fail"].values()),
        "flag_counts": merged["flag"],
        "availability_counts": merged["avail"],
        "availability_rate_of_rows": {k: round(rate(v, rows), 6)
                                      for k, v in merged["avail"].items()},
        "temperature_bins": merged["temp_bins"],
        "temperature_units": merged["temp_units"],
        "yield_bins": merged["yield_bins"],
        "yield_measurement_details": merged["yield_details"],
        "yield_chosen_details": merged["yield_chosen_details"],
        "yield_out_of_range_bands": merged["yield_oor_mild"],
        "reaction_class_counts": merged["reaction_class"],
        "n_reaction_classes": len(merged["reaction_class"]),
        "identifier_type_counts": merged["ident_types"],
        "reaction_role_counts": merged["role_counts"],
        "reaction_metadata_keys": merged["reaction_metadata_keys"],
        "n_row_groups_done": len(merged["row_groups"]),
        "extract_seconds_summed": round(merged["elapsed_s"], 1),
        "progress": progress,
        "shard_file_verification": verify,
    }
    write_json_atomic(obj, SUMMARY_JSON)
    print(f"[summary] 已写 {SUMMARY_JSON}", flush=True)
    return obj


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def run_sample(args):
    """--limit N：复用 forward_template_mining 的可复现 reservoir 抽样。"""
    import duckdb
    parquet_path = Path(args.parquet)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    t0 = time.time()
    rows = con.execute(
        f"SELECT reaction_id, reaction FROM read_parquet('{parquet_path.as_posix()}') "
        f"USING SAMPLE {args.limit} ROWS (reservoir, {args.seed})").fetchall()
    t_sample = time.time() - t0
    print(f"[sample] reservoir 抽样 {len(rows)} 条  seed={args.seed}  "
          f"耗时 {t_sample:.1f}s", flush=True)

    if args.show_raw:
        shown = 0
        for rid, blob in rows:
            if shown >= args.show_raw:
                break
            try:
                rxn = R.Reaction()
                rxn.ParseFromString(blob)
            except Exception as e:
                print(f"!!! 原始记录打印失败 {rid}: {type(e).__name__} {e}", flush=True)
                continue
            shown += 1
            print("=" * 72, flush=True)
            print(f"### 原始记录 {shown}  reaction_id={rid}  (抽样第 {shown} 条)", flush=True)
            print("=" * 72, flush=True)
            print(text_format.MessageToString(rxn), flush=True)

    stats = new_stats()
    out_rows = []
    t0 = time.time()
    for rid, blob in rows:
        row = extract_record(rid, blob, -1, stats)
        if row is not None:
            out_rows.append(row)
    stats["elapsed_s"] = round(time.time() - t0, 2)
    sample_name = f"sample_limit{args.limit}_seed{args.seed}"
    write_parquet_atomic(out_rows, out_dir / f"{sample_name}.parquet")
    write_json_atomic(stats, out_dir / f"{sample_name}.stats.json")
    print(f"[sample] 写出 {len(out_rows)} 行 -> {out_dir / (sample_name + '.parquet')}",
          flush=True)
    print_summary(stats, 1, 1, len(rows),
                  extra_lines=[f"  ★ 模式：reservoir 抽样 limit={args.limit} "
                               f"seed={args.seed}（单文件，未切片）",
                               f"  抽样耗时 {t_sample:.1f}s，解析耗时 {stats['elapsed_s']}s"])
    obj = write_summary_json(stats, args, 1, 1, len(rows), complete=False,
                             progress={"mode": "sample", "limit": args.limit,
                                       "seed": args.seed,
                                       "note": "小样本验证，不是全量；全量分片跑完后本文件会被覆盖为 complete=true"})
    obj["mode"] = "sample"
    return 0


def run_full(args):
    parquet_path = Path(args.parquet)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    shards, counts = plan_shards(parquet_path, args.shard_rows)
    n_total = sum(counts)
    print(f"[full] parquet={parquet_path}", flush=True)
    print(f"[full] 总记录 {n_total}，row group {len(counts)} 个，"
          f"分片 {len(shards)} 片（每片 ~{args.shard_rows} 条）", flush=True)

    done = []
    pending = []
    for idx, rgs in enumerate(shards):
        pf_file = out_dir / f"shard_{idx:04d}.parquet"
        st_file = out_dir / f"shard_{idx:04d}.stats.json"
        if pf_file.exists() and st_file.exists():
            done.append(idx)
        else:
            pending.append(idx)
    if done and not args.resume:
        print(f"!! 输出目录已有 {len(done)} 个已完成分片，但未传 --resume。"
              f"为避免把两次运行混在一起，直接退出。", flush=True)
        return 2
    print(f"[full] 已完成分片 {len(done)}（{'跳过' if done else '无'}），"
          f"待处理 {len(pending)}", flush=True)
    if args.max_shards:
        pending = pending[:args.max_shards]
        print(f"[full] --max-shards={args.max_shards} -> 本次只处理 {len(pending)} 片",
              flush=True)
    if not pending:
        print("[full] 没有待处理分片，直接汇总。", flush=True)
        merged, n_done = load_shard_stats(out_dir)
        print_summary(merged, n_done, len(shards), n_total)
        write_summary_json(merged, args, n_done, len(shards), n_total, complete=True)
        return 0

    jobs = [(idx, shards[idx], str(parquet_path), str(out_dir), args.show_raw)
            for idx in pending]
    merged = new_stats()
    if done:
        merged, _ = load_shard_stats(out_dir)
    t_start = time.time()
    n_done_now = len(done)
    n_failed = 0
    run_records = 0
    progress_path = out_dir / PROGRESS_JSON_NAME
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(process_shard, j): j[0] for j in jobs}
        for fut in as_completed(futs):
            idx = futs[fut]
            try:
                st = fut.result()
            except Exception:
                n_failed += 1
                print(f"!!! 分片 {idx} 失败（不静默跳过）：\n"
                      f"{traceback.format_exc()}", flush=True)
                continue
            merge_stats(merged, st)
            run_records += st["n_records"]
            n_done_now += 1
            el = time.time() - t_start
            rate_rec = run_records / el if el > 0 else 0.0
            remain = n_total - sum(counts[i] for i in done) - run_records
            eta = remain / rate_rec if rate_rec > 0 else float("inf")
            print(f"[shard {idx:04d}] rg {st['row_groups'][0]}-{st['row_groups'][-1]} "
                  f"记录 {st['n_records']} 行 {st['rows']} "
                  f"耗时 {st['elapsed_s']}s | 累计 {n_done_now}/{len(shards)} 片 "
                  f"本次 {run_records}/{n_total - sum(counts[i] for i in done)} 条 "
                  f"({rate_rec:.0f} 条/s) ETA {eta / 60:.1f} min", flush=True)
            write_json_atomic({
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "n_shards_total": len(shards),
                "n_shards_done": n_done_now,
                "n_shards_failed": n_failed,
                "n_records_processed_all_shards": merged["n_records"],
                "n_records_this_run": run_records,
                "rows_written_all_shards": merged["rows"],
                "parquet_total_records": n_total,
                "elapsed_s": round(el, 1),
                "records_per_s": round(rate_rec, 1),
                "eta_s": None if math.isinf(eta) else round(eta, 1),
                "workers": args.workers,
                "shard_rows": args.shard_rows,
            }, progress_path)

    merged, n_done_all = load_shard_stats(out_dir)
    complete = (n_done_all == len(shards)) and n_failed == 0
    prog = {"mode": "full", "elapsed_s": round(time.time() - t_start, 1),
            "workers": args.workers, "shard_rows": args.shard_rows,
            "n_shards_failed_this_run": n_failed}
    print_summary(merged, n_done_all, len(shards), n_total,
                  extra_lines=[f"  ★ 模式：全量分片  workers={args.workers} "
                               f"shard_rows={args.shard_rows}",
                               f"  本次失败分片 {n_failed}；累计完成分片 "
                               f"{n_done_all}/{len(shards)}；complete={complete}",
                               f"  本次运行耗时 {(time.time() - t_start) / 60:.1f} min"])
    write_summary_json(merged, args, n_done_all, len(shards), n_total,
                       complete=complete, progress=prog,
                       verify=verify_shard_files(out_dir, merged))
    return 0 if n_failed == 0 else 1


def main():
    ap = argparse.ArgumentParser(
        description="ORD 全量 -> 条件+数值收率训练表（可续跑分片）")
    ap.add_argument("--limit", type=int, default=0,
                    help=">0 时走可复现 reservoir 抽样 N 条（小样本验证，单文件）")
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT),
                    help="输出目录（分片 + 统计）")
    ap.add_argument("--seed", type=int, default=20261013,
                    help="--limit 抽样用的随机种子（可复现）")
    ap.add_argument("--resume", action="store_true",
                    help="跳过已完成分片；不传且目录已有分片则报错退出")
    ap.add_argument("--workers", type=int, default=1, help="并行进程数（默认 1）")
    ap.add_argument("--shard-rows", type=int, default=10000,
                    help="每片目标记录数（默认 10000 = 10 个 row group）")
    ap.add_argument("--max-shards", type=int, default=0,
                    help="单次运行最多处理多少片（0=不限）")
    ap.add_argument("--show-raw", type=int, default=-1,
                    help="解析前先打印几条完整原始记录（默认 limit 模式 3，全量 0）")
    ap.add_argument("--parquet", type=str, default=str(DEFAULT_PARQUET))
    ap.add_argument("--summary-only", action="store_true",
                    help="只合并已有分片统计写 summary.json")
    args = ap.parse_args()

    if args.show_raw < 0:
        args.show_raw = 3 if args.limit else 0

    if args.summary_only:
        if not Path(args.out).exists():
            print(f"!! 输出目录不存在：{args.out}", flush=True)
            return 2
        shards, counts = plan_shards(Path(args.parquet), args.shard_rows)
        merged, n_done = load_shard_stats(args.out)
        verify = verify_shard_files(args.out, merged)
        print(f"[verify] 分片 parquet 行数合计 {verify['parquet_rows_total']} vs "
              f"stats 合计 {verify['stats_rows_total']} -> "
              f"match={verify['rows_match']}；不一致 {verify['n_mismatched']} 片；"
              f"残留 .tmp {verify['leftover_tmp_files']}", flush=True)
        print_summary(merged, n_done, len(shards), sum(counts))
        # 把上次真跑的运行信息（_progress.json / 旧 summary）保留下来，别弄丢
        prev_progress = None
        prog_path = Path(args.out) / PROGRESS_JSON_NAME
        if prog_path.exists():
            try:
                with open(prog_path, encoding="utf-8") as fh:
                    prev_progress = json.load(fh)
            except Exception as e:
                print(f"!! _progress.json 读取失败（忽略）：{type(e).__name__} {e}",
                      flush=True)
        if prev_progress is None and SUMMARY_JSON.exists():
            try:
                with open(SUMMARY_JSON, encoding="utf-8") as fh:
                    prev_progress = json.load(fh).get("progress")
            except Exception as e:
                print(f"!! 旧 summary 读取失败（忽略）：{type(e).__name__} {e}", flush=True)
        write_summary_json(merged, args, n_done, len(shards), sum(counts),
                           complete=(n_done == len(shards)), verify=verify,
                           progress=prev_progress)
        return 0

    if args.limit > 0:
        return run_sample(args)
    return run_full(args)


if __name__ == "__main__":
    sys.exit(main())
