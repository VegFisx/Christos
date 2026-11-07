# -*- coding: utf-8 -*-
r"""第十四轮 / 任务①：用 ORD 自抽【正向】模板，能不能把覆盖率从 28.6% 顶上去？

背景：上一轮 pilot（tools/extract_new_templates.py，4000 抽样）的结论是
      「新模板只救回 4~5 / 358 个零覆盖目标」= 整体 ≈ +0.4%。本脚本把它做成
      **规模化 + 口径写死** 的实验，回答一个问题：增量到底有多少。

口径（写死，不许事后改）：
  1. 抽样：BIG parquet 的 `USING SAMPLE N ROWS (reservoir, seed)`，seed 固定 -> 可复现。
  2. 可用反应：CXSMILES 拆三段；产物有映射；**恰好 2 个组分的原子进入产物**（与
     tools/validate_ord_coverage.py 的「可测」口径一致）；去重 (r1,r2,product)。
  3. 划分：md5(r1|r2|product) 奇偶 -> train / test（互不相交）。
  4. 基准覆盖率：test 上 `ReactionEnumerator.enumerate_pair(r1,r2)` 能否复现记录产物
     —— 与官方口径同为「恰 2 底物」的可测集。
  5. 挖掘：只用 **train 里基准漏掉的**反应抽 rdchiral 模板，再反转成【正向】
     （rdchiral 给的是 产物>>底物）。两种形态：
        raw = rdchiral 原样； gen = 泛化（只留 元素+芳香性+电荷+原子映射号）
  6. 选择：按「train 支持数 >= K」筛选，K ∈ {1,2,3,5}。
  7. 验收（在 test 上，且只看基准漏掉的那些反应）：
        增量命中 = 新模板产出了记录产物
        φ 宽松度 = 新模板在 test 反应上「有产出」的比例（有产出≠错，但过宽说明模板太泛）
  说明：本轮只回答「增量与宽松度」，不把新模板接进引擎（接引擎要看增量是否值得）。

用法: python forward_template_mining.py [抽样数] [seed]
输出: reports/forward_template_mining.json

======================= 第十七轮新增（可选参数，默认行为不变）=======================
`--cond-out PATH`：额外为【每条模板】记录它来自哪些 ORD 记录的**条件分布**，
让条件判据能按「这条模板实际在什么条件下被做出来过」门控，而不是靠 37 类的类名。

  python forward_template_mining.py [抽样数] [seed] --cond-out reports/mined_forward_templates_v2.jsonl

  · **不传 `--cond-out` 时行为与旧版完全一致**（同一抽样、同一抽取、同一输出数字）。
  · 传了才写 v2 jsonl：在原三字段外再加
      temp_C   {min,p25,median,p75,max,n}   来源记录摄氏温度分布（缺失不计入 n）
      solvents {溶剂名: 次数}                来源记录溶剂计数（记录内去重）
      solvent_smiles {SMILES: 次数}          同上，SMILES 形态（引擎条件表按试剂 SMILES 键）
      n_src / n_temp_known / n_solv_known    来源记录数 / 其中温度、溶剂可得数
      solv_source {components|cxsmiles_agents|无: 条数}
  · 温度/溶剂解析**复用** tools/ord_condition_dataset.py（不重写 protobuf 解析）。
  · ★ 保护只读件：传了 `--cond-out` 时**不覆盖** reports/mined_forward_templates.jsonl
    （除非显式 `--overwrite-v1=1`），并在写 v2 前逐条校验两文件的 support 一致性。
  · 其它可选：`--show-raw K`（默认 5）打印前 K 条来源记录的 yield/conditions 原文；
    `--limit N` / `--seed N` 是位置参数的显式写法；
    `--extract-budget S`（默认 600，与旧版一致）改抽模板的墙钟预算 ——
    **做 v1 一致性校验时必须放大**（如 3600），否则机器负载会让它提前 break 成子集。
"""
import hashlib
import json
import math
import random
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
for _p in (STAGE / "libs", STAGE / "tools"):
    sys.path.insert(0, str(_p))

import duckdb  # noqa: E402
from google.protobuf import text_format  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdChemReactions  # noqa: E402
from rdchiral.template_extractor import extract_from_reaction  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

import mapped_chem as mc  # noqa: E402
# ★ 第十七轮：条件解析复用这个模块（已被验证过的口径），不重写 protobuf 解析 ★
import ord_condition_dataset as ocd  # noqa: E402

RDLogger.DisableLog("rdApp.*")

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
OUT = STAGE / "reports" / "forward_template_mining.json"
OUT_TMPL = STAGE / "reports" / "mined_forward_templates.jsonl"   # ★ 挖到的模板（可复用）
OUT_TMPL_V2 = STAGE / "reports" / "mined_forward_templates_v2.jsonl"       # ★ 带条件分布
OUT_SUM_V2 = STAGE / "reports" / "mined_forward_templates_v2_summary.json"


