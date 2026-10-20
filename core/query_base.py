# -*- coding: utf-8 -*-
r"""查询式交互的【共用底座】
============================

用户 2026-10-12 拍板的架构（见 reports/项目接手总结-2026-10-12-收工版.md §一）：

    一次枚举（每条产物带出处：来源底物 / 反应规则 / 第几轮）
  + 一份索引（产物规范化 SMILES -> InChIKey）
  -> 三个查询入口（A 查产物 / B 查底物 / C 结果集检索）

本模块只提供底座 + 三个入口的**纯函数实现**；命令行在 `tools/query_engine.py`。

## 三条必须写进界面的边界（用户文档 §一）
1. **查不到 ≠ 不存在** —— 只等于"当前模板库 + 当前轮数没枚举出来"。
2. **B 只给一个分子 → 只有单底物化学**；双分子反应必须同时给配体。
3. **预测出的新产物没有名字** —— 按名称查只对库里已有的分子有效。

## 纪律（AGENTS.md）
* 结论标来源：本模块打印的统计都标 `实测`/`推断`。
* 不静默失败：批量任务累计失败计数并打印（禁止 `except: continue` 式吞错）。
* 原子映射安全：本模块不碰映射号，不做 SMARTS 重写；子结构用 RDKit。
* 口径先定死：见 `build_inventory` docstring。

## 与既有代码的关系（不重复造轮子）
* 枚举：`SmartReactEngine.step()`（当前完整默认档 D：K1 双底物 + 单底物模板）。
* 条件：`conditions/templates.py` 的 10 个模板。
* 打分：`scorer.score_product`（**只作为一列信息展示，不做排序筛选** ——
  用户已明确"排序/打分停工，判断权交回用户"）。
* 名称/分子式反查：`D:\TCMAI\tcm.db` + `D:\TCMAI\coconut.db`（**只读**）。
"""
from __future__ import annotations

