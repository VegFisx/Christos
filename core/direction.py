# -*- coding: utf-8 -*-
r"""方向层：把「能生成就生成」改成「能生成 + 标出它往哪个方向走」
================================================================

对应框架缺口 ②（方向性/热力学）。设计原则（2026-10-13 与用户商定）：

  1. **不删任何产物。** 只打标记：`方向明确` / `平衡` / `方向可疑` / `方向未定`。
     判断权仍在用户手里（与"排序/打分停工"同一个决定）。
  2. **判据表单一真相在 `rules/direction_table.json`**，本模块只读它 ——
     规则可审查、可改、可关（`enabled=False`），代码里不埋化学知识。
  3. **优先复用项目里已有的知识**，不另造一套：
     * `core/smartreact_engine.py` 的 `CONDENSATION_CLASSES`（引擎既有的介质可逆性）
     * `rules/rules.json` 里 `thermo_unreliable=true` 的规则（气相 xTB 符号系统性错误的
       那 9 类"水切断键"水解，来自实测 `tools/refine_hydrolysis_boundary.py`）
  4. **xTB 只作加分项、不作判据**：半经验 ΔG 误差 ±10~20 kJ/mol，且天然产物尺寸根本算不了
     （`core/thermo.py` 的 `MAX_HEAVY_FOR_XTB=45`）。所以本层默认不调用 xTB。

数据层的第二部分（`direction_evidence.json`，由 `tools/build_direction_evidence.py`
从 ORD 分片统计）回答的是另一个问题：**"这个反应类型在文献里、在这种溶剂下出现过吗"**。
它只证明"文献有这个方向"，不证明热力学可行 —— 两者在输出里分列，不混为一谈。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _p in (_STAGE / "core", _STAGE / "conditions", _STAGE / "rules", _STAGE / "libs",
           _STAGE / "sources"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DIRECTION_TABLE = _STAGE / "rules" / "direction_table.json"
DIRECTION_EVIDENCE = _STAGE / "reports" / "direction_evidence.json"

# 输出给用户的四种标记（不要再多，多了等于又替用户做判断）
# ★ 口径唯一：`rules/direction_table.json` 每个家族都映射到这四个之一。
#   （第一版我把表里的 label 写成 irreversible/derivatization 等，与这里对不上，
#     结果 3 项自检 FAIL —— 表与代码必须用同一套枚举。）
LABELS = {
    "clear": ("方向明确", "该方向在化学上成立（含：水解侧已被实测确认的那 9 类）"),
    "equilibrium": ("平衡", "缩合-水解平衡：它同时是另一个方向的底物，别当终产物"),
    "suspect": ("方向可疑", "与当前介质相反：水相里应往水解走，而非往缩合走"),
    "undecided": ("方向未定", "判据表覆盖不到（自抽模板），或方向本身取决于试剂/条件"),
}

# ★ 2026-10-13：形状判据的**失败计数**（AGENTS.md 第六节第 4 条：批量任务禁止静默吞异常）。
#   为什么要它：如果 rdkit 缺失/坏掉，`Chem.MolFromSmiles` 对每条都会抛，判据整条**静默失效**，
#   调用方只会看到「方向未定」，看不出是判据坏了。现在会打印 + 计数。
_SHAPE_FAILS: Dict[str, Any] = {"n": 0, "last": ""}

_CACHE: Dict[str, Any] = {}


# ---------------------------------------------------------------- 表 & 证据

def load_table(path: Path = DIRECTION_TABLE) -> Dict[str, Any]:
    if "table" not in _CACHE:
        if not path.exists():
            _CACHE["table"] = {}
        else:
            with open(path, encoding="utf-8") as f:
                _CACHE["table"] = json.load(f)
    return _CACHE["table"]


def class_to_family(table: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """反应类名 -> 家族名。"""
    if "c2f" in _CACHE:
        return _CACHE["c2f"]
    t = table if table is not None else load_table()
    out: Dict[str, str] = {}
    for fam, d in (t.get("families") or {}).items():
        for c in d.get("classes", []):
            out[c] = fam
    _CACHE["c2f"] = out
    return out


def condensation_classes() -> frozenset:
    """引擎既有的缩合类集合（**唯一真相在引擎里**，这里不重复写）。"""
    if "cond" not in _CACHE:
        try:
            from smartreact_engine import CONDENSATION_CLASSES
            _CACHE["cond"] = frozenset(CONDENSATION_CLASSES)
        except Exception:                        # noqa: BLE001 —— 兜底：退回表里的家族
            fam = (load_table().get("families") or {}).get("condensation_reversible", {})
            _CACHE["cond"] = frozenset(fam.get("classes", []))
    return _CACHE["cond"]


def thermo_unreliable_rules(rules_path: Optional[Path] = None) -> Dict[str, str]:
    """`rules.json` 里 thermo_unreliable=true 的规则 -> 备注（实测：气相 xTB 对这些符号错）。"""
    if "unrel" in _CACHE:
        return _CACHE["unrel"]
    p = Path(rules_path) if rules_path else (_STAGE / "rules" / "rules.json")
    out: Dict[str, str] = {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules", data) if isinstance(data, dict) else data
        if isinstance(rules, dict):
            rules = list(rules.values())
        for r in rules or []:
            if not isinstance(r, dict):
                continue
            if r.get("thermo_unreliable"):
                rid = str(r.get("id") or r.get("name") or "")
                if rid:
                    out[rid] = str(r.get("thermo_note")
                                   or r.get("note") or "气相 xTB 对这类水解符号系统性错误")
    except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
        print(f"   [warn] 读 rules.json 的 thermo_unreliable 失败："
              f"{type(ex).__name__}: {ex}")
    _CACHE["unrel"] = out
    return out


def load_evidence(path: Path = DIRECTION_EVIDENCE) -> Dict[str, Any]:
    """ORD 侧的条件-方向证据（由 tools/build_direction_evidence.py 生成）。没有就返回空。"""
    if "evidence" not in _CACHE:
        if not path.exists():
            _CACHE["evidence"] = {}
        else:
            try:
                with open(path, encoding="utf-8") as f:
                    _CACHE["evidence"] = json.load(f)
            except Exception as ex:              # noqa: BLE001
                print(f"   [warn] direction_evidence 读不动：{type(ex).__name__}: {ex}")
                _CACHE["evidence"] = {}
    return _CACHE["evidence"]


# ---------------------------------------------------------------- 判方向

def _medium_bucket(solvent: str, table: Dict[str, Any]) -> str:
    s = str(solvent or "").strip().lower()
    med = table.get("medium_rules") or {}
    for k, d in med.items():
        for name in d.get("solvents", []):
            if name.lower() in s:
                return k
    return "unknown"


def shape_from_element_delta(element_delta) -> str:
    """★ D1（2026-10-13）**元素收支形状**：从 (dC, dH, dO) 判这一步的形状。

    口径写死（与 ORD 元素收支普查同一套形状定义）：
      * `dH <= -2 且 dO <= -1` -> `dehydration`（脱了一分子水 / 缩合形状）
      * `dH >= +2 且 dO >= +1` -> `hydrolysis`（加了一分子水 / 水解或加成形状）
      * 其它 -> 不作判断（返回空串）
    为什么它比 `shape_from_co_products` 更值得依赖：副产物是「同批其它产物」，与是否生成水无关；
    元素收支是**从反应式直接算出来的**，与模板出处无关（实测：9,770 条模板全是 2 个反应物模板，
    所以「两个底物」就是完整的反应物侧）。
    """
    try:
        dc, dh, do = (int(element_delta[0]), int(element_delta[1]), int(element_delta[2]))
    except Exception:                            # noqa: BLE001 —— 形状不对就不判，但要计数
        _SHAPE_FAILS["n"] += 1
        _SHAPE_FAILS["last"] = "element_delta 形状异常: %r" % (element_delta,)
        return ""
    del dc                                       # 只用水/氢的收支，碳数不参与判形状
    if dh <= -2 and do <= -1:
        return "dehydration"
    if dh >= 2 and do >= 1:
        return "hydrolysis"
    return ""


def shape_from_co_products(co_products) -> str:
    """★ D1（2026-10-13）可计算形状判据：从**同批副产物**判这一步的脱水/缩合形状。

    口径写死（避免误判）：只有当某个副产物的规范化 SMILES 恰好是 `O`（一分子水）时，
    才判为 `dehydration`；其它小分子（HCl/醇/胺…）一律不判（返回空串）。
    只有「生成水」这一侧能从副产物看出来；「消耗水」的水解形状需要反应物侧，属后续工作。
    """
    for x in co_products or ():
        s = str(x or "").strip()
        if not s:
            continue
        try:
            from rdkit import Chem
            m = Chem.MolFromSmiles(s)
            # ★ 注意：水只有 1 个重原子（H2O -> 重原子 O），判据用规范化 SMILES 而不是原子数
            if m is not None and Chem.MolToSmiles(m) == "O":
                return "dehydration"
        except Exception as ex:                  # noqa: BLE001 —— 解析失败不算命中，但**不许静默**
            _SHAPE_FAILS["n"] += 1
            _SHAPE_FAILS["last"] = "%s: %s (%s)" % (type(ex).__name__, ex, s[:40])
            if _SHAPE_FAILS["n"] <= 3:           # 只提示前几次，避免刷屏
                print("   [warn] 方向层形状判据：副产物解析失败 %r（%s: %s）"
                      % (s[:40], type(ex).__name__, ex))
            continue
    return ""


def _co_products_all_small(co_products, max_hac: int = 2) -> bool:
    """★ D1 收紧（2026-10-14，第四十三轮）：其余产物是否都是小分子（≤max_hac 重原子）。

    用来决定"元素收支"路径可不可信：element_delta 是「**单个产物 vs 整个反应物侧**」算的，
    多产物模板里其它产物没有被扣掉 -> 会高估"损失"、可能假装成脱水形状。
    约定：没有副产物记录（单产物情形）-> True（沿用旧行为）；解析失败 -> False（保守，且计数）。
    """
    for x in co_products or ():
        s = str(x or "").strip()
        if not s:
            continue
        try:
            from rdkit import Chem
            m = Chem.MolFromSmiles(s)
        except Exception as ex:                  # noqa: BLE001 —— 计数，不静默
            _SHAPE_FAILS["n"] += 1
            _SHAPE_FAILS["last"] = "%s: %s (%s)" % (type(ex).__name__, ex, s[:40])
            return False
        if m is None:
            _SHAPE_FAILS["n"] += 1
            _SHAPE_FAILS["last"] = "副产物解析失败: %s" % s[:40]
            return False
        if m.GetNumHeavyAtoms() > max_hac:
            return False
    return True


def judge(rule_name: str, cond=None,
          table: Optional[Dict[str, Any]] = None,
          evidence: Optional[Dict[str, Any]] = None,
          with_evidence: bool = True,
           co_products=None,
           element_delta=None) -> Dict[str, Any]:
    """给一条**规则名 + 条件**判方向标记。

    返回 dict：
      label        clear / equilibrium / suspect / undecided
      label_cn     中文标记
      reason       一句话说明（为什么这么判）
      source       判据来源：table / engine_condensation / rules_thermo_unreliable / none
      evidence     文献侧证据（可选）：该类型在该溶剂下的 ORD 记录数
    """
    t = table if table is not None else load_table()
    fam = class_to_family(t).get(str(rule_name), "")
    fdef = (t.get("families") or {}).get(fam, {}) if fam else {}
    label = str(fdef.get("label") or "undecided")
    if label not in LABELS:                      # 表里写了不在枚举内的标记 -> 归为"未定"
        label = "undecided"
    # 说明用表里的**规则原文**（中文），而不是 direction 那个短代号 —— 界面上不出现
    # "undecidable" 这种代号（第一版踩过：用户看到的是理由是代号，等于没说）
    reason = str(fdef.get("rule") or fdef.get("direction") or "")
    source = "table" if fam else "none"

    solvent = str(getattr(cond, "solvent", "") or "")
    bucket = _medium_bucket(solvent, t) if t else "unknown"

    # ★ 缩合类：用引擎既有的可逆性知识覆盖（单一真相在引擎里）
    if str(rule_name) in condensation_classes():
        source = "engine_condensation"
        if bucket == "water_like":
            label, reason = "suspect", "水相：缩合类应往水解方向走，此产物是缩合方向"
        elif bucket == "nonwater":
            label, reason = "clear", "非水介质：缩合方向成立（引擎既有行为一致）"
        else:
            label, reason = "equilibrium", "缩合-水解平衡（介质不明，按平衡看）"

    # ★ thermo_unreliable：水的【切断】型水解 —— 方向其实是明确的（水解侧）
    unrel = thermo_unreliable_rules()
    if str(rule_name) in unrel:
        label = "clear"
        reason = "水解侧方向明确（实测：气相 xTB 对这类符号系统性错误，故不采信数值，只取方向）"
        source = "rules_thermo_unreliable"

    # ★ D1（2026-10-13）：**可计算的形状判据** —— 只补表里没覆盖的具名类（不动已判定的）。
    #   表是「手写类别清单」，只覆盖缩合类那 10 类 + 9 条水解规则；这一步把判据换成
    #   「**这一步是否脱掉一分子水**」（从副产物直接算出来），于是任何能算出副产物的具名类都能拿到方向判决。
    #   ★ 2026-10-13 D1：**也覆盖自抽模板（mined_*）**。原立场是「mined 一律未定」（判据表覆盖不到），
    #   但「这一步脱没脱掉一分子水」是**从反应本身算出来的**，与模板出处无关 ——
    #   所以只要副产物里确实有水，就按形状判；判不了（无水）才留在未定。
    if label == "undecided":
        # 两条可计算判据，优先用「元素收支」（更普遍：不依赖副产物里是否列了水）
        # ★ D1 收紧（第四十三轮）：多产物模板里 element_delta 会高估"损失"（其余产物没扣掉），
        #   所以**只有当其余产物都是小分子（≤2 重原子）**时才按元素收支判形状；
        #   否则跳过它、只用「副产物是不是水」这条（那条与产物个数无关）。
        shape = ""
        src_shape = "element_delta_shape"
        if _co_products_all_small(co_products):
            shape = shape_from_element_delta(element_delta)
        if not shape:
            shape = shape_from_co_products(co_products)
            src_shape = "co_product_shape"
        if shape == "dehydration":
            source = src_shape
            if bucket == "water_like":
                label = "suspect"
                reason = ("该步脱掉一分子水（脱水/缩合形状，" + src_shape + "）；"
                          "水相里方向相反，应往水解走")
            elif bucket == "nonwater":
                label = "clear"
                reason = ("该步脱掉一分子水（脱水/缩合形状，" + src_shape + "）；"
                          "非水介质里该方向成立")
            else:
                label = "equilibrium"
                reason = "该步脱掉一分子水（脱水/缩合形状）；介质不明，按平衡看"
        elif shape == "hydrolysis":
            source = src_shape
            if bucket == "water_like":
                label = "clear"
                reason = ("该步加了一分子水（水解/加成形状，" + src_shape + "）；水相里该方向成立")
            elif bucket == "nonwater":
                label = "suspect"
                reason = ("该步加了一分子水（水解/加成形状，" + src_shape + "）；"
                          "非水介质里方向相反（缺水）")
            else:
                label = "equilibrium"
                reason = "该步加了一分子水（水解/加成形状）；介质不明，按平衡看"

    out: Dict[str, Any] = {
        "label": label,
        "label_cn": LABELS.get(label, ("?", ""))[0],
        "reason": reason,
        "source": source,
        "family": fam,
        "medium": bucket,
        "solvent": solvent,
    }

    if with_evidence and evidence is not None:
        ev = evidence_lookup(str(rule_name), solvent, evidence)
        if ev:
            out["evidence"] = ev
    return out


def evidence_lookup(rule_name: str, solvent: str,
                    evidence: Optional[Dict[str, Any]] = None,
                    family: str = "") -> Dict[str, Any]:
    """文献侧证据：该反应类型（或其家族）在 ORD 里、在该溶剂类别下的记录数。

    ★ 只回答"文献里有没有这个方向"，**不回答"热力学可行吗"**。
    """
    ev = evidence if evidence is not None else load_evidence()
    if not ev:
        return {}
    per_class = ev.get("per_class") or {}
    per_family = ev.get("per_family") or {}
    by_solv = (ev.get("by_solvent_class") or {})
    bucket = str(solvent or "").strip().lower() or "unknown"
    hit: Dict[str, Any] = {"n_ord": 0, "n_ord_same_solvent": 0,
                           "samples": ev.get("n_records", 0)}
    row = per_class.get(rule_name)
    if row:
        hit["n_ord"] = int(row.get("n", 0))
        hit["top_solvents"] = row.get("top_solvents", [])[:3]
    if family and not row:
        frow = per_family.get(family)
        if frow:
            hit["n_ord"] = int(frow.get("n", 0))
            hit["top_solvents"] = frow.get("top_solvents", [])[:3]
            hit["via"] = "family"
    sc = by_solv.get(bucket, {}) if isinstance(by_solv, dict) else {}
    if sc:
        hit["n_ord_same_solvent"] = int(sc.get(rule_name, sc.get("__all__", 0)) or 0)
    # ★ 数据自身的发表偏倚（实测）：同溶剂桶里「H↗O↗（水解/加成形状）」占多少。
    #   这是拿 ORD 判方向时必须告诉用户的前提：水解形状在文献里天然稀缺。
    pats = (ev.get("element_patterns_by_solvent_class") or {}).get(bucket) or {}
    n_tot = int(pats.get("n", 0) or 0)
    if n_tot:
        up = int(pats.get("H_up_O_up", 0) or 0)
        down = int(pats.get("H_down_O_down", 0) or 0)
        hit["ord_same_solvent_n"] = n_tot
        hit["ord_hydrolysis_shape_share"] = round(up / n_tot, 4)
        hit["ord_dehydration_shape_share"] = round(down / n_tot, 4)
    med = (ev.get("element_delta_median_by_solvent_class") or {}).get(bucket) or {}
    if med:
        hit["ord_median_dH_dO"] = [med.get("dH"), med.get("dO")]
    if not hit["n_ord"] and not hit["n_ord_same_solvent"] and not n_tot:
        return {}
    return hit


def summarize(judgements) -> Dict[str, Any]:
    """一批判定结果 -> 计数（给 build/A/C 的界面用）。"""
    n: Dict[str, int] = {}
    for j in judgements:
        k = str(j.get("label_cn") or "?")
        n[k] = n.get(k, 0) + 1
    return n


def describe_table(path: Path = DIRECTION_TABLE) -> str:
    t = load_table(path)
    lines = [f"方向判据表：{path.name}  版本 {t.get('version', '?')}"]
    for fam, d in (t.get("families") or {}).items():
        lines.append(f"  {fam:<28} -> {d.get('label'):<20} {len(d.get('classes', []))} 类")
    unrel = thermo_unreliable_rules()
    lines.append(f"  （另有 rules.json 里 thermo_unreliable={len(unrel)} 条：水解侧方向明确）")
    lines.append(f"  形状判据（D1）：失败计数 {_SHAPE_FAILS['n']}"
                 + (f"  最后一次：{_SHAPE_FAILS['last']}" if _SHAPE_FAILS["n"] else ""))
    ev = load_evidence()
    if ev:
        lines.append(f"  文献侧证据：{ev.get('source', '?')} 抽样 {ev.get('n_records', 0):,} 条")
    else:
        lines.append("  文献侧证据：尚未生成（跑 tools/build_direction_evidence.py）")
    return "\n".join(lines)