def _parse_argv(argv):
    r"""解析参数。★ 不传新参数时，位置参数语义与旧版完全一致 ★

    旧：python forward_template_mining.py [抽样数] [seed]
    """
    positional, opts = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if "=" in key:
                key, val = key.split("=", 1)
            else:
                i += 1
                val = argv[i] if i < len(argv) else ""
            opts[key] = val
        else:
            positional.append(a)
        i += 1
    return positional, opts


_POS, _OPTS = _parse_argv(sys.argv[1:])
if len(_POS) > 2:
    print(f"[参数] 忽略多余位置参数：{_POS[2:]}", flush=True)
N_SAMPLE = int(_OPTS["limit"] if _OPTS.get("limit") else
               (_POS[0] if len(_POS) > 0 else 40000))
SEED = int(_OPTS["seed"] if _OPTS.get("seed") else
           (_POS[1] if len(_POS) > 1 else 20261012))
COND_OUT = Path(_OPTS["cond-out"]) if _OPTS.get("cond-out") else None
# --out-json 只用于小样本冒烟测试时别覆盖正式结果（默认路径不变）
OUT_JSON = Path(_OPTS["out-json"]) if _OPTS.get("out-json") else OUT
# --tmpl-out 同上，只用于把 v1 模板落盘改到别处（默认路径不变）；一致性校验仍读真 v1
OUT_TMPL_WRITE = Path(_OPTS["tmpl-out"]) if _OPTS.get("tmpl-out") else OUT_TMPL
SHOW_RAW = int(_OPTS["show-raw"]) if _OPTS.get("show-raw") else 5
OVERWRITE_V1 = bool(_OPTS.get("overwrite-v1"))
K_GRID = (1, 2, 3, 5)
MAX_EVAL_TARGETS = 4000      # test 上最多评估多少条漏掉的反应（算力护栏）
MAX_PROBE = 500              # 宽松度探针的样本数
MAX_TEMPLATES_PER_VARIANT = 600
# 抽模板的时间预算（rdchiral 在复杂分子上会掉到 ~1 条/秒）。
# ★ 默认 600 与旧版一致；但它是**墙钟**预算 —— 机器被别的任务占满时同一份数据会
#   提前 break，导致模板集是 v1 的子集。要严格复现 v1（如做 support 校验）就显式
#   放大：--extract-budget=3600。v1 那次运行的 skipped_by_budget=0（实测），
#   所以「一条不漏地跑完 tr_miss」= v1 的模板全集。
EXTRACT_BUDGET_S = int(_OPTS["extract-budget"]) if _OPTS.get("extract-budget") else 600
MAX_HEAVY_ATOMS = 70         # 底物+产物重原子总数超过它就跳过抽取（慢且难泛化）


def generalize_smarts(smarts):
    r"""把模板原子剥到只剩 元素+芳香性+电荷+映射号（解决 rdchiral radius=1 过拟合）。"""
    try:
        rx = rdChemReactions.ReactionFromSmarts(smarts)
    except Exception:
        return None
    if rx is None:
        return None

    def gen(mol):
        if mol is None:
            return None
        rw = Chem.RWMol()
        idx = {}
        for a in mol.GetAtoms():
            na = Chem.Atom(a.GetAtomicNum())
            na.SetIsAromatic(a.GetIsAromatic())
            na.SetFormalCharge(a.GetFormalCharge())
            na.SetAtomMapNum(a.GetAtomMapNum())
            idx[a.GetIdx()] = rw.AddAtom(na)
        for b in mol.GetBonds():
            rw.AddBond(idx[b.GetBeginAtomIdx()], idx[b.GetEndAtomIdx()], b.GetBondType())
        m = rw.GetMol()
        try:
            Chem.SanitizeMol(m)
        except Exception:
            return None
        try:
            return Chem.MolToSmarts(m)
        except Exception:
            return None

    rs = [gen(rx.GetReactantTemplate(i)) for i in range(rx.GetNumReactantTemplates())]
    ps = [gen(rx.GetProductTemplate(i)) for i in range(rx.GetNumProductTemplates())]
    if any(x is None for x in rs + ps) or not rs or not ps:
        return None
    return ".".join(rs) + ">>" + ".".join(ps)


# --------------------------------------------------------------------------- #
# ★ 第十七轮新增：模板 -> 来源记录的条件分布（只在传 --cond-out 时启用）★
#   条件解析【复用】tools/ord_condition_dataset.py 的口径与函数，不重写 protobuf 解析：
#     · ocd.ROLE_NAME            ReactionRole 枚举号 -> 名字
#                                （本环境 R.ReactionRole 是 message，Name() 不存在，
#                                  必须走 field descriptor 反查；坑已在那边解决）
#     · ocd._compound_smiles_name 组分 NAME / SMILES 取法
#     · ocd._temp_to_celsius      CELSIUS / KELVIN / FAHRENHEIT -> 摄氏
#   失败一律分类计数（禁止静默 continue）。
# --------------------------------------------------------------------------- #
def new_cond_stats():
    return {"n_rec": 0, "avail": Counter(), "fail": Counter(),
            "temp_units": Counter(), "temp_bins": Counter(),
            "solv_source": Counter(), "solv_key_kind": Counter(),
            "n_agents_split": 0}