import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutTimeout, as_completed
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _p in (_STAGE / "core", _STAGE / "conditions", _STAGE / "rules",
           _STAGE / "libs", _STAGE / "sources"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

REPORTS = _STAGE / "reports"
TCM_DB = Path(r"D:\TCMAI\tcm.db")
COCONUT_DB = Path(r"D:\TCMAI\coconut.db")
COCONUT_IK = REPORTS / "coconut_inchikey_index.jsonl"

# 产物台账的固定文件名（build 子命令默认写这两个）
INVENTORY_CSV = REPORTS / "query_inventory_paths.csv"
INDEX_TSV = REPORTS / "query_inventory_index.tsv"
IK_CACHE = REPORTS / "query_inchikey_cache.json"
# ★ 第三十轮：指纹缓存（相似度检索用；按台账文件名派生，不写死）
FP_CACHE = REPORTS / "query_fingerprints.json"
# ★ 第三十轮：用户查询日志（证据回流；append-only）
QUERY_LOG = REPORTS / "query_log.jsonl"

FP_RADIUS = 2
FP_BITS = 2048
# 指纹格式版本：换指纹算法/参数时必须改这个字符串，否则会读到旧缓存
# （★ 实测教训：旧式 Chem.RDKFingerprint 对 552 个天然产物要 3.37 s，
#   MorganGenerator 只要 0.06 s —— 换算法后缓存必须失效）
FP_KIND = "morgan-r2-2048-gen-v1"
FP_LEGACY_KIND = "morgan-r2-2048-rdkfp-v0"

IK_TIMEOUT_S = 25.0        # 单分子 InChIKey 超时（RDKit 有过挂死实例 → 必须有超时）
IK_MAX_WORKERS = 4

# ---------------------------------------------------------------- 数据结构

PATH_FIELDS = ["product_smiles", "product_inchikey", "formula", "mw", "heavy_atoms",
               "source_smiles", "source_name", "source_herb", "source_role",
               "rule_name", "round", "activation", "activation_why",
               "is_byproduct", "score",
               # ★ 方向/平衡信号（引擎本来就有，之前没落进台账）
               "reversible", "co_products",
               # ★ 方向层（第三十一轮）：标记 + 为什么 + 判据来源
               "direction", "direction_cn", "direction_reason", "direction_source",
               # ★ D2（第三十八轮）：条件可行性模型的标记（只打标记，不删产物/不排序）
               "cond_model",
               # ★ D1：元素收支 (dC,dH,dO) —— 让 element_delta_shape 这个判据**可审计**
               "element_delta",
               # ★ D5：3 组分模板的 support（只打标记；空 = 非三组分）
               "template_support"]


@dataclass
class RunSpec:
    """一次枚举的输入规格：输入分子 + 条件 + 轮数（轮数由用户掌握）。"""
    seeds: List[Tuple[str, str, str]]          # (name, smiles, 来源标签)
    cond_name: str = "煎煮"
    rounds: int = 1
    max_pairs: int = 4000
    max_products_per_pair: int = 8
    direction: bool = True                     # ★ 方向层：给每条出处打方向标记（不删产物）
    # ★ D4（2026-10-13）：本批处理里加入的辅助试剂（SMILES 或名字）。
    #   不填 -> 保持现状（`Conditions.reagents` 为空 -> 「必需试剂判零」在生产链路上从不触发）。
    reagents: tuple = ()

    # ★ D5：3 组分模板（默认关；实测成本见 SmartReactEngine.use_triple_templates 注释）
    triples: bool = False
    # ★ D5：3 组分模板的 support 门槛（实测：2,443 条里 2,295 条 support=1）
    triples_min_support: int = 2
    # ★ 2026-10-15（第50轮）：透明化 + 开关记录（用户基础原则：任何取舍都要有开关、且留证）
    fair_pairs: bool = False                   # 对子超预算时公平截断（默认 False=旧行为不变）
    # ★ B 试点（2026-10-17）：实时路径是否接入 6 条 curated 规则（默认 False，评测不变）
    use_curated_templates: bool = False
    # ★ C 试点（2026-10-17）：实时路径是否接入 top mined 模板的 per-template 条件
    use_mined_top_conditions: bool = False
    meta_extra: dict = field(default_factory=dict)   # 原样并入 .meta.json（selection/switches 等）

    def cond(self):
        import templates as T
        c = T.get_template(self.cond_name)
        if self.reagents:
            # ★ D4：把用户给的试剂注入生产条件 —— 这是「必需试剂判零」在生产链路上
            #   第一次真正能触发的前提（第二十六轮实测：带真实试剂时判零 2.94×，误杀 3.6%）。
            from dataclasses import replace as _replace
            c = _replace(c, reagents=tuple(str(x) for x in self.reagents if str(x).strip()))
        return c

    def describe(self) -> str:
        names = [n for n, _s, _src in self.seeds]
        head = ", ".join(names[:6]) + ("…" if len(names) > 6 else "")
        return (f"输入 {len(self.seeds)} 个 [{head}] · 条件 {self.cond_name} · "
                f"轮数 {self.rounds}")


@dataclass
class EnumStats:
    """枚举过程的可复现统计（全部为**实测**）。"""
    seconds: float = 0.0
    n_seeds: int = 0
    n_paths_raw: int = 0
    n_paths_kept: int = 0
    n_products: int = 0
    n_self_products: int = 0          # 产物 == 某个输入分子（本不该算产物）
    per_round_new: List[Dict[str, Any]] = field(default_factory=list)
    ik_ok: int = 0
    ik_fail: int = 0
    ik_cached: int = 0
    ik_examples_failed: List[str] = field(default_factory=list)
    engine_notes: List[str] = field(default_factory=list)
    truncated: bool = False


@dataclass
class Inventory:
    """产物台账：每条 path 一行；索引给出每个产物分子。"""
    spec: RunSpec
    paths: List[Dict[str, Any]] = field(default_factory=list)
    stats: EnumStats = field(default_factory=EnumStats)
    built_at: str = ""
    paths_file: Optional[Path] = None
    index_file: Optional[Path] = None
    _idx: Optional["OrderedDict[str, Dict[str, Any]]"] = field(
        default=None, repr=False, compare=False)
    _smi2key: Optional[Dict[str, str]] = field(
        default=None, repr=False, compare=False)

    # ---- 索引（惰性 + 缓存：一个进程里只建一次）----
    def index(self) -> "OrderedDict[str, Dict[str, Any]]":
        """InChIKey -> 条目。InChIKey 缺失时用 `SMI:<canonical smiles>` 当键。"""
        if self._idx is not None:
            return self._idx
        role_of = _seed_roles(self.spec)
        idx: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        for r in self.paths:
            key = r.get("product_inchikey") or ("SMI:" + r["product_smiles"])
            e = idx.get(key)
            if e is None:
                e = {
                    "key": key,
                    "smiles": r["product_smiles"],
                    "inchikey": r.get("product_inchikey") or "",
                    "formula": r.get("formula", ""),
                    "mw": r.get("mw", ""),
                    "heavy_atoms": r.get("heavy_atoms", ""),
                    "score": r.get("score", ""),
                    "is_byproduct": str(r.get("is_byproduct", "")) == "True",
                    "reversible": str(r.get("reversible", "")) == "True",
                    "co_products": [x for x in str(r.get("co_products", "")).split("|")
                                    if x],
                    "direction": {},               # 方向标记 -> 条数
                    "direction_reasons": {},       # 方向标记 -> 说明
                    "activation_whys": {},         # 条件依据 -> 条数
                    "sources": OrderedDict(),      # source_smiles -> 来源信息
                }
                idx[key] = e
            dc = str(r.get("direction_cn", "") or "")
            if dc:
                e["direction"][dc] = e["direction"].get(dc, 0) + 1
                e["direction_reasons"].setdefault(dc, r.get("direction_reason", ""))
            aw = str(r.get("activation_why", "") or "")
            if aw:
                e["activation_whys"][aw] = e["activation_whys"].get(aw, 0) + 1
            src = r["source_smiles"]
            s = e["sources"].get(src)
            if s is None:
                s = {"source_smiles": src, "source_name": r.get("source_name", ""),
                     "source_herb": r.get("source_herb", ""),
                     "role": (r.get("source_role")
                              or role_of.get(src, "中间体")),
                     "paths": []}
                e["sources"][src] = s
            s["paths"].append({"rule_name": r.get("rule_name", ""),
                               "round": _as_int(r.get("round")),
                               "activation": r.get("activation", ""),
                               "activation_why": r.get("activation_why", ""),
                               "direction": r.get("direction", ""),
                               "direction_cn": r.get("direction_cn", ""),
                               "direction_reason": r.get("direction_reason", ""),
                               "direction_source": r.get("direction_source", "")})
        self._idx = idx
        return idx

    def by_smiles(self) -> Dict[str, str]:
        """canonical SMILES -> 索引键。

        ★ 必须缓存：调用方会在**循环里**查它（名称解析、子结构命中），
        每次重建就是 O(产物数) × O(查询次数) —— 台账一大就是二次方级的慢。
        """
        if self._smi2key is None:
            self._smi2key = {e["smiles"]: k for k, e in self.index().items()}
        return self._smi2key

    def __len__(self) -> int:
        return len(self.index())


def _as_int(v: Any) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _cond_model_note(rule_name: str, cond, rec: Dict[str, Any], src_rec: Dict[str, Any]) -> str:
    """★ D2（2026-10-13）：条件可行性模型的**标记**（不删产物、不排序、不筛路线）。

    只在模型覆盖的反应类上给值（`condition_model.TRAINED_CLASSES`）；条件分布外时如实标注。
    覆盖不到 / 不适用 -> 返回空串（空列 = 按类降级，不是「没算」）。

    ⚠ 口径：引擎不区分「芳基」与「胺」两个槽位，这里按出现顺序填，两个指纹位可能互换
    —— 标记里带 `[槽位未定]` 提示。
    """
    try:
        import condition_model as cm
    except Exception as ex:                      # noqa: BLE001 —— 不许静默
        return "加载失败:" + type(ex).__name__
    if str(rule_name) not in cm.TRAINED_CLASSES:
        return ""
    try:
        r = cm.score(solvent=str(getattr(cond, "solvent", "") or ""),
                     catalyst=str(getattr(cond, "catalyst", "") or ""),
                     base=str(getattr(cond, "base", "") or ""),
                     source="(query)",
                     aryl=str(src_rec.get("source_smiles") or ""),
                     amine=str(rec.get("partner_smiles") or ""),
                     reaction=str(rule_name))
    except Exception as ex:                      # noqa: BLE001
        # ★ 第四十三轮：模型不可用（如缺 joblib/sklearn）时**不崩枚举**，标记里如实写
        return "标记失败:" + type(ex).__name__
    if not r.get("applicable") or r.get("p") is None:
        return ""
    note = "p=%.3f %s [槽位未定]" % (r["p"], r["band"])
    if r.get("ood"):
        note += " [分布外:%d]" % len(r["ood"])
    return note


def _seed_roles(spec: Optional["RunSpec"]) -> Dict[str, str]:
    """输入分子 canonical SMILES -> 角色标签（"输入"）。非输入分子一律是"中间体"。"""
    out: Dict[str, str] = {}
    for _nm, sm, _src in (getattr(spec, "seeds", None) or []):
        cs = canon(sm)
        if cs:
            out.setdefault(cs, "输入")
    return out


# ---------------------------------------------------------------- 分子身份

def canon(smiles: str) -> Optional[str]:
    """规范化 SMILES；解析失败返回 None。**不抹映射号以外的任何信息**。"""
    from rdkit import Chem
    if not smiles or not str(smiles).strip():
        return None
    m = Chem.MolFromSmiles(str(smiles).strip())
    if m is None:
        return None
    return Chem.MolToSmiles(m)


def _ik_worker(smiles: str) -> Tuple[str, Optional[str], str]:
    """子进程里算 InChIKey（超时保护用）。返回 (smiles, ik, err)。"""
    try:
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")
        m = Chem.MolFromSmiles(smiles)
        if m is None:
            return (smiles, None, "SMILES 无法解析")
        ik = Chem.MolToInchiKey(m)
        if not ik:
            return (smiles, None, "InChIKey 为空")
        return (smiles, ik, "")
    except Exception as ex:                      # noqa: BLE001  —— 必须带回错误文本
        return (smiles, None, f"{type(ex).__name__}: {ex}"[:120])


def load_ik_cache(path: Path = IK_CACHE) -> Dict[str, str]:
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            return {str(k): str(v) for k, v in d.items() if v}
        except Exception as ex:                  # noqa: BLE001
            print(f"   [warn] InChIKey 缓存读不动（{type(ex).__name__}: {ex}），忽略")
    return {}


def save_ik_cache(cache: Dict[str, str], path: Path = IK_CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def inchikeys_of(smiles_list: Sequence[str],
                 cache: Optional[Dict[str, str]] = None,
                 workers: int = IK_MAX_WORKERS,
                 timeout_s: float = IK_TIMEOUT_S,
                 ) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """批量算 InChIKey。

    ★ 为什么要子进程 + 超时：RDKit 的 InChI 在个别分子上会**挂死**
      （项目里已有实例：`diag_inchi_hang.py`，全量跑卡在 282,000/297,885）。
      挂死的进程杀掉、记一次失败，**绝不静默丢弃**。
    """
    cache = cache if cache is not None else {}
    uniq = sorted({s for s in smiles_list if s})
    todo = [s for s in uniq if s not in cache]
    stat: Dict[str, Any] = {"total": len(uniq), "cached": len(uniq) - len(todo),
                            "ok": 0, "fail": 0, "examples_failed": []}
    for s in uniq:
        if s in cache:
            stat["ok"] += 1

    if todo:
        t0 = time.time()
        # ★★ 真保护：不能用"顺序 fut.result(timeout=)" ★★
        #   旧写法的三个漏洞（2026-10-13 修）：
        #     ① 顺序取 -> 排在前面的分子挂死，后面全部干等（timeout 形同虚设）；
        #     ② shutdown(wait=False, cancel_futures=True) **杀不掉正在跑的 worker**；
        #     ③ 超时后原样返回，管道里静默少一批 InChIKey。
        #   现在：整批一次提交 + as_completed 收结果 + **两层截止**（每个分子 timeout_s、
        #   整批时间预算），超时/放弃的分子**逐个记名打印**，并计入 stat['timeout']。
        budget = max(60.0, 0.5 * len(todo))
        stat.update({"timeout": 0, "abandoned": 0, "budget_s": round(budget, 1),
                     "timed_out_examples": []})
        pool = None
        try:
            pool = ProcessPoolExecutor(max_workers=max(1, workers))
        except Exception as err:                 # noqa: BLE001  —— 退化成单进程串行
            print(f"   [warn] 进程池起不来（{type(err).__name__}: {err}），改串行")
        if pool is None:
            for s in todo:
                if time.time() - t0 > budget:
                    stat["abandoned"] += len(todo) - (stat["ok"] + stat["fail"]
                                                      + stat["cached"])
                    print(f"   [warn] 串行模式超整批预算 {budget:.0f}s，放弃剩余分子")
                    break
                _s, ik, e = _ik_worker(s)
                if ik:
                    cache[s] = ik
                    stat["ok"] += 1
                else:
                    stat["fail"] += 1
                    if len(stat["examples_failed"]) < 5:
                        stat["examples_failed"].append(f"{_s[:40]} <- {e}")
        else:
            ordered = list(todo)
            fut2s = {}
            for s in ordered:
                fut2s[pool.submit(_ik_worker, s)] = s
            state = {"deadline_hit": False, "killed": False}
            try:
                for fut in as_completed(fut2s, timeout=budget):
                    s = fut2s[fut]
                    try:
                        _s, ik, e = fut.result(timeout=timeout_s)
                    except FutTimeout:
                        ik, e = None, f"单分子超时 >{timeout_s:.0f}s"
                    except Exception as exr:     # noqa: BLE001
                        ik, e = None, f"{type(exr).__name__}: {exr}"[:120]
                    if ik:
                        cache[s] = ik
                        stat["ok"] += 1
                    else:
                        stat["fail"] += 1
                        stat["timeout"] += 1
                        if len(stat["timed_out_examples"]) < 5:
                            stat["timed_out_examples"].append(f"{s[:44]} <- {e}")
                    if time.time() - t0 > budget:
                        state["deadline_hit"] = True
                        break
            except FutTimeout:
                state["deadline_hit"] = True
            if state["deadline_hit"]:
                # 还有 worker 在跑 -> 杀进程（shutdown 杀不掉），再记账
                try:
                    for proc in list(getattr(pool, "_processes", {}).values()):
                        proc.kill()
                    state["killed"] = True
                except Exception as exk:         # noqa: BLE001
                    print(f"   [warn] 杀超时 worker 失败：{type(exk).__name__}: {exk}")
            done = stat["ok"] + stat["fail"]
            left = len(todo) - (done - stat["cached"])
            stat["abandoned"] = max(0, left)
            if state["deadline_hit"] or stat["abandoned"]:
                print(f"   [warn] InChIKey 整批预算 {budget:.0f}s 用尽："
                      f"完成 {done - stat['cached']}/{len(todo)}，"
                      f"放弃 {stat['abandoned']} 个（kill={state['killed']}）")
            if stat["timed_out_examples"]:
                print(f"   [warn] 失败/超时分子样例（不静默）：{stat['timed_out_examples']}")
            pool.shutdown(wait=False, cancel_futures=True)
        stat["seconds"] = round(time.time() - t0, 1)
    return cache, stat


# ---------------------------------------------------------------- 枚举（底座）

def build_inventory(spec: RunSpec,
                    score: bool = True,
                    ik_workers: int = IK_MAX_WORKERS,
                    use_cache: bool = True,
                    ) -> Inventory:
    """★ 一次枚举 ★ —— 底座的核心。

    ## 口径（先定死，再跑；来源：用户文档 §三 + demo 同款默认引擎）
    * 引擎 = `SmartReactEngine()` 默认构造 = 配置 **D**（K1 双底物模板 + 单底物模板），
      与 `tools/predict_demo.py` 完全一致（能力基线 35.9%）。
    * 每轮的 `exclude_smiles` = **之前所有轮已产出的分子 + 输入分子**（与 `core/cascade.py` 同款），
      所以 `round` 列 = **该分子最早出现的轮次**（这正是入口 A 要的"第几轮冒出来"）。
    * 逐轮"新增 < min_new 就停"**不采用**：轮数由用户掌握，跑到他给的轮数为止。
    * 产物 == 输入分子（自身被"反应"回自己）**不计入产物**，只统计条数（`n_self_products`）——
      过滤前是引擎原始输出，过滤后才是台账。
    * `score` **只作为一列信息**，不排序、不筛选（用户已明确打分停工）。

    ## 每轮怎么调引擎（与配置 D 的评测口径一致）
    轮 1：`step(seeds, cond, round_no=1)` —— 一次调用，同时跑双底物 + 单底物模板
    （和 `measure_ord_capability.py` 的 D 档一致）。
    轮 2..n：`step(frontier_全部, cond, round_no=r)`。
    ⚠ 只对"参与过底物对"的分子套用单底物模板；因此前沿 **超过 max_pairs 的尾巴分子
    不会被单底物模板覆盖**（本轮若发生截断，`truncated` 会标 True）。
    """
    from engine import Compound, get_mol
    from scorer import score_product
    from smartreact_engine import SmartReactEngine

    t_all = time.time()
    inv = Inventory(spec=spec, built_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    st = inv.stats
    st.n_seeds = len(spec.seeds)

    eng = SmartReactEngine(max_pairs=spec.max_pairs,
                           max_products_per_pair=spec.max_products_per_pair,
                           use_triple_templates=bool(getattr(spec, "triples", False)),
                           triple_min_support=int(getattr(spec, "triples_min_support", 2)),
                           fair_pairs=bool(getattr(spec, "fair_pairs", False)),
                           use_curated_templates=bool(
                               getattr(spec, "use_curated_templates", False)),
                           use_mined_top_conditions=bool(
                               getattr(spec, "use_mined_top_conditions", False)))
    st.engine_notes = [f"extra: {eng.extra_template_note}",
                       f"mono: {eng.mono_template_note}",
                       f"curated: {getattr(eng, 'curated_note', '未启用')}",
                       f"mined_top: {getattr(eng, 'mined_top_note', '未启用')}"]

    seeds = [Compound(smiles=sm, name=nm, herb=src, source="user")
             for nm, sm, src in spec.seeds]
    seed_canon = set()
    for c in seeds:
        cs = canon(c.smiles)
        if cs:
            seed_canon.add(cs)
    live = [c for c in seeds if get_mol(c.smiles) is not None]
    n_unparsable = len(seeds) - len(live)

    cond = spec.cond()
    # ★ 方向层（缺口②）：默认开。判据表在 `rules/direction_table.json`，
    #   文献侧证据在 `reports/direction_evidence.json`（没有就只报规则侧）。
    judge = None
    if getattr(spec, "direction", True):
        try:
            import direction as _dir
            judge = _dir
        except Exception as ex:                  # noqa: BLE001 —— 打印，不静默
            print(f"   [warn] 方向层加载失败，本次不打方向标记：{type(ex).__name__}: {ex}")
    n_dir: Dict[str, int] = {}

    seen: set = set(seed_canon)          # 已出现过的分子（输入 + 各轮产物）
    collected: Dict[str, Dict[str, Any]] = {}
    frontier: List[Compound] = live
    n_self = 0
    n_raw_paths = 0

    for r in range(1, max(1, spec.rounds) + 1):
        if not frontier:
            break
        t0 = time.time()
        step_products = eng.step(frontier, cond, round_no=r, exclude_smiles=set(seen))
        st.truncated = st.truncated or bool(eng.stats.get("pairs_truncated"))
        new_this_round: List[str] = []
        for p in step_products:
            if p.smiles in seen:
                continue                      # 引擎已按 exclude/seen 去过重，这里是冗余保险
            n_raw_paths += 1
            if p.smiles in seed_canon:
                n_self += 1
                continue
            seen.add(p.smiles)
            new_this_round.append(p.smiles)
            sc = ""
            if score:
                rule = eng._rule_by_id.get(p.rule_id, {})
                try:
                    base, _detail = score_product(p.smiles, rule, p.activation,
                                                  source_smiles=p.source_smiles)
                    sc = round(base, 4)
                except Exception as ex:          # noqa: BLE001  —— 累计，不静默
                    eng.gate_stats["score_异常"] = eng.gate_stats.get("score_异常", 0) + 1
                    sc = ""
            rec = collected.get(p.smiles)
            if rec is None:
                rec = {
                    "product_smiles": p.smiles,
                    "product_inchikey": "",
                    "formula": p.formula,
                    "mw": p.mw,
                    "heavy_atoms": p.heavy_atoms,
                    "score": sc,
                    "is_byproduct": bool(p.is_byproduct),
                    # ★ 方向/平衡信号（引擎本就有；之前只在内存里，没进台账）
                    "reversible": bool(p.reversible),
                    "co_products": [x for x in (p.co_products or ()) if x != p.smiles][:4],
                    # ★ D2：同批另一个底物（条件模型要两个指纹位）
                    "partner_smiles": str(getattr(p, "partner_smiles", "") or ""),
                    "element_delta": tuple(getattr(p, "element_delta", ()) or ()),
                    "template_support": int(getattr(p, "template_support", 0) or 0),
                    "sources": OrderedDict(),
                }
                collected[p.smiles] = rec
            else:
                rec["reversible"] = rec["reversible"] or bool(p.reversible)
                for x in (p.co_products or ()):
                    if x != p.smiles and x not in rec["co_products"] and len(rec["co_products"]) < 4:
                        rec["co_products"].append(x)
            src = rec["sources"].get(p.source_smiles)
            if src is None:
                rec["sources"][p.source_smiles] = {
                    "source_smiles": p.source_smiles,
                    "source_name": p.source_name,
                    "source_herb": p.source_herb,
                    "paths": {},
                }
                src = rec["sources"][p.source_smiles]
            key = (str(p.rule_name), int(p.round))
            ent = src["paths"].get(key)
            if ent is None:
                ent = {"rule_name": key[0], "round": key[1],
                       "activation": float(p.activation),
                       "activation_why": str(getattr(p, "activation_why", "") or ""),
                       "direction": "", "direction_cn": "", "direction_reason": "",
                       "direction_source": ""}
                if judge is not None:
                    j = judge.judge(str(p.rule_name), cond,
                                    co_products=getattr(p, "co_products", ()),
                                    element_delta=getattr(p, "element_delta", ()))
                    ent.update({"direction": j["label"], "direction_cn": j["label_cn"],
                                "direction_reason": j["reason"],
                                "direction_source": j["source"]})
                    n_dir[j["label_cn"]] = n_dir.get(j["label_cn"], 0) + 1
                src["paths"][key] = ent
            else:
                ent["activation"] = max(float(ent["activation"]), float(p.activation))

        st.per_round_new.append({"round": r, "new": len(new_this_round),
                                 "kept_raw": len(step_products),
                                 "seconds": round(time.time() - t0, 2)})
        if not new_this_round:
            break
        # ★ 下一轮前沿 = 本轮新增分子（与 core/cascade.py 同款：输入分子只参与第 1 轮）。
        #   注意：本底座**不做传播筛选**（不按分数/可逆性剔除，也不采样截断）——
        #   轮数由用户掌握，用户要几轮就跑几轮。
        frontier = [Compound(smiles=sm, name="", herb="", source="cascade")
                    for sm in new_this_round]

    st.n_self_products = n_self
    st.n_products = len(collected)
    st.ik_cached = 0

    # ---- InChIKey 索引（★ 一份索引）----
    cache = load_ik_cache() if use_cache else {}
    cache, ikstat = inchikeys_of(list(collected.keys()), cache, workers=ik_workers)
    st.ik_ok = ikstat["ok"]
    st.ik_fail = ikstat["fail"]
    st.ik_cached = ikstat["cached"]
    st.ik_examples_failed = ikstat["examples_failed"]
    if use_cache:
        save_ik_cache(cache)

    # ---- 摊平成 path 行（每条带出处 + 方向标记）----
    for sm, rec in collected.items():
        rec["product_inchikey"] = cache.get(sm, "")
        for s in rec["sources"].values():
            for ent in sorted(s["paths"].values(), key=lambda x: (x["round"], x["rule_name"])):
                inv.paths.append({
                    "product_smiles": sm,
                    "product_inchikey": rec["product_inchikey"],
                    "formula": rec["formula"],
                    "mw": rec["mw"],
                    "heavy_atoms": rec["heavy_atoms"],
                    "source_smiles": s["source_smiles"],
                    "source_name": s["source_name"],
                    "source_herb": s["source_herb"],
                    "source_role": "输入" if s["source_smiles"] in seed_canon else "中间体",
                    "rule_name": ent["rule_name"],
                    "round": ent["round"],
                    "activation": ent["activation"],
                    "activation_why": ent.get("activation_why", ""),
                    "is_byproduct": rec["is_byproduct"],
                    "score": rec["score"],
                    "reversible": rec["reversible"],
                    "co_products": "|".join(rec["co_products"]),
                    "direction": ent["direction"],
                    "direction_cn": ent["direction_cn"],
                    "direction_reason": ent["direction_reason"],
                    "direction_source": ent["direction_source"],
                    "cond_model": _cond_model_note(ent["rule_name"], cond, rec, s),
                    "element_delta": "|".join(str(x) for x in (rec.get("element_delta") or ())),
                    "template_support": int(rec.get("template_support", 0) or 0),
                })
    st.n_paths_raw = n_raw_paths
    st.n_paths_kept = len(inv.paths)
    st.seconds = round(time.time() - t_all, 2)
    inv.notes = {                          # 供界面如实转述的边界说明
        "unparsable_seeds": n_unparsable,
        "pairs_truncated": st.truncated,
        "direction_summary": n_dir,
        "direction_enabled": judge is not None,
    }
    return inv


# ---------------------------------------------------------------- 落盘 / 读回

def dump_inventory(inv: Inventory,
                   paths_file: Path = INVENTORY_CSV,
                   index_file: Path = INDEX_TSV) -> Tuple[Path, Path]:
    """写两个文件：
    * `<paths_file>`：CSV，**一行一条出处路径**（可复查、可用 Excel 打开）
    * `<index_file>`：TSV，**一行一个产物分子**（索引：SMILES / InChIKey / 出处条数）
    """
    paths_file.parent.mkdir(parents=True, exist_ok=True)
    with open(paths_file, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PATH_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in inv.paths:
            w.writerow(r)

    idx = inv.index()
    with open(index_file, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["product_inchikey", "product_smiles", "formula", "mw",
                    "heavy_atoms", "n_source_molecules", "n_paths",
                    "min_round", "rules", "reversible", "is_byproduct",
                    "co_products", "directions", "direction_reason"])
        for key, e in idx.items():
            rounds = [p["round"] for s in e["sources"].values() for p in s["paths"]]
            rules = sorted({p["rule_name"] for s in e["sources"].values()
                            for p in s["paths"]})
            n_paths = sum(len(s["paths"]) for s in e["sources"].values())
            dirs = "|".join(f"{k}×{v}" for k, v in sorted(e["direction"].items()))
            why = "；".join(f"{k}：{v}" for k, v in e["direction_reasons"].items())
            w.writerow([e["inchikey"], e["smiles"], e["formula"], e["mw"],
                        e["heavy_atoms"], len(e["sources"]), n_paths,
                        min(rounds) if rounds else "", "|".join(rules),
                        e["reversible"], e["is_byproduct"],
                        "|".join(e["co_products"]), dirs, why])
    inv.paths_file, inv.index_file = paths_file, index_file
    # ★ 元信息 sidecar：条件/轮数/输入分子。没有它，读回台账只能显示"(读回)"，
    #   下一个会话就看不出这份台账是在什么条件下枚举的。
    meta = {
        "built_at": inv.built_at,
        "cond_name": inv.spec.cond_name,
        "rounds": inv.spec.rounds,
        "max_pairs": inv.spec.max_pairs,
        "max_products_per_pair": inv.spec.max_products_per_pair,
        "seeds": [{"name": n, "smiles": s, "source": src} for n, s, src in inv.spec.seeds],
        "stats": {
            "n_products": inv.stats.n_products,
            "n_paths_kept": inv.stats.n_paths_kept,
            "seconds": inv.stats.seconds,
            "ik_ok": inv.stats.ik_ok,
            "ik_fail": inv.stats.ik_fail,
            "per_round_new": inv.stats.per_round_new,
            "n_self_products": inv.stats.n_self_products,
            "truncated": inv.stats.truncated,
        },
        "notes": getattr(inv, "notes", {}),
        "engine_notes": inv.stats.engine_notes,
    }
    # ★ 2026-10-15：开关/取舍记录（selection / switches / pair_coverage 等）——
    #   核心字段优先，不被覆盖（setdefault）。
    for _k, _v in (getattr(inv.spec, "meta_extra", None) or {}).items():
        meta.setdefault(_k, _v)
    meta_path = Path(str(paths_file).replace(".csv", ".meta.json"))
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return paths_file, index_file


def load_inventory(paths_file: Path = INVENTORY_CSV,
                   spec_note: str = "(从台账读回)") -> Inventory:
    """从 CSV 台账读回（不重跑枚举）。索引与出处都在这一个文件里。"""
    if not paths_file.exists():
        raise FileNotFoundError(f"台账不存在：{paths_file}（先跑 build）")
    inv = Inventory(spec=RunSpec(seeds=[], cond_name="(读回)", rounds=0))
    inv.built_at = datetime.fromtimestamp(paths_file.stat().st_mtime).strftime(
        "%Y-%m-%d %H:%M:%S")
    with open(paths_file, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            row["round"] = _as_int(row.get("round"))
            if "is_byproduct" in row:
                row["is_byproduct"] = str(row["is_byproduct"]).strip() == "True"
            inv.paths.append(row)
    inv.paths_file = paths_file
    # 同目录的 sidecar：条件/轮数/输入分子（没有也能用，只是出处信息变少）
    meta_path = Path(str(paths_file).replace(".csv", ".meta.json"))
    if meta_path.exists():
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            inv.spec = RunSpec(seeds=[(s.get("name", ""), s.get("smiles", ""),
                                       s.get("source", "")) for s in meta.get("seeds", [])],
                               cond_name=meta.get("cond_name", "(读回)"),
                               rounds=int(meta.get("rounds", 0)),
                               max_pairs=int(meta.get("max_pairs", 0)),
                               max_products_per_pair=int(
                                   meta.get("max_products_per_pair", 0)))
            inv.built_at = str(meta.get("built_at") or inv.built_at)
            st = inv.stats
            ms = meta.get("stats", {})
            st.n_products = int(ms.get("n_products", 0))
            st.n_paths_kept = int(ms.get("n_paths_kept", len(inv.paths)))
            st.seconds = float(ms.get("seconds", 0.0))
            st.ik_ok, st.ik_fail = int(ms.get("ik_ok", 0)), int(ms.get("ik_fail", 0))
            st.per_round_new = list(ms.get("per_round_new", []))
            st.n_self_products = int(ms.get("n_self_products", 0))
            st.truncated = bool(ms.get("truncated", False))
            st.engine_notes = list(meta.get("engine_notes", []))
            inv.notes = dict(meta.get("notes", {}))
            inv.notes["loaded_from"] = str(paths_file)
        except Exception as ex:                  # noqa: BLE001 —— 打印，不静默
            print(f"   [warn] sidecar {meta_path.name} 读不动（{type(ex).__name__}: {ex}），"
                  f"退回最小信息模式")
            inv.notes = {"loaded_from": str(paths_file), "note": spec_note}
    else:
        inv.notes = {"loaded_from": str(paths_file), "note": spec_note}
    return inv


# ---------------------------------------------------------------- 名称 / 库反查

_NAMES_MEM: Dict[str, List[Dict[str, str]]] = {}
_NAMES_SCAN: Optional[Dict[str, List[Dict[str, str]]]] = None


def names_of_inchikey(ik: str, limit: int = 8,
                      coco_index: Path = COCONUT_IK) -> List[Dict[str, str]]:
    """InChIKey -> 库里已有的名称（COCONUT 名称表 + tcm.db 英文名）。只读。

    一个进程内只**顺序扫一次** COCONUT 名称表（15 MB），之后走内存缓存 ——
    避免"每打印一行都扫一遍 27 万行"。
    """
    global _NAMES_SCAN
    if not ik:
        return []
    if ik in _NAMES_MEM:
        return _NAMES_MEM[ik][:limit]
    if _NAMES_SCAN is None:
        t0 = time.perf_counter()
        scan: Dict[str, List[Dict[str, str]]] = {}
        if coco_index.exists():
            with open(coco_index, encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if not parts or not parts[0]:
                        continue
                    scan.setdefault(parts[0], []).append({
                        "db": "coconut.db",
                        "name": parts[1] if len(parts) > 1 else "",
                        "extra": parts[3] if len(parts) > 3 else ""})
        _NAMES_SCAN = scan
        print(f"   （名称表 {coco_index.name} 扫入内存：{len(scan):,} 个 InChIKey，"
              f"{time.perf_counter()-t0:.1f}s）")
    out = list(_NAMES_SCAN.get(ik, []))
    out += _tcm_names_by_ik(ik, max(0, limit - len(out)))
    _NAMES_MEM[ik] = out
    return out[:limit]


_TCM_IK_NAMES: Optional[Dict[str, str]] = None


def _load_tcm_ik_names() -> Dict[str, str]:
    """tcm.db 的 `inchi_key -> name_en` 全量索引（31,646 行，只读一次）。

    ★ 实测教训（2026-10-13）：原来按 InChIKey 查名字是**每个分子一条 SQL**
      （`WHERE inchi_key = ?`），在 tcm.db 上没有索引 → **每条约 26 ms**；
      一次相似度检索有 484 个命中 → 光查名字就 12 s。
      改成一次性把整表读进内存（3 万行，约 0.2 s），之后查名字是字典命中。
    """
    global _TCM_IK_NAMES
    if _TCM_IK_NAMES is not None:
        return _TCM_IK_NAMES
    import sqlite3
    t0 = time.perf_counter()
    out: Dict[str, str] = {}
    if TCM_DB.exists():
        try:
            con = sqlite3.connect(f"file:{TCM_DB}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT inchi_key, COALESCE(name_en,'') FROM compounds "
                "WHERE inchi_key IS NOT NULL AND inchi_key != ''").fetchall()
            con.close()
            for k, nm in rows:
                if k and k not in out:
                    out[str(k)] = str(nm or "")
            print(f"   （tcm.db 名称索引读入内存：{len(out):,} 个 InChIKey，"
                  f"{time.perf_counter()-t0:.2f}s）")
        except Exception as ex:                  # noqa: BLE001 —— 打印，不静默
            print(f"   [warn] tcm.db 名称索引建不起来：{type(ex).__name__}: {ex}")
    _TCM_IK_NAMES = out
    return out


def _tcm_names_by_ik(ik: str, limit: int) -> List[Dict[str, str]]:
    if limit <= 0:
        return []
    names = _load_tcm_ik_names()
    if ik not in names or not names[ik]:
        return []
    return [{"db": "tcm.db", "name": names[ik], "extra": ""}]


_LABEL_MEM: Dict[str, str] = {}


def label_of(smiles: str, seed_labels: Optional[Dict[str, str]] = None) -> str:
    """来源分子的**可读名字**（第二十九轮后续：让出处从 SMILES 变成「甘草酸」）。

    优先级：
      1) 它是本次枚举的**输入分子** -> 直接用输入名（最可靠，来自 tcm.db / 用户输入）
      2) 库里按 InChIKey 反查到的名字（COCONUT / tcm.db）
      3) 都没有 -> 返回空串，由调用方退回显示 SMILES
    一个进程内缓存，避免同一个来源分子反复查库。
    """
    cs = canon(smiles) or smiles
    if seed_labels and cs in seed_labels:
        return seed_labels[cs]
    if cs in _LABEL_MEM:
        return _LABEL_MEM[cs]
    info = resolve_molecule(cs)
    if info["kind"] == "名称" and info.get("candidates"):
        nm = str(info["candidates"][0].get("name") or "").strip()
        _LABEL_MEM[cs] = nm
        return nm
    ik = info.get("inchikey") or ""
    if not ik:
        cache, _st = inchikeys_of([cs], load_ik_cache(), workers=1)
        ik = cache.get(cs, "")
    nm = ""
    if ik:
        got = names_of_inchikey(ik, limit=1)
        nm = str(got[0]["name"]).strip() if got else ""
    _LABEL_MEM[cs] = nm
    return nm


def seed_label_map(spec: Optional["RunSpec"]) -> Dict[str, str]:
    """输入分子的 canonical SMILES -> 名字。"""
    out: Dict[str, str] = {}
    for nm, sm, _src in (getattr(spec, "seeds", None) or []):
        cs = canon(sm)
        if cs and nm:
            out.setdefault(cs, nm)
    return out


def resolve_molecule(ref: str, limit: int = 5) -> Dict[str, Any]:
    """把用户的任意写法解析成分子。

    支持：canonical SMILES / 分子式 / InChIKey / **库里的名称**（中英文）。
    返回 {'kind': ..., 'smiles': ..., 'inchikey': ..., 'name': ..., 'candidates': [...]}
    """
    ref = (ref or "").strip()
    if not ref:
        return {"kind": "空", "smiles": None, "candidates": []}

    # ① InChIKey 形态：14-10-1 个字母，两段连字符
    parts = ref.split("-")
    if len(parts) == 3 and len(parts[0]) == 14 and len(parts[1]) == 10 and len(parts[2]) == 1:
        return {"kind": "InChIKey", "smiles": None, "inchikey": ref.upper(),
                "name": "", "candidates": []}

    # ② 分子式形态：只有元素符号和数字（且含大写字母）
    if _looks_like_formula(ref):
        return {"kind": "分子式", "smiles": None, "inchikey": "", "name": "",
                "formula": ref, "candidates": []}

    # ③ SMILES 形态：能被 RDKit 解析
    cs = canon(ref)
    if cs:
        return {"kind": "SMILES", "smiles": cs, "inchikey": "", "name": "",
                "candidates": []}

    # ④ 名称：查 tcm.db / coconut.db
    cands = search_db_by_name(ref, limit=limit)
    if cands:
        return {"kind": "名称", "smiles": None, "inchikey": "", "name": ref,
                "candidates": cands}
    return {"kind": "无法识别", "smiles": None, "inchikey": "", "name": ref,
            "candidates": []}


def _looks_like_formula(s: str) -> bool:
    import re
    if not s or " " in s or "-" in s:
        return False
    if not re.fullmatch(r"(?:[A-Z][a-z]?\d*)+", s):
        return False
    return any(ch.isupper() for ch in s)


_NAME_SEARCH_MEM: Dict[str, List[Dict[str, str]]] = {}


def search_db_by_name(keyword: str, limit: int = 5) -> List[Dict[str, str]]:
    """按名称查 tcm.db（中文/英文名）+ coconut.db。**只读**，返回结构候选。"""
    import sqlite3
    ck = f"{keyword.strip().lower()}|{limit}"
    if ck in _NAME_SEARCH_MEM:
        return _NAME_SEARCH_MEM[ck]
    out: List[Dict[str, str]] = []
    if TCM_DB.exists():
        try:
            con = sqlite3.connect(f"file:{TCM_DB}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT COALESCE(name_en,'?'), COALESCE(isomeric_smiles, smiles), "
                "       COALESCE(formula,''), COALESCE(tcmsp_id,'') "
                "FROM compounds "
                "WHERE (name_en LIKE ? OR alias LIKE ?) "
                "  AND smiles IS NOT NULL AND LENGTH(smiles) > 3 LIMIT ?",
                (f"%{keyword}%", f"%{keyword}%", limit)).fetchall()
            con.close()
            for nm, smi, form, tid in rows:
                out.append({"db": "tcm.db", "name": nm, "smiles": smi or "",
                            "formula": form, "id": tid})
        except Exception as ex:                  # noqa: BLE001
            print(f"   [warn] tcm.db 按名称查失败：{type(ex).__name__}: {ex}")
    if COCONUT_DB.exists() and len(out) < limit:
        try:
            con = sqlite3.connect(f"file:{COCONUT_DB}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT COALESCE(name,'?'), COALESCE(smiles,''), COALESCE(cnp_id,'') "
                "FROM compounds WHERE name LIKE ? "
                "  AND smiles IS NOT NULL AND smiles <> '' LIMIT ?",
                (f"%{keyword}%", limit - len(out))).fetchall()
            con.close()
            for nm, smi, cid in rows:
                out.append({"db": "coconut.db", "name": nm, "smiles": smi,
                            "formula": "", "id": cid})
        except Exception as ex:                  # noqa: BLE001
            print(f"   [warn] coconut.db 按名称查失败：{type(ex).__name__}: {ex}")
    _NAME_SEARCH_MEM[ck] = out
    return out


# ---------------------------------------------------------------- 入口 A：查产物

def query_product(inv: Inventory, ref: str, max_sources: int = 20) -> Dict[str, Any]:
    """★ 入口 A ★ 用户给一个分子 -> 答「在不在产物集里 / 由哪条路径生成」。

    边界①：**查不到 ≠ 不存在**。
    """
    res: Dict[str, Any] = {"query": ref, "found": False, "hits": [],
                           "notes": ["查不到 ≠ 不存在：只等于「当前模板库 + 当前轮数」没枚举出来"]}
    ident = resolve_molecule(ref)
    res["resolved"] = ident
    idx = inv.index()
    seed_labels = seed_label_map(getattr(inv, "spec", None))
    keys: List[str] = []
    if ident["kind"] == "InChIKey":
        keys = [ident["inchikey"]] if ident["inchikey"] in idx else []
    elif ident["kind"] == "分子式":
        keys = [k for k, e in idx.items() if e["formula"] == ident["formula"]]
    elif ident.get("smiles"):
        cs = ident["smiles"]
        k = inv.by_smiles().get(cs)
        if k:
            keys = [k]
        else:                                    # InChIKey 层面回退（立体/互变写法不同）
            cache, _st = inchikeys_of([cs], load_ik_cache())
            ik = cache.get(cs)
            if ik and ik in idx:
                keys = [ik]
                res["notes"].append("SMILES 不是同一规范化写法，但 InChIKey 一致 -> 命中")
    elif ident["kind"] == "名称" and ident.get("candidates"):
        for c in ident["candidates"][:5]:
            cs = canon(c.get("smiles", ""))
            if not cs:
                continue
            k = inv.by_smiles().get(cs)
            if k and k not in keys:
                keys.append(k)
    for k in keys[:5]:
        e = idx[k]
        srcs = []
        for s in list(e["sources"].values())[:max_sources]:
            srcs.append({
                "source_smiles": s["source_smiles"],
                "source_name": s["source_name"],
                "source_herb": s["source_herb"],
                "role": s.get("role", ""),
                "source_label": (label_of(s["source_smiles"], seed_labels)
                                 if seed_labels else ""),
                "paths": sorted(s["paths"], key=lambda x: (x["round"], x["rule_name"])),
            })
        names = names_of_inchikey(e["inchikey"]) if e["inchikey"] else []
        rounds = [p["round"] for s in e["sources"].values() for p in s["paths"]]
        rules = sorted({p["rule_name"] for s in e["sources"].values()
                        for p in s["paths"]})
        res["hits"].append({
            "smiles": e["smiles"], "inchikey": e["inchikey"], "formula": e["formula"],
            "mw": e["mw"], "heavy_atoms": e["heavy_atoms"], "score": e["score"],
            "is_byproduct": e["is_byproduct"], "reversible": e["reversible"],
            "co_products": e["co_products"],
            "directions": dict(e.get("direction") or {}),
            "direction_reasons": dict(e.get("direction_reasons") or {}),
            "n_sources": len(e["sources"]),
            "n_paths": sum(len(s["paths"]) for s in e["sources"].values()),
            "min_round": min(rounds) if rounds else None,
            "rules": rules, "sources": srcs,
            "known_names": names,
        })
    res["found"] = bool(res["hits"])
    if not res["found"] and ident["kind"] == "无法识别":
        res["notes"].append("输入既不是合法 SMILES/分子式/InChIKey，也没在库里查到该名称")
    return res


# ---------------------------------------------------------------- 入口 B：查底物

def query_substrate(smiles: str,
                    cond_name: str = "煎煮",
                    max_products: int = 50,
                    score: bool = True,
                    engine=None) -> Dict[str, Any]:
    """★ 入口 B ★ 用户给一个分子当**底物** -> 只跑它 -> 输出产物。

    边界②：**一个分子进去只有单底物化学**；要双分子反应必须同时给配体。
    """
    from engine import Compound
    from scorer import score_product
    from smartreact_engine import SmartReactEngine

    res: Dict[str, Any] = {"query": smiles, "notes": [
        "一个分子进去 = 只有【单底物】化学（mined_mono 的单反应物模板）；"
        "双分子反应必须同时给配体（见 --with）",
        "产物是候选清单，不是「会不会发生」的判据",
    ]}
    cs = canon(smiles)
    if cs is None:
        res["error"] = "SMILES 无法解析"
        res["products"] = []
        return res
    eng = engine or SmartReactEngine()
    import templates as T
    cond = T.get_template(cond_name)
    t0 = time.time()
    prods = eng.step([Compound(smiles=cs, name="(查询底物)", herb="(用户输入)")],
                     cond, round_no=1)
    dt = time.time() - t0
    rows = []
    for p in prods:
        sc = ""
        if score:
            rule = eng._rule_by_id.get(p.rule_id, {})
            try:
                base, _d = score_product(p.smiles, rule, p.activation,
                                         source_smiles=p.source_smiles)
                sc = round(base, 4)
            except Exception:                    # noqa: BLE001
                sc = ""
        rows.append({"smiles": p.smiles, "formula": p.formula, "mw": p.mw,
                     "heavy_atoms": p.heavy_atoms, "rule_name": p.rule_name,
                     "activation": p.activation, "score": sc,
                     "is_byproduct": p.is_byproduct, "reversible": p.reversible,
                     "co_products": [x for x in (p.co_products or ())
                                     if x != p.smiles][:4]})
    rows.sort(key=lambda r: (-(r["score"] if isinstance(r["score"], float) else 0.0),
                             r["rule_name"]))
    res.update({
        "input_canonical": cs, "cond": cond.describe(), "seconds": round(dt, 2),
        "n_products": len(rows), "n_rules": len({r["rule_name"] for r in rows}),
        "products": rows[:max_products], "n_shown": min(len(rows), max_products),
        "engine_notes": [f"extra: {eng.extra_template_note}",
                         f"mono: {eng.mono_template_note}"],
    })
    return res


def query_substrate_pair(smiles_a: str, smiles_b: str,
                         cond_name: str = "煎煮",
                         max_products: int = 50) -> Dict[str, Any]:
    """B 的双分子版：给两个分子当底物（回答"要双分子就得给配体"）。"""
    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    res: Dict[str, Any] = {"query": [smiles_a, smiles_b], "notes": []}
    ca, cb = canon(smiles_a), canon(smiles_b)
    if ca is None or cb is None:
        res["error"] = "其中一个 SMILES 无法解析"
        res["products"] = []
        return res
    eng = SmartReactEngine()
    cond = T.get_template(cond_name)
    t0 = time.time()
    prods = eng.step([Compound(smiles=ca, name="A", herb="(用户输入)"),
                      Compound(smiles=cb, name="B", herb="(用户输入)")], cond, round_no=1)
    dt = time.time() - t0
    rows = [{"smiles": p.smiles, "formula": p.formula, "rule_name": p.rule_name,
             "activation": p.activation, "is_byproduct": p.is_byproduct,
             "source_smiles": p.source_smiles} for p in prods]
    res.update({"cond": cond.describe(), "seconds": round(dt, 2),
                "n_products": len(rows), "products": rows[:max_products],
                "n_shown": min(len(rows), max_products)})
    return res


# ---------------------------------------------------------------- 入口 C：结果集检索

def query_inventory(inv: Inventory,
                    name: Optional[str] = None,
                    formula: Optional[str] = None,
                    smiles: Optional[str] = None,
                    inchikey: Optional[str] = None,
                    substructure: Optional[str] = None,
                    max_round: Optional[int] = None,
                    include_byproducts: bool = True,
                    limit: int = 200) -> Dict[str, Any]:
    """★ 入口 C ★ 结果集检索：名称 / 分子式 / SMILES / 子结构 -> 过滤后的清单（**不高亮、不排序**）。

    边界③：**预测出的新产物没有名字** -> 按名称查只对库里已有的分子有效。
    """
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    res: Dict[str, Any] = {"filters": {"name": name, "formula": formula,
                                       "smiles": smiles, "inchikey": inchikey,
                                       "substructure": substructure,
                                       "max_round": max_round,
                                       "include_byproducts": include_byproducts},
                           "hits": [], "n_hits": 0,
                           "notes": ["产物按分子去重；「不高亮、不排序」= 判断权在用户",
                                     "名称为空 = 该分子不在 tcm.db/COCONUT 里（预测出的新结构本来就没名字）"]}
    idx = inv.index()
    keys: Optional[set] = None
    seed_labels = seed_label_map(getattr(inv, "spec", None))

    def _narrow(new: Optional[Iterable[str]]) -> None:
        nonlocal keys
        s = set(new or [])
        keys = s if keys is None else (keys & s)

    if inchikey:
        _narrow([inchikey.upper()])
    if smiles:
        cs = canon(smiles)
        if cs is None:
            res["error"] = f"SMILES 无法解析：{smiles}"
            return res
        k = inv.by_smiles().get(cs)
        _narrow([k] if k else [])
    if formula:
        f = formula.replace(" ", "")
        _narrow([k for k, e in idx.items() if e["formula"] == f])
    if name:
        cands = search_db_by_name(name, limit=25)
        res["name_candidates"] = cands
        hit_keys = set()
        for c in cands:
            cs = canon(c.get("smiles", ""))
            if cs and cs in inv.by_smiles():
                hit_keys.add(inv.by_smiles()[cs])
        _narrow(hit_keys)
    if substructure:
        patt = Chem.MolFromSmarts(substructure)
        how = "SMARTS"
        if patt is None:
            patt = Chem.MolFromSmiles(substructure)
            how = "SMILES 当子结构"
        if patt is None:
            res["error"] = f"子结构既不是 SMARTS 也不是 SMILES：{substructure}"
            return res
        res["substructure_parsed_as"] = how
        hits = set()
        for k, e in idx.items():
            m = Chem.MolFromSmiles(e["smiles"])
            if m is not None and m.HasSubstructMatch(patt):
                hits.add(k)
        _narrow(hits)

    rows = []
    for k, e in idx.items():
        if keys is not None and k not in keys:
            continue
        if not include_byproducts and e["is_byproduct"]:
            continue
        rounds = [p["round"] for s in e["sources"].values() for p in s["paths"]]
        mn = min(rounds) if rounds else None
        if max_round is not None and (mn is None or mn > max_round):
            continue
        rows.append({
            "smiles": e["smiles"], "inchikey": e["inchikey"],
            "formula": e["formula"], "mw": e["mw"],
            "heavy_atoms": e["heavy_atoms"], "score": e["score"],
            "min_round": mn, "n_sources": len(e["sources"]),
            "reversible": e["reversible"], "is_byproduct": e["is_byproduct"],
            "co_products": e["co_products"],
            "directions": dict(e.get("direction") or {}),
            "rules": sorted({p["rule_name"] for s in e["sources"].values()
                             for p in s["paths"]}),
            "sources": [label_of(s["source_smiles"], seed_labels)
                        or s["source_name"] or s["source_smiles"]
                        for s in list(e["sources"].values())[:6]],
        })
    # 未加任何过滤 = 全量清单
    rows.sort(key=lambda r: (r["min_round"] if r["min_round"] is not None else 99,
                             r["smiles"]))
    res["n_hits"] = len(rows)
    res["hits"] = rows[:limit]
    res["n_shown"] = min(len(rows), limit)
    if keys is None and not (name or formula or smiles or inchikey or substructure):
        res["notes"].append("未加任何过滤 -> 返回全量产物清单（按首次出现轮次、SMILES 排序）")
    res["notes"].append("按名称查：只在 tcm.db / COCONUT 里能找到名字的分子可查；"
                        "新预测结构请用 SMILES / 分子式 / 子结构查")
    return res


# ---------------------------------------------------------------- 方向摘要

def direction_summary(inv: Inventory) -> Dict[str, Any]:
    """整份台账的**方向标记**统计（按产物分子去重，避免一条产物多路径重复计数）。

    返回 {'n_products': N, 'by_label': {标记: 产物数}, 'examples': [...]}
    以及**每个标记的判据来源**（哪条规则、什么理由），供界面如实转述。
    """
    idx = inv.index()
    by_label: Dict[str, int] = {}
    examples: Dict[str, Dict[str, Any]] = {}
    for e in idx.values():
        dirs = e.get("direction") or {}
        if not dirs:
            continue
        # 一个产物可能有多条路径、不同标记：按最"需要提醒"的那个算
        order = {"方向可疑": 0, "平衡": 1, "方向未定": 2, "方向明确": 3}
        top = sorted(dirs, key=lambda k: (order.get(k, 9), -dirs[k]))[0]
        by_label[top] = by_label.get(top, 0) + 1
        if top not in examples:
            reasons = e.get("direction_reasons") or {}
            examples[top] = {"smiles": e["smiles"], "formula": e["formula"],
                             "rules": sorted({p["rule_name"]
                                              for s in e["sources"].values()
                                              for p in s["paths"]}),
                             "reason": reasons.get(top, "")}
    n = max(1, len(idx))
    return {"n_products": len(idx), "by_label": by_label, "examples": examples,
            "share": {k: round(v / n, 4) for k, v in by_label.items()},
            "note": ("方向标记只是提醒，不删产物、不排序："
                     "「方向可疑」= 与当前介质相反；「平衡」= 它同时是反向底物")}


# ---------------------------------------------------------------- 入口 C+：相似度检索
# （边界①最实用的缓解）。全量扫描在当前规模（552 产物，实测 0.02 s）完全够用，
# 所以**不做**近似最近邻那套索引 —— 先把接口定下来，规模真上来了再换。

_FP_CACHE_MEM: Dict[str, Dict[str, str]] = {}


def fp_cache_path(paths_file: Optional[Path] = None) -> Path:
    """指纹缓存路径：跟随台账文件名（换台账不会互相污染）。"""
    if paths_file is None:
        return FP_CACHE
    return Path(str(paths_file).replace(".csv", ".fingerprints.json"))


def fp_of_smiles(smiles: str, radius: int = FP_RADIUS, nbits: int = FP_BITS,
                 ) -> Optional[str]:
    """Morgan 指纹 -> 十六进制串（RDKit BitVect 的 FPSText 写法）。

    ★ 用 rdFingerprintGenerator（新版 Morgan），**不用** `Chem.RDKFingerprint`：
      实测后者对平均 106 重原子的天然产物是 3.37 s/552 个，前者 0.06 s（快 50 倍），
      而且 RDKFingerprint 是路径式指纹，语义上也不是相似度检索该用的 ECFP。
    """
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    m = Chem.MolFromSmiles(smiles or "")
    if m is None:
        return None
    try:
        from rdkit.Chem import rdFingerprintGenerator
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=nbits)
        bv = gen.GetFingerprint(m)
    except Exception:                            # noqa: BLE001 —— 老版本 RDKit 兜底
        bv = Chem.RDKFingerprint(m, fpSize=nbits)
    return bv.ToBitString()


def _bv_to_store(bv) -> str:
    """位向量 -> 可 JSON 存的紧凑串（二进制位串；比十六进制短 4 倍）。"""
    try:
        return bv.ToBitString()
    except Exception:                            # noqa: BLE001
        from rdkit import DataStructs
        return DataStructs.BitVectToFPSText(bv)


def _store_to_bv(s: str):
    """存下来的串 -> ExplicitBitVect。兼容旧的十六进制格式。"""
    from rdkit import DataStructs
    if s and all(c in "01" for c in s[:32]):
        return DataStructs.CreateFromBitString(s)
    return DataStructs.CreateFromFPSText(s)


def tanimoto(fp_a, fp_b) -> float:
    """Tanimoto 相似度。fp 可以是 ExplicitBitVect，也可以是缓存里的字符串。"""
    from rdkit import DataStructs
    a = _store_to_bv(fp_a) if isinstance(fp_a, str) else fp_a
    b = _store_to_bv(fp_b) if isinstance(fp_b, str) else fp_b
    return float(DataStructs.TanimotoSimilarity(a, b))


def build_fingerprints(inv: Inventory,
                       paths_file: Optional[Path] = None,
                       force: bool = False) -> Tuple[Path, Dict[str, Any], Dict[str, Any]]:
    """给台账里每个产物分子算 Morgan 指纹并缓存（增量：已有的不重算）。

    缓存是**带版本**的字典：`{"_meta": {...}, "fp": {smiles: bits}}`。
    版本不匹配（换了指纹算法）时自动丢弃旧缓存重算 —— 否则会静默用错指纹。
    """
    out = fp_cache_path(paths_file)
    cache: Dict[str, str] = {}
    reused = 0
    reason = ""
    if not force:
        mem = _FP_CACHE_MEM.get(str(out))
        if mem:
            cache, reused = dict(mem), len(mem)
        elif out.exists():
            try:
                with open(out, encoding="utf-8") as f:
                    raw = json.load(f)
                meta = raw.get("_meta", {}) if isinstance(raw, dict) else {}
                if isinstance(raw, dict) and meta.get("kind") == FP_KIND and "fp" in raw:
                    cache = {str(k): str(v) for k, v in raw["fp"].items()}
                    reused = len(cache)
                else:
                    reason = (f"缓存版本不匹配（旧 {meta.get('kind', '无版本')} -> "
                              f"新 {FP_KIND}），重算")
            except Exception as ex:              # noqa: BLE001 —— 打印，不静默
                reason = f"指纹缓存读不动（{type(ex).__name__}: {ex}），重建"
    if reason:
        print(f"   [info] {reason}")
    todo = [e["smiles"] for e in inv.index().values() if e["smiles"] not in cache]
    t0 = time.time()
    n_fail = 0
    fails: List[str] = []
    for sm in todo:
        fp = fp_of_smiles(sm)
        if fp is None:
            n_fail += 1
            if len(fails) < 5:
                fails.append(sm[:40])
            continue
        cache[sm] = fp
    if todo:
        # ★ 只保存**当前台账里**的分子：否则换台账时旧指纹会一直堆在缓存文件里。
        keep = {e["smiles"] for e in inv.index().values()}
        cache = {k: v for k, v in cache.items() if k in keep}
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"kind": FP_KIND, "radius": FP_RADIUS,
                                 "nbits": FP_BITS,
                                 "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 "n": len(cache)},
                       "fp": cache}, f)
    _FP_CACHE_MEM[str(out)] = dict(cache)
    stat = {"n": len(cache), "computed": len(todo), "reused": reused, "fail": n_fail,
            "fail_examples": fails, "path": str(out),
            "seconds": round(time.time() - t0, 2), "kind": FP_KIND}
    return out, cache, stat


def query_similar(inv: Inventory, ref: str, threshold: float = 0.4,
                  limit: int = 30,
                  paths_file: Optional[Path] = None) -> Dict[str, Any]:
    """★ 入口 C+ ★ 相似度检索：给一个分子 -> 产物集里结构相近的分子（Tanimoto）。

    * 输入可以是 SMILES / 库里的名称（但**不需要**它在产物集里 —— 这正是它比精确查好用的地方）
    * 指纹是 Morgan(radius=2, 2048 bit) + Tanimoto；口径写在输出里
    * 不做近似最近邻索引：当前规模一次 `BulkTanimotoSimilarity` 全量比完（实测 < 0.01 s / 552 个）
    """
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    res: Dict[str, Any] = {"query": ref, "threshold": threshold, "hits": [],
                           "n_hits": 0,
                           "fps": {"type": "Morgan", "radius": FP_RADIUS,
                                   "nbits": FP_BITS, "metric": "Tanimoto"},
                           "notes": ["查不到 ≠ 不存在（边界①）；相似命中只说明"
                                     "「结构接近」，不代表它是这个反应的产物",
                                     "指纹：Morgan(radius=2, 2048 bit) · Tanimoto"]}
    ident = resolve_molecule(ref)
    res["resolved"] = ident
    q_smiles = ident.get("smiles")
    if q_smiles is None and ident.get("candidates"):
        # 名称写法：resolve_molecule 已经候选结构解析到 canonical 了，别重复解析一遍
        q_smiles = ident["candidates"][0].get("smiles")
    if not q_smiles:
        res["error"] = (f"无法把 {ref!r} 解析成结构（相似度检索需要一个结构；"
                        f"名称请用库里有的名字）")
        return res
    res["query_smiles"] = q_smiles
    q_fp = fp_of_smiles(q_smiles)
    if q_fp is None:
        res["error"] = "查询分子算不出指纹"
        return res
    _fpfile, fp_map, fpstat = build_fingerprints(inv, paths_file)
    res["fp_stats"] = fpstat
    idx = inv.index()
    seed_labels = seed_label_map(getattr(inv, "spec", None))
    # ★ 一次 BulkTanimotoSimilarity（C++ 层）算完全部相似度 ——
    #   实测 552 个的批量比较 < 0.01 s；逐次 Python 调用也测过（0.000s），
    #   真正的瓶颈是**算指纹**，所以指纹必须走缓存 + 新版 Morgan 生成器。
    from rdkit import DataStructs
    pairs = [(e["smiles"], fp_map[e["smiles"]]) for e in idx.values()
             if e["smiles"] in fp_map]
    q_bv = _store_to_bv(q_fp)
    sims = DataStructs.BulkTanimotoSimilarity(
        q_bv, [_store_to_bv(h) for _s, h in pairs]) if pairs else []
    rows = []
    for (sm, _hex), sim in zip(pairs, sims):
        if sim < threshold:
            continue
        e = idx[inv.by_smiles()[sm]]
        rounds = [p["round"] for s in e["sources"].values() for p in s["paths"]]
        rows.append({
            "tanimoto": round(float(sim), 4), "smiles": e["smiles"],
            "inchikey": e["inchikey"], "formula": e["formula"], "mw": e["mw"],
            "heavy_atoms": e["heavy_atoms"], "min_round": min(rounds) if rounds else None,
            "rules": sorted({p["rule_name"] for s in e["sources"].values()
                             for p in s["paths"]}),
            "reversible": e["reversible"], "is_byproduct": e["is_byproduct"],
            "sources": [label_of(s["source_smiles"], seed_labels)
                        or s["source_name"] or s["source_smiles"]
                        for s in list(e["sources"].values())[:4]],
            "known_names": [x["name"] for x in
                            (names_of_inchikey(e["inchikey"], limit=1)
                             if e["inchikey"] else [])],
        })
    # 相似度降序 —— 这是**检索排序**，不是"替用户挑产物"（打分仍是停工的）
    rows.sort(key=lambda r: (-r["tanimoto"], r["smiles"]))
    # ★ 去重：同一 InChIKey（含立体化学）只留相似度最高的那条。
    #   不加这一步会出现"同一分子连刷 3 行"（索引键退化成 SMI: 时才该有独立行）。
    dedup: List[Dict[str, Any]] = []
    seen_keys: set = set()
    for r in rows:
        k = r["inchikey"] or r["smiles"]
        if k in seen_keys:
            continue
        seen_keys.add(k)
        dedup.append(r)
    res["n_dup_removed"] = len(rows) - len(dedup)
    res["n_hits"] = len(dedup)
    res["hits"] = dedup[:limit]
    res["n_shown"] = min(len(dedup), limit)
    res["notes"].append("排序依据 = 与查询分子的 Tanimoto 相似度（检索排序），"
                        "不是引擎的 score 排序")
    return res


# ---------------------------------------------------------------- 聚合视图（按反应类型）


def aggregate_by_rule(inv: Inventory, limit: int = 40) -> Dict[str, Any]:
    """★ 聚合视图 ★ 按反应类型汇总：这是"通用框架"最自然的自检指标。

    口径：每条 path 一行 -> 按 rule_name 分组。
      * paths = 出处路径条数
      * products = 去重后的产物分子数（一个产物可能由多条路径生成）
      * sources = 涉及的不同来源分子数
      * min_round = 该类反应最早出现在第几轮
      * reversible = 该类里被标为可逆/介质相关的产物分子数
    """
    idx = inv.index()
    per: Dict[str, Dict[str, Any]] = {}
    for e in idx.values():
        for s in e["sources"].values():
            for p in s["paths"]:
                rule = p["rule_name"] or "(未命名规则)"
                r = per.setdefault(rule, {"rule": rule, "paths": 0, "products": 0,
                                          "sources": set(), "min_round": None,
                                          "reversible": 0, "byproducts": 0,
                                          "gate": {}})
                r["paths"] += 1
                r["sources"].add(s["source_smiles"])
                cat = classify_activation(p.get("activation_why") or "")
                r["gate"][cat] = r["gate"].get(cat, 0) + 1
                if r["min_round"] is None or p["round"] < r["min_round"]:
                    r["min_round"] = p["round"]
    # 产物数按 (规则, 产物) 去重
    seen: Dict[str, set] = {}
    for e in idx.values():
        for s in e["sources"].values():
            for p in s["paths"]:
                rule = p["rule_name"] or "(未命名规则)"
                seen.setdefault(rule, set()).add(e["smiles"])
    rows = []
    for rule, r in per.items():
        g = dict(r.get("gate") or {})
        rows.append({"rule": rule, "paths": r["paths"],
                     "products": len(seen.get(rule, ())),
                     "sources": len(r["sources"]), "min_round": r["min_round"],
                     "gate": g,
                     "gate_window": g.get(GATE_WINDOW_OK, 0),
                     "gate_penalty": g.get(GATE_PENALTY, 0),
                     "gate_no_data": g.get(GATE_PASS_NO_DATA, 0)})
    rows.sort(key=lambda x: (-x["products"], -x["paths"], x["rule"]))
    total = sum(x["paths"] for x in rows)
    for x in rows:
        x["share"] = round(x["paths"] / total, 4) if total else 0.0
    return {"n_rules": len(rows), "n_paths": total, "rows": rows[:limit],
            "n_shown": min(len(rows), limit),
            "notes": ["口径：paths = 出处路径条数；products = 去重产物分子数；"
                      "sources = 涉及的不同来源分子数"]}


# ---------------------------------------------------------------- 用户查询日志（证据回流）
#
# 为什么不违反"打分停工"：这里**不排序、不推荐**，只是把"用户查了什么、命中没有"
# 记下来 —— 项目里唯一的天然产物监督来源就是用户，先把它**可收集**。


def dump_query_log(records: Iterable[Dict[str, Any]],
                   path: Path = QUERY_LOG) -> int:
    """append-only 写一条 JSONL。返回写入条数。"""
    rows = list(records)
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def read_query_log(path: Path = QUERY_LOG, limit: int = 20000) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception as ex:              # noqa: BLE001 —— 累计并打印
                print(f"   [warn] query_log 第 {i+1} 行解析失败：{type(ex).__name__}")
    return out


def stats_of_query_log(path: Path = QUERY_LOG) -> Dict[str, Any]:
    """汇总日志：命中率、按入口分布、被查最多的分子。"""
    recs = read_query_log(path)
    by_cmd: Dict[str, Dict[str, int]] = {}
    by_kind: Dict[str, int] = {}
    top_query: Dict[str, Dict[str, Any]] = {}
    n_hit = 0
    for r in recs:
        cmd = str(r.get("cmd", "?"))
        c = by_cmd.setdefault(cmd, {"n": 0, "hit": 0})
        c["n"] += 1
        if r.get("found"):
            c["hit"] += 1
            n_hit += 1
        kind = str(r.get("resolved_kind", "?"))
        by_kind[kind] = by_kind.get(kind, 0) + 1
        key = str(r.get("query", ""))[:80]
        t = top_query.setdefault(key, {"query": key, "n": 0, "hit": 0})
        t["n"] += 1
        if r.get("found"):
            t["hit"] += 1
    tops = sorted(top_query.values(), key=lambda x: (-x["n"], x["query"]))[:15]
    return {"path": str(path), "n": len(recs), "n_hit": n_hit,
            "hit_rate": round(n_hit / len(recs), 4) if recs else 0.0,
            "by_cmd": by_cmd, "by_kind": by_kind, "top_queries": tops,
            "notes": ["这是**证据回流**，不是打分：只记录用户查了什么、命中没有",
                      "命中率低 ≠ 系统差：也反映用户查的是「当前模板库 + 轮数」"
                      "枚举不到的东西（边界①）"]}


# ---------------------------------------------------------------- 条件依据摘要

# 依据分类（★ 唯一实现；CLI 与聚合都调它）：
#   1) "无 ORD 条件数据" -> 放行（**没有任何条件依据**，自抽模板就走这条）
#   2) 降权类（试剂/溶剂/温度不匹配）
#   3) 窗口命中（1.0 且有说明）
#   4) 依据未记录（空说明）
# ★ 踩过的坑：第一版用"字符串里有没有'降权'"分类，结果把
#   "ORD 条件窗口内，无降权" 误判成降权、又把"无 ORD 条件数据，放行"误判成窗口命中
#   （后者含"无降权"字样）。分类必须显式写，不能靠关键字碰运气。
GATE_PASS_NO_DATA = "无数据放行"
GATE_PENALTY = "降权"
GATE_WINDOW_OK = "窗口命中"
GATE_UNRECORDED = "依据未记录"


def classify_activation(why: str, act=None) -> str:
    """条件依据 -> 四类之一。"""
    w = str(why or "").strip()
    if not w:
        return GATE_UNRECORDED
    if "无 ORD 条件数据" in w or "无数据" in w or "放行" in w or "按中性处理" in w:
        return GATE_PASS_NO_DATA
    if ("降权" in w) or ("不在" in w) or ("超出" in w):
        return GATE_PENALTY
    return GATE_WINDOW_OK


def activation_reason_short(why: str, limit: int = 38) -> str:
    """长理由 -> 短标签（给表格/列表用）。"""
    w = str(why or "").strip()
    if not w:
        return ""
    w = w.split("；")[0]
    return w[:limit] + ("…" if len(w) > limit else "")


def gate_summary(inv: Inventory) -> Dict[str, Any]:
    """整份台账的**条件依据**统计（按出处路径，因为依据是逐条的）。

    这是"别把 0.5/1.0 当判断"的量化版本：
    `无数据放行` 的那些产物，其"能发生"**没有任何条件证据**支撑。
    """
    import collections
    by_cat = collections.Counter()
    by_why = collections.Counter()
    for r in inv.paths:
        why = str(r.get("activation_why", "") or "")
        by_cat[classify_activation(why)] += 1
        by_why[activation_reason_short(why) or "(依据未记录)"] += 1
    n = max(1, len(inv.paths))
    return {"n_paths": len(inv.paths),
            "by_cat": dict(by_cat),
            "share": {k: round(v / n, 4) for k, v in by_cat.items()},
            "top_reasons": by_why.most_common(8),
            "note": ("activation 是**条件层的判据强度**，不是「发生概率」；"
                     "「无数据放行」= 该类反应没有 ORD 条件窗口，能发生这一条"
                     "**没有条件证据**（自抽模板都走这条）。")}


def provenance_line(inv: Optional[Inventory]) -> str:
    if inv is None:
        return "枚举来源：(未知)"
    if getattr(inv, "spec", None) and inv.spec.seeds:
        s = inv.spec
        return (f"枚举来源：{s.describe()} · 构建于 {inv.built_at} · "
                f"路径 {inv.stats.n_paths_kept} 条 / 产物 {inv.stats.n_products} 个")
    return (f"枚举来源：台账 {Path(inv.paths_file).name if inv.paths_file else '?'}"
            f"（{len(inv.paths)} 条路径 · 改动时间 {inv.built_at}）"
            f" · 条件/轮数见 build 时打印的抬头")