def extract_conditions(rxn, agents, stats):
    r"""解析单条 ORD 记录的温度/溶剂。返回 per-record dict（溶剂在记录内去重）。"""
    stats["n_rec"] += 1

    # ---- 温度（口径照抄 ord_condition_dataset.extract_record）----
    temp_C, temp_source = None, None
    tc = rxn.conditions.temperature
    has_sp = tc.HasField("setpoint")
    if has_sp:
        temp_C = ocd._temp_to_celsius(tc.setpoint, stats["temp_units"])
        if temp_C is not None:
            temp_source = "setpoint"
    if temp_C is None and tc.measurements:
        for t in tc.measurements:
            temp_C = ocd._temp_to_celsius(t, stats["temp_units"])
            if temp_C is not None:
                temp_source = "measurement"
                break
    if temp_C is None:
        stats["fail"]["温度_单位未知" if (has_sp or tc.measurements)
                     else "无温度字段"] += 1
    else:
        stats["avail"]["温度"] += 1
        stats["temp_bins"][ocd._bin_label(temp_C, ocd.TEMPERATURE_BINS,
                                          ocd.TEMPERATURE_BIN_LABELS)] += 1
        if abs(temp_C) < 1e-9:
            # 【实测】setpoint=0.0 CELSIUS 是真实冰浴，不是缺失（同 ocd 的口径）
            stats["avail"]["温度_恰好0C_真冰浴"] += 1

    # ---- 溶剂：inputs[*].components[*].reaction_role == SOLVENT ----
    names, smis = {}, {}
    for _key, inp in rxn.inputs.items():
        for comp in inp.components:
            if ocd.ROLE_NAME.get(comp.reaction_role, "?") != "SOLVENT":
                continue
            smi, nm = ocd._compound_smiles_name(comp)
            if nm:
                names[nm] = 1
                stats["solv_key_kind"]["组分NAME"] += 1
            elif smi:
                names[smi] = 1            # 【推断】没 NAME 时回退用 SMILES 当键
                stats["solv_key_kind"]["组分仅SMILES_回退"] += 1
            else:
                stats["fail"]["溶剂组分无NAME也无SMILES"] += 1
            if smi:
                smis[smi] = 1
            elif nm:
                smis[nm] = 1
    src = ""
    if names:
        src = "components"
    elif agents:
        # 口径照抄 ocd：没有 SOLVENT 组分时用 CXSMILES 中间段当溶剂；
        # 【推断】中间段是 "." 分隔的 SMILES 串，这里拆成单个溶剂以便逐个匹配。
        src = "cxsmiles_agents"
        parts = [p for p in agents.split(".") if p]
        for p in parts:
            names[p] = 1
            smis[p] = 1
        stats["n_agents_split"] += len(parts)
    if names:
        stats["avail"]["溶剂"] += 1
    else:
        stats["fail"]["无溶剂"] += 1
    stats["solv_source"][src or "无"] += 1
    return {"temp_C": temp_C, "temp_source": temp_source, "solvents": names,
            "solvent_smiles": smis, "solv_source": src}


def _pctl(sorted_vals, q):
    """线性插值分位数（与 numpy 默认 linear 同口径）。输入必须已排序。"""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return sorted_vals[0]
    pos = (n - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def temp_stats(vals):
    """{min,p25,median,p75,max,n}；n 为温度可得数（缺失行不进来）。"""
    if not vals:
        return None
    s = sorted(vals)
    return {"min": round(s[0], 2), "p25": round(_pctl(s, 0.25), 2),
            "median": round(_pctl(s, 0.5), 2), "p75": round(_pctl(s, 0.75), 2),
            "max": round(s[-1], 2), "n": len(s)}


def _clip(s, n):
    s = str(s).replace("\n", " | ")
    return s if len(s) <= n else s[:n] + f" ...[裁剪,原文{len(s)}字符]"


def raw_record_dump(rxn, rec, tag, why):
    """打印一条来源记录的原文（yields / conditions / inputs 角色），用于人工核对。"""
    print("\n" + "=" * 78)
    print(f"[来源记录原文 {tag}] {why}")
    print(f"  CXSMILES 产物侧(rhs)={_clip(rec['rhs'], 120)}")
    print(f"  CXSMILES 中间段(agents)={_clip(rec['agents'], 160)}")
    print("  --- conditions（原文）---")
    print("  " + _clip(text_format.MessageToString(rxn.conditions), 900))
    for oi, oc in enumerate(rxn.outcomes):
        # ★ 坑：RepeatedCompositeContainer 没有 DESCRIPTOR，不能整体 MessageToString
        print(f"  --- outcome {oi}（含 yield 原文）---")
        print("  " + _clip(text_format.MessageToString(oc), 900))
    print("  --- inputs 组分角色（原文摘要）---")
    for k, inp in rxn.inputs.items():
        for comp in inp.components:
            rn = ocd.ROLE_NAME.get(comp.reaction_role, "?")
            smi, nm = ocd._compound_smiles_name(comp)
            print(f"    input={k!r} role={rn!r} name={_clip(nm, 60)!r} "
                  f"smiles={_clip(smi, 70)!r}")


def check_support_consistency(v1_path, tmpl_support, tmpl_gen=None):
    """逐条比对 v1 与本次模板集的 (template -> support / generalized)。返回校验 dict。"""
    v1, n_line, n_badline = {}, 0, 0
    with open(v1_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            n_line += 1
            try:
                d = json.loads(line)
                v1[d["template"]] = (int(d["support"]), d.get("generalized"))
            except Exception:
                n_badline += 1
    s1, s2 = set(v1), set(tmpl_support)
    mism = [(t, v1[t][0], tmpl_support[t]) for t in (s1 & s2)
            if v1[t][0] != tmpl_support[t]]
    gen_mism = 0
    if tmpl_gen is not None:
        gen_mism = sum(1 for t in (s1 & s2) if v1[t][1] != tmpl_gen.get(t))
    # ★ 集合差异的性质：把 '@' 全部去掉再比 —— 相等就说明差异只在立体标注
    #   （实测：rdchiral 的 ChiralTag 标注在个别模板上会随进程内哈希顺序在 @/@@ 间翻转，
    #    表现为「同一条模板的 1 个字符位置互换」，generalized 侧完全不受影响）
    o1, o2 = sorted(s1 - s2), sorted(s2 - s1)
    diff_stereo_only = None
    if o1 or o2:
        diff_stereo_only = (sorted(x.replace("@", "") for x in o1)
                            == sorted(x.replace("@", "") for x in o2))
    return {"v1_lines": n_line, "v1_unique": len(v1), "v1_badlines": n_badline,
            "now_unique": len(tmpl_support), "n_common": len(s1 & s2),
            "support_mismatch": len(mism), "mismatch_examples": mism[:5],
            "generalized_mismatch": gen_mism, "diff_stereo_only": diff_stereo_only,
            "only_in_v1": len(o1), "only_in_now": len(o2)}


def engine_k1_set(v1_path, limit=600, min_support=1):
    """复现引擎默认 K1 档加载的模板集合（与 core/smartreact_engine 同一条代码路径）。

    引擎走 tools/rdkit_template_lib.py：load_mined_templates(limit=600) + compile
    -> 实测「加载 600、编译通过 590」。这里直接调用同一模块，保证口径一致。
    """
    import importlib.util
    lib_py = STAGE / "tools" / "rdkit_template_lib.py"
    spec = importlib.util.spec_from_file_location("rdkit_template_lib", lib_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rdkit_template_lib"] = mod
    spec.loader.exec_module(mod)
    tpls = mod.load_mined_templates(Path(v1_path), min_support=min_support,
                                    limit=limit)
    compiled, n_fail = mod.compile_templates(tpls)
    return [sm for sm, _rx in compiled], len(tpls), n_fail


def aggregate_conditions(tmpl_support, tmpl_src):
    """把「模板 -> 来源记录」聚合成 v2 的条件字段。返回 (t -> payload, 统计)。"""
    out = {}
    bad_n_src = 0
    n_src_total = 0
    for t, sup in tmpl_support.most_common():
        srcs = tmpl_src.get(t, [])
        if len(srcs) != sup:
            bad_n_src += 1
        n_src_total += len(srcs)
        temps, solv, solv_smi, src_kind = [], Counter(), Counter(), Counter()
        n_temp_known = n_solv_known = 0
        for r in srcs:
            c = r.get("cond")
            if c is None:                       # 只在分配记录缺失时发生（应恒为 0）
                continue
            if c["temp_C"] is not None:
                temps.append(c["temp_C"])
                n_temp_known += 1
            if c["solvents"]:
                n_solv_known += 1
                for k in c["solvents"]:
                    solv[k] += 1
            for k in c["solvent_smiles"]:
                solv_smi[k] += 1
            src_kind[c["solv_source"] or "无"] += 1
        out[t] = {"temp_C": temp_stats(temps),
                  "solvents": dict(solv.most_common()),
                  "solvent_smiles": dict(solv_smi.most_common()),
                  "n_src": len(srcs),
                  "n_temp_known": n_temp_known,
                  "n_solv_known": n_solv_known,
                  "solv_source": dict(src_kind)}
    return out, {"n_src_total": n_src_total, "templates_with_bad_n_src": bad_n_src}


def coverage_of(smarts_list, tmap):
    """给一批模板 SMARTS，数其中拿到温度/溶剂分布的有多少。"""
    c = Counter()
    for k in ("total", "不在v2表里", "有温度分布", "无温度分布", "有溶剂分布",
              "无溶剂分布", "温度溶剂都有", "温度n>=2", "温度n>=3"):
        c[k] = 0
    for sm in smarts_list:
        e = tmap.get(sm)
        c["total"] += 1
        if e is None:
            c["不在v2表里"] += 1
            continue
        if e["n_temp_known"] > 0:
            c["有温度分布"] += 1
        else:
            c["无温度分布"] += 1
        if e["n_solv_known"] > 0:
            c["有溶剂分布"] += 1
        else:
            c["无溶剂分布"] += 1
        if e["n_temp_known"] > 0 and e["n_solv_known"] > 0:
            c["温度溶剂都有"] += 1
        if e["n_temp_known"] >= 2:
            c["温度n>=2"] += 1
        if e["n_temp_known"] >= 3:
            c["温度n>=3"] += 1
    return dict(c)


def main():
    t_all = time.time()
    cond_stats = new_cond_stats()
    print(f"[参数] 抽样={N_SAMPLE} seed={SEED} "
          f"cond_out={COND_OUT if COND_OUT else '未启用（旧行为）'} "
          f"抽取预算={EXTRACT_BUDGET_S}s", flush=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') "
        f"USING SAMPLE {N_SAMPLE} ROWS (reservoir, {SEED})").fetchall()
    print(f"抽样 {len(rows)} 条（seed={SEED}）", flush=True)

    # ---------------- 1. 整理可用反应 ----------------
    recs, skip, seen = [], Counter(), set()
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            skip["protobuf失败"] += 1
            continue
        cx = next((i.value for i in rxn.identifiers
                   if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES
                   and i.value), None)
        if not cx:
            skip["无CXSMILES"] += 1
            continue
        lhs, agents, rhs = mc.split_rxn(cx)
        if not lhs or not rhs:
            skip["拆段失败"] += 1
            continue
        pm = mc.parse_plain(rhs)
        if pm is None:
            skip["产物SMILES非法"] += 1
            continue
        pmaps = mc.map_nums(pm)
        if not pmaps:
            skip["产物无映射"] += 1
            continue
        product = mc.canon_plain(rhs)
        raws, plains = mc.contributing_components(lhs, pmaps)
        if len(plains) != 2:
            skip[f"贡献组分={len(plains)}"] += 1
            continue
        r1, r2 = sorted(plains)
        if (r1, r2, product) in seen:
            skip["重复"] += 1
            continue
        seen.add((r1, r2, product))
        hid = hashlib.md5(f"{r1}|{r2}|{product}".encode()).hexdigest()
        rec = {"r1": r1, "r2": r2, "product": product,
               "raws": ".".join(raws), "rhs": rhs, "agents": agents or "",
               "split": "train" if int(hid[:8], 16) % 2 == 0 else "test"}
        if COND_OUT:
            # ★ 只在传 --cond-out 时做：复用同一份已解析的 rxn，不重复 parse ★
            rec["cond"] = extract_conditions(rxn, agents or "", cond_stats)
            rec["_blob"] = blob        # 仅用于打印来源记录原文（5 条）
        recs.append(rec)
    tr = [r for r in recs if r["split"] == "train"]
    te = [r for r in recs if r["split"] == "test"]
    print(f"可用 {len(recs)}（去重后）  train {len(tr)}  test {len(te)}")
    print(f"  跳过原因: {dict(skip.most_common(8))}", flush=True)

    # ---------------- 2. 基准覆盖率（现有 9770 模板） ----------------
    enum = ReactionEnumerator()

    def baseline(recs_, tag):
        hit = 0
        miss = []
        t0 = time.time()
        for i, r in enumerate(recs_, 1):
            try:
                res = enum.enumerate_pair(r["r1"], r["r2"])
            except Exception:
                continue
            ok = False
            for x in res:
                for p in x.products:
                    if mc.canon_plain(p) == r["product"]:
                        ok = True
                        break
                if ok:
                    break
            if ok:
                hit += 1
            else:
                miss.append(r)
            if i % 2000 == 0:
                print(f"    [{tag}] {i}/{len(recs_)} 命中 {hit}  {time.time()-t0:.0f}s",
                      flush=True)
        return hit, miss

    tr_hit, tr_miss = baseline(tr, "train")
    te_hit, te_miss = baseline(te, "test")
    base_tr = tr_hit / max(1, len(tr))
    base_te = te_hit / max(1, len(te))
    print(f"\n基准覆盖率：train {tr_hit}/{len(tr)} = {base_tr:.1%}；"
          f"test {te_hit}/{len(te)} = {base_te:.1%}", flush=True)

    # ---------------- 3. 只从 train 的漏项里抽模板 ----------------
    tmpl_support = Counter()
    tmpl_raw = {}
    tmpl_src = {}                  # ★ 模板 -> 来源 rec 列表（仅 --cond-out 用）
    cond_fail = Counter()          # ★ 抽取失败分类（仅 --cond-out 用，不动旧计数器）
    n_dump = 0
    n_try = n_ok = n_too_big = n_budget = 0
    t0 = time.time()
    for r in tr_miss:
        if time.time() - t0 > EXTRACT_BUDGET_S:
            n_budget = len(tr_miss) - n_try
            print(f"    [预算] 抽取超过 {EXTRACT_BUDGET_S}s，跳过剩余 {n_budget} 条"
                  f"（增量因此是**下界**）", flush=True)
            break
        # 过大分子：rdchiral 慢且模板难泛化（实测 ~1 条/秒 -> 跳）
        try:
            ha = (mc.parse_plain(r["r1"]).GetNumHeavyAtoms()
                  + mc.parse_plain(r["r2"]).GetNumHeavyAtoms()
                  + mc.parse_plain(r["product"]).GetNumHeavyAtoms())
        except Exception:
            ha = 0
        if ha > MAX_HEAVY_ATOMS:
            n_too_big += 1
            skip["挖掘_重原子过多"] += 1
            continue
        n_try += 1
        err = None
        try:
            out = extract_from_reaction({"reactants": r["raws"],
                                         "reagents": r["agents"],
                                         "products": r["rhs"], "_id": "x"})
        except Exception as e:
            out, err = None, f"异常_{type(e).__name__}"
        if err is None and (not out or not out.get("reaction_smarts")):
            err = "无reaction_smarts"
        if err is None and (out.get("intra_only") or out.get("dimer_only")):
            err = "intra_only" if out.get("intra_only") else "dimer_only"
        if err is None and ">>" not in out["reaction_smarts"]:
            err = "SMARTS无>>"
        if err is not None:
            # ★ 失败分类计数（旧版这里是静默 continue；只在 --cond-out 时统计）
            if COND_OUT:
                cond_fail[f"抽取_{err}"] += 1
                if n_dump < SHOW_RAW:
                    n_dump += 1
                    _rxn = reaction_pb2.Reaction()
                    _rxn.ParseFromString(r["_blob"])
                    raw_record_dump(_rxn, r, n_dump, f"抽取失败：{err}")
            continue
        rs = out["reaction_smarts"]
        a, b = rs.split(">>", 1)
        fwd = b + ">>" + a            # ★ rdchiral 给逆方向，正向要交换 ★
        tmpl_support[fwd] += 1
        tmpl_raw.setdefault(fwd, r["r1"])
        if COND_OUT:
            tmpl_src.setdefault(fwd, []).append(r)     # 记来源记录（support 累加同一处）
            if n_dump < SHOW_RAW:
                n_dump += 1
                _rxn = reaction_pb2.Reaction()
                _rxn.ParseFromString(r["_blob"])
                raw_record_dump(_rxn, r, n_dump, f"抽取成功 -> {_clip(fwd, 90)}")
        n_ok += 1
        if n_try % 500 == 0:
            print(f"    抽模板 {n_try}  成功 {n_ok}  去重 {len(tmpl_support)}  "
                  f"跳过过大 {n_too_big}  {time.time()-t0:.0f}s", flush=True)
    print(f"\n从 {n_try} 条漏项抽出 {n_ok} 次模板，去重 {len(tmpl_support)} 个"
          f"（过大跳过 {n_too_big}，预算跳过 {n_budget}）", flush=True)
    if COND_OUT:
        print(f"  抽取失败分类（本次新增统计，旧计数器未改）："
              f"{dict(cond_fail.most_common())}", flush=True)

    # ---------------- 4. 编译模板（raw / gen × 支持数阈值） ----------------
    # ★ 先把挖到的模板落盘（可复用件；不落盘这轮实验就只剩数字）★
    n_written = 0
    # ★ 保护只读件：传了 --cond-out 时不覆盖 v1（除非显式 --overwrite-v1=1）★
    write_v1 = (not COND_OUT) or OVERWRITE_V1
    if write_v1:
        with open(OUT_TMPL_WRITE, "w", encoding="utf-8") as f:
            for t, sup in tmpl_support.most_common():
                g = generalize_smarts(t)
                f.write(json.dumps({"template": t, "generalized": g, "support": sup},
                                   ensure_ascii=False) + "\n")
                n_written += 1
        print(f"\n模板落盘 {n_written:,} 条 -> {OUT_TMPL_WRITE.name}"
              f"（支持数>=5 的 {sum(1 for v in tmpl_support.values() if v >= 5):,} 条，"
              f">=3 的 {sum(1 for v in tmpl_support.values() if v >= 3):,} 条）", flush=True)
    else:
        print(f"\n[保护只读件] 传了 --cond-out -> **不覆盖** {OUT_TMPL.name}"
              f"（要覆盖请显式 --overwrite-v1=1）；本次在内存里算出 {len(tmpl_support):,} 条模板",
              flush=True)

    # ---------------- 4b. ★ 第十七轮：v2（模板 + 来源条件分布）+ support 一致性校验 ----------------
    v2_summary = None
    tmap = None
    if COND_OUT:
        tmap, agg_info = aggregate_conditions(tmpl_support, tmpl_src)
        tmpl_gen = {t: generalize_smarts(t) for t in tmpl_support}   # ★ 只算一次
        with open(COND_OUT, "w", encoding="utf-8") as f:
            for t, sup in tmpl_support.most_common():
                e = tmap[t]
                f.write(json.dumps({"template": t,
                                    "generalized": tmpl_gen[t],
                                    "support": sup,
                                    "temp_C": e["temp_C"],
                                    "solvents": e["solvents"],
                                    "solvent_smiles": e["solvent_smiles"],
                                    "n_src": e["n_src"],
                                    "n_temp_known": e["n_temp_known"],
                                    "n_solv_known": e["n_solv_known"],
                                    "solv_source": e["solv_source"]},
                                   ensure_ascii=False) + "\n")
        print(f"\n★ v2 落盘 {len(tmap):,} 条 -> {COND_OUT}"
              f"（来源记录总数 {agg_info['n_src_total']:,}；"
              f"n_src != support 的模板 {agg_info['templates_with_bad_n_src']} 条，期望 0）",
              flush=True)

        # ---- support 一致性校验（v1 逐条对）----
        if OUT_TMPL.exists():
            chk = check_support_consistency(OUT_TMPL, tmpl_support, tmpl_gen)
            print("★ support 一致性校验（v1 逐条比对）："
                  f"v1 行数 {chk['v1_lines']}，v1 唯一 template {chk['v1_unique']}，"
                  f"本次唯一 template {chk['now_unique']}", flush=True)
            print(f"   common {chk['n_common']}  support 不一致 {chk['support_mismatch']} 条"
                  f"（期望 0）  generalized 不一致 {chk['generalized_mismatch']} 条"
                  f"（期望 0）  仅 v1 有 {chk['only_in_v1']}  仅本次有 {chk['only_in_now']}"
                  f"  v1 坏行 {chk['v1_badlines']}"
                  f"  两侧差集去掉'@'后相同={chk['diff_stereo_only']}", flush=True)
            if chk["support_mismatch"]:
                print(f"   不一致示例（template, v1, now）：{chk['mismatch_examples']}",
                      flush=True)
        else:
            chk = {"error": f"{OUT_TMPL} 不存在，跳过一致性校验"}
            print(f"★ support 一致性校验：跳过 —— {chk['error']}", flush=True)

        # ---- 引擎默认 K1 档（加载 600 -> 编译通过 590）的条件覆盖率 ----
        k1 = {"error": None}
        try:
            k1_smarts, k1_loaded, k1_fail = engine_k1_set(OUT_TMPL)
            k1 = {"loaded": k1_loaded, "compiled": len(k1_smarts),
                  "compile_fail": k1_fail, "coverage": coverage_of(k1_smarts, tmap)}
            print(f"★ 引擎默认 K1 档（走 tools/rdkit_template_lib.py 同路径）："
                  f"加载 {k1_loaded}，编译通过 {len(k1_smarts)}，编译失败 {k1_fail}"
                  f" -> 条件覆盖 {k1['coverage']}", flush=True)
        except Exception as e:
            k1 = {"error": f"{type(e).__name__}: {e}"}
            print(f"★ 引擎默认 K1 档条件覆盖：失败（{k1['error']}）", flush=True)

        # ---- 全档 + 各支持数段的可得率 ----
        all_cov = coverage_of(list(tmpl_support), tmap)
        band_cov = {}
        for lab, lo, hi in (("1", 1, 1), ("2", 2, 2), ("3-5", 3, 5),
                            ("6+", 6, 10 ** 9)):
            subset = [t for t, s in tmpl_support.items() if lo <= s <= hi]
            band_cov[lab] = coverage_of(subset, tmap)
        print(f"★ 全档 {all_cov}", flush=True)
        for lab, cv in band_cov.items():
            print(f"   支持数={lab:>3}: 总数 {cv['total']:>4}  有温度分布 "
                  f"{cv['有温度分布']:>4}（{cv['有温度分布']/max(1,cv['total']):.1%}）"
                  f"  有溶剂分布 {cv['有溶剂分布']:>4}"
                  f"（{cv['有溶剂分布']/max(1,cv['total']):.1%}）", flush=True)
        print(f"★ 条件解析计数器：avail={dict(cond_stats['avail'])}", flush=True)
        print(f"   fail={dict(cond_stats['fail'])}  temp_units="
              f"{dict(cond_stats['temp_units'])}  solv_source="
              f"{dict(cond_stats['solv_source'])}  solv_key_kind="
              f"{dict(cond_stats['solv_key_kind'])}  agents拆分={cond_stats['n_agents_split']}",
              flush=True)

        v2_summary = {
            "script": "tools/forward_template_mining.py --cond-out",
            "sample": {"n_sampled": len(rows), "seed": SEED, "usable": len(recs),
                       "train": len(tr), "test": len(te)},
            "v2_file": str(COND_OUT),
            "n_templates": len(tmap),
            "agg": agg_info,
            "support_check_vs_v1": chk,
            "extract_fail": dict(cond_fail),
            "cond_stats": {k: (dict(v) if isinstance(v, Counter) else v)
                           for k, v in cond_stats.items()},
            "coverage_all": all_cov,
            "coverage_by_support_band": band_cov,
            "engine_K1": k1,
        }

    variants = {}
    # 按支持数降序再截断：否则 MAX_TEMPLATES_PER_VARIANT 会按"遇到顺序"随便砍掉模板
    sup_sorted = sorted(tmpl_support.items(), key=lambda kv: (-kv[1], kv[0]))
    for tag, gen_flag in (("raw", False), ("gen", True)):
        for K in K_GRID:
            lib = []
            for t, sup in sup_sorted:
                if sup < K:
                    continue
                sm = generalize_smarts(t) if gen_flag else t
                if not sm:
                    continue
                try:
                    rx = rdChemReactions.ReactionFromSmarts(sm)
                except Exception:
                    continue
                if rx is None or rx.GetNumReactantTemplates() != 2:
                    continue
                lib.append((sm, rx))
                if len(lib) >= MAX_TEMPLATES_PER_VARIANT:
                    break
            variants[f"{tag}_K{K}"] = lib
            print(f"  {tag}_K{K}: {len(lib)} 个模板", flush=True)

    # ---------------- 5. test 上验收增量 ----------------
    random.seed(SEED)
    targets = te_miss if len(te_miss) <= MAX_EVAL_TARGETS else \
        random.sample(te_miss, MAX_EVAL_TARGETS)
    probe = te if len(te) <= MAX_PROBE else random.sample(te, MAX_PROBE)
    print(f"\n验收：目标 {len(targets)} 条（基准漏掉的 test 反应）；"
          f"宽松度探针 {len(probe)} 条", flush=True)

    def apply_lib(r, lib):
        m1, m2 = mc.parse_plain(r["r1"]), mc.parse_plain(r["r2"])
        if m1 is None or m2 is None:
            return set()
        got = set()
        for _sm, rx in lib:
            try:
                outs = rx.RunReactants((m1, m2))
            except Exception:
                continue
            for tup in outs:
                for pmol in tup:
                    try:
                        Chem.SanitizeMol(pmol)
                    except Exception:
                        continue
                    cp = mc.canon_plain(Chem.MolToSmiles(pmol))
                    if cp:
                        got.add(cp)
        return got

    results = {}
    miss_share = len(te_miss) / max(1, len(te))
    capped = len(targets) < len(te_miss)
    for name, lib in variants.items():
        if not lib:
            results[name] = {"templates": 0, "incremental_hits": 0,
                             "incremental_rate_on_targets": 0.0,
                             "overall_increment": 0.0, "probe_any_product": 0}
            continue
        t0 = time.time()
        inc = 0
        for r in targets:
            if r["product"] in apply_lib(r, lib):
                inc += 1
        any_prod = sum(1 for r in probe if apply_lib(r, lib))
        rate = inc / max(1, len(targets))
        # 若因算力护栏只评了一部分漏项，则按"漏项占比"外推整体增量（明确标注）
        overall = (inc / max(1, len(te))) if not capped else rate * miss_share
        results[name] = {
            "templates": len(lib),
            "targets_evaluated": len(targets),
            "incremental_hits": inc,
            "incremental_rate_on_targets": rate,
            "overall_increment": overall,
            "extrapolated": capped,
            "probe_any_product": any_prod,
            "probe_any_product_rate": any_prod / max(1, len(probe)),
            "seconds": round(time.time() - t0, 1),
        }
        print(f"  {name}: 模板 {len(lib)}  增量命中 {inc}/{len(targets)}  "
              f"（漏项命中率 {rate:.1%}）-> 整体 +{overall:.2%}"
              f"{'（外推）' if capped else ''}  "
              f"探针有产出 {any_prod}/{len(probe)}  {time.time()-t0:.0f}s", flush=True)

    payload = {
        "scratch": "ORD 自抽正向模板的增量实验（train/test 隔离）",
        "sample": {"n_sampled": len(rows), "seed": SEED, "usable": len(recs),
                   "train": len(tr), "test": len(te), "skip": dict(skip)},
        "baseline": {"train_hits": tr_hit, "train_testable": len(tr),
                     "test_hits": te_hit, "test_testable": len(te),
                     "train_coverage": base_tr, "test_coverage": base_te},
        "mining": {"missed_train_tried": n_try, "extracted": n_ok,
                   "unique_templates": len(tmpl_support),
                   "skipped_too_big": n_too_big, "skipped_by_budget": n_budget,
                   "extract_budget_s": EXTRACT_BUDGET_S,
                   "max_heavy_atoms": MAX_HEAVY_ATOMS,
                   "support_hist": dict(Counter(
                       "1" if v == 1 else "2" if v == 2 else "3-5" if v <= 5 else ">5"
                       for v in tmpl_support.values()))},
        "variants": results,
        "template_dump": {"file": OUT_TMPL.name, "n": n_written},
        "eval_caps": {"max_eval_targets": MAX_EVAL_TARGETS, "max_probe": MAX_PROBE,
                      "max_templates_per_variant": MAX_TEMPLATES_PER_VARIANT},
        "seconds": round(time.time() - t_all, 1),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n结果 -> {OUT_JSON.name}   总耗时 {time.time()-t_all:.0f}s")
    if v2_summary is not None:
        v2_summary["variant_templates"] = {k: v.get("templates", 0)
                                           for k, v in results.items()}
        v2_summary["seconds"] = round(time.time() - t_all, 1)
        OUT_SUM_V2.write_text(json.dumps(v2_summary, ensure_ascii=False, indent=1),
                              encoding="utf-8")
        print(f"★ v2 摘要 -> {OUT_SUM_V2.name}（总耗时 {v2_summary['seconds']}s）", flush=True)
    print("\n口径提醒：增量 = 在【基准漏掉的 test 反应】上复现记录产物 / 全部 test 可测反应；")
    print("          探针有产出率是宽松度指标（有产出 ≠ 错，但过高说明模板太泛）。")
    enum.close()
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
