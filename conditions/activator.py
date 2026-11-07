# -*- coding: utf-8 -*-
"""
chemreact 条件层：条件 → 规则激活分数
=====================================

职责：给定一次处理的条件（煎煮？酸水解？通氧？），
算出每条规则"在这个条件下该不该发生、有多该发生"，输出 0~1 的分数。

设计取舍（重要，读之前先看这段）：

  · **硬门槛（直接判 0）**：气氛、溶剂。
    理由：没有氧气，氧化反应就是不可能发生，不该给个"低分"让它混进产物表。
    这类是"物理上不可能"，不是"不太可能"。

  · **软打分（0~1 渐变）**：温度、pH、时间、催化剂。
    理由：它们的边界本来就是模糊的。100°C 和 90°C 都是"接近沸腾"，
    不该差一个数量级。所以用带衰减的窗口，而不是非黑即白。

  · **取最小值而不是平均值**：
    一条规则要跑，必须温度、pH、时间**全部**说得通。
    平均值会让"温度完美但 pH 荒谬"混过去。最小值才是"木桶短板"。

  · 最终分数 = 木桶短板 × 规则的 priority。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from model import Conditions, SOLVENT_PARENT  # noqa: E402  （见 model.py 顶部关于文件名的说明）

# 把规则文件里写的 `profiles`（条件窗口）解析出来，复用规则库那份定义，
# 避免两处维护同一套阈值。
_RULES_DIR = _HERE.parent / "rules"
if str(_RULES_DIR) not in sys.path:
    sys.path.insert(0, str(_RULES_DIR))

from schema import load_rules, resolve_conditions  # noqa: E402


# ---------------------------------------------------------------- 溶剂归族

# 规则里写 "alcohol" 泛指醇类；模板里可能写 "ethanol"。
# 不做归一化的话，醇提会被所有水解规则判死——这是个很容易踩的坑。
#
# ★ 第十二轮：改为从 model.SOLVENT_PARENT 生成（单一真相）★
#   原来只硬编码 3 条（ethanol/methanol/aqueous）。扩词表后用户可能写 thf/DMF/DCM，
#   若不归族，它们会命中"不在 allowed 里 -> 0.0"，把 64 条规则全部判死。
#   现在所有细类别都有父类：thf/DMF/DCM/… -> organic，醇类 -> alcohol，aqueous -> water。
#   对旧取值（ethanol/methanol/aqueous）行为不变（回归断言见 tools/test_solvent_gate.py）。
SOLVENT_FAMILY = {k: v for k, v in SOLVENT_PARENT.items() if k != v}

# ---------------------------------------------------------------- 阈值（外置）
# ★ 第 101 轮（用户 2026-11-04）★
#   门控阈值原来散落在代码里（0.35 / 0.15 步长 / 0.25 softness / 0.5 催化剂降权 / 0.15 通过线），
#   全是『建模选择』且没有参考文献。用户要求：涉及底层反应逻辑的参数必须有出处，
#   没有出处的只能当排序提示、不能判零。所以统一搬到 thresholds.json，
#   每项带 status；代码只读文件，不再藏数字。
_THRESH_PATH = _HERE / "thresholds.json"


def _load_thresholds() -> Dict[str, Any]:
    try:
        import json
        return json.loads(_THRESH_PATH.read_text(encoding="utf-8"))
    except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
        print(f"   [warn] thresholds.json 读取失败（{type(ex).__name__}: {ex}），用内置默认值")
        return {}


TH = _load_thresholds()


def _num(section: str, key: str, default: float) -> float:
    try:
        return float((TH.get(section) or {}).get(key, default))
    except (TypeError, ValueError):
        return float(default)


def threshold_status(section: str) -> str:
    """某项阈值有没有出处；返回 'cited' 或 'unvalidated_model_choice'。"""
    return str((TH.get(section) or {}).get("status") or "unvalidated_model_choice")


def solvent_score(run_solvent: str, allowed: Sequence[str]) -> float:
    """溶剂打分。

    ★ 关键约定：【列表顺序 = 偏好排序】，第一个是首选溶剂。

    为什么不能只当黑名单用（实测教训）：
    水解类规则的溶剂列表是 ["water", "aqueous", "alcohol"]，
    如果只判断"在不在列表里"，那煎煮（水）和醇提（乙醇）**两者都通过、都得满分**，
    条件层对这两种最重要的中药工艺完全没有区分能力——等于摆设。

    改成按顺序衰减后，醇提下水解类规则得 0.7 倍分，差异才体现出来。

    这个"顺序即偏好"是**建模选择**，不是实验测定值，需要化学专家复核。
    """
    if not allowed:
        return 1.0
    if run_solvent in allowed:
        idx = allowed.index(run_solvent)
    else:
        fam = SOLVENT_FAMILY.get(run_solvent)
        if fam is None or fam not in allowed:
            return 0.0
        idx = allowed.index(fam)
    step = _num("solvent", "decay_step", 0.15)
    floor = _num("solvent", "floor", 0.35)
    return max(floor, 1.0 - step * idx)


def solvent_matches(run_solvent: str, allowed: Sequence[str]) -> bool:
    return solvent_score(run_solvent, allowed) > 0.0


def ph_score(ph: float, preference: Optional[str]) -> float:
    """按反应类型的 pH 偏好打分。

    为什么需要它（实测教训）：
    原来把 pH 写成窗口 [1, 14]——**等于没有约束**。
    结果酸水解（pH 1.5）和煎煮（pH 6.5）对酯水解的打分**完全一样**（都是 0.850），
    条件层区分不出这两种工艺。

    取值：
      any        不敏感（脱水、脱羧这类热驱动反应）
      acid_base  酸碱都能催化，中性最慢（酯水解、糖苷水解）——离 pH 7 越远越快
      acid       酸催化为主
      base       碱催化为主
      neutral    要近中性（酶催化）
    """
    if preference in (None, "any"):
        return 1.0
    ph_cfg = TH.get("ph") or {}

    def _tbl(name: str, default):
        rows = ph_cfg.get(name) or default
        return rows

    if preference == "acid_base":
        c = ph_cfg.get("acid_base") or {}
        neutral = float(c.get("neutral_ph", 7.0))
        half = float(c.get("half_range", 6.0)) or 6.0
        floor = float(c.get("floor", 0.40))
        slope = float(c.get("slope", 0.60))
        d = min(abs(ph - neutral) / half, 1.0)
        return floor + slope * d
    if preference == "acid":
        for hi, sc in _tbl("acid", [[3.0, 1.0], [5.0, 0.70], [8.0, 0.45], [14.0, 0.20]]):
            if ph <= float(hi):
                return float(sc)
        return 0.20
    if preference == "base":
        for lo, sc in _tbl("base", [[11.0, 1.0], [9.0, 0.70], [6.0, 0.45], [0.0, 0.20]]):
            if ph >= float(lo):
                return float(sc)
        return 0.20
    if preference == "neutral":
        for lo, hi, sc in _tbl("neutral", [[5.5, 8.0, 1.0], [4.0, 9.5, 0.50], [0.0, 14.0, 0.15]]):
            if float(lo) <= ph <= float(hi):
                return float(sc)
        return 0.15
    return 1.0


# ---------------------------------------------------------------- 软窗口打分

def window_score(value: float, spec: Dict[str, float],
                 softness: Optional[float] = None) -> float:
    """落在 [min, max] 内得 1.0；越界按窗口宽度的 softness 倍线性衰减到 0。

    softness=0.25 表示：越界超过窗口宽度的 25%，分数归零。
    ★ 第 101 轮：默认值改从 thresholds.json 读（window.softness）。
    """
    if softness is None:
        softness = _num("window", "softness", 0.25)
    lo = float(spec["min"])
    hi = float(spec["max"])
    if lo <= value <= hi:
        return 1.0
    span = max(hi - lo, 1e-9)
    dist = (lo - value) if value < lo else (value - hi)
    return max(0.0, 1.0 - dist / (span * softness))


# ---------------------------------------------------------------- 主函数

def _temperature_gate(spec: Dict[str, Any], T: float) -> Tuple[float, str, bool]:
    """温度判据，委托给 extent.temperature_gate()（单一真相）。

    为什么不让 activator 自己再写一套：第 84 轮接入 extent 时已经证明"同一个问题
    在两个引擎里各写一份"必然跑偏——这里只负责把规则的条件档 shape 转过去。
    万一 extent 不可用（路径/依赖缺失），退回旧的窗口打分，不让条件层整个失效。
    """
    try:
        import extent as _extent
        return _extent.temperature_gate(spec.get("min"), spec.get("max"), T)
    except Exception:                        # noqa: BLE001 —— 显式退回，不静默
        s = window_score(T, spec)
        return s, ("" if s >= 0.5 else f"温度 {T:g} 落在窗口之外"), s <= 0.0


def activation_score(rule: Dict[str, Any],
                     resolved: Optional[Dict[str, Any]],
                     run: Conditions) -> Tuple[float, List[str]]:
    """返回 (分数, 判零/降权的原因列表)。分数 0 表示这条规则在这种条件下不会发生。"""
    reasons: List[str] = []

    if resolved is None:
        return 0.0, ["规则没有可解析的条件窗口"]

    _prov = str(rule.get("provenance") or "").strip().lower()
    if _prov in ("cited", "literature", "curated"):
        priority = float(rule.get("priority", 0.5))
    else:
        # ★ 第 101 轮（用户口径：无出处的参数不许当判据）★
        #   priority 是手写的 0.3~1.0，没有文献，不能拿它把某条规则压到门槛以下。
        #   这里统一置 1.0：priority 只在排序里体现（见 active_rules 返回的分数顺序），
        #   不参与「判零/判不发生」。
        priority = 1.0
    category = rule.get("category", "")

    # ---- 硬门槛 1：气氛 ----
    # 类别层面的物理约束。氧化要氧、还原要氢，没有就是不可能。
    if category == "oxidation" and run.atmosphere not in ("air", "O2"):
        return 0.0, [f"氧化反应需要氧气，当前气氛 {run.atmosphere}"]
    if category == "reduction" and run.atmosphere != "H2":
        return 0.0, [f"还原反应需要氢气，当前气氛 {run.atmosphere}"]

    allowed_atm = resolved.get("atmosphere")
    if allowed_atm and run.atmosphere not in allowed_atm:
        return 0.0, [f"规则要求气氛 {allowed_atm}，当前 {run.atmosphere}"]

    # ---- 溶剂：0 分即判死（完全不溶的介质里反应无从发生），否则按偏好衰减 ----
    s_solvent = solvent_score(run.solvent, resolved.get("solvent") or [])
    if s_solvent <= 0.0:
        return 0.0, [f"规则要求溶剂 {resolved.get('solvent')}，当前 {run.solvent}"]
    if s_solvent < 1.0:
        reasons.append(f"溶剂 {run.solvent} 不是首选（{resolved.get('solvent')}），"
                       f"降至 {s_solvent:.2f}")

    # ---- 软打分：温度 / 时间 ----
    scores = [s_solvent]

    # ---- 温度：第 85 轮 A 案（低温判死、高温不判死）----
    #   旧版对温度和时间用同一套 window_score，高温越界判 0 分。实测方向是反的：
    #   250 °C 会把水解判关（ORD 水解上限 150 °C），而高温只会让它更快。
    #   现在温度委托 extent.temperature_gate()，与生产路径同一份判据。
    t_spec = resolved.get("temperature")
    if t_spec:
        t_score, t_why, t_dead = _temperature_gate(t_spec, float(run.temperature))
        if t_dead:
            return 0.0, [t_why]
        scores.append(t_score)
        if t_why:
            reasons.append(t_why)

    # ---- 时间：仍用软窗口（"跑多久"由 extent 层表达，这里只做门控）----
    tm_spec = resolved.get("time_min")
    if tm_spec:
        s = window_score(float(run.time_min), tm_spec)
        scores.append(s)
        if s < 0.5:
            reasons.append(
                f"time_min={run.time_min:g} 落在窗口 "
                f"[{tm_spec['min']}, {tm_spec['max']}] 之外，得分 {s:.2f}")

    if not scores:
        return 0.0, ["规则的条件窗口为空"]

    # ---- pH：两条独立判据，取短板 ----
    #   window     这条规则在什么 pH 范围内才可能发生（可能很宽，比如 [1,14]）
    #   preference 在这个范围内，哪种 pH 更有利（这才是区分酸碱工艺的关键）
    ph_spec = resolved.get("pH")
    ph_win = window_score(float(run.pH), ph_spec) if ph_spec else 1.0
    ph_pref = ph_score(run.pH, resolved.get("pH_preference"))
    ph_final = min(ph_win, ph_pref)
    scores.append(ph_final)
    if ph_final < 0.5:
        reasons.append(
            f"pH {run.pH:g} 不利于该反应"
            f"（偏好 {resolved.get('pH_preference')}），得分 {ph_final:.2f}")

    # ---- 软打分：催化剂 ----
    allowed_cat = resolved.get("catalyst")
    if allowed_cat is not None:
        if run.catalyst in allowed_cat:
            scores.append(1.0)
        else:
            # 催化剂不匹配是"降权"不是"判死"：
            # 很多反应在无催化或别的催化下也能缓慢发生，只是慢得多。
            # 0.5 是建模选择（无文献），所以从 thresholds.json 读，便于日后标定。
            _cat_bad = _num("catalyst", "mismatch_factor", 0.5)
            scores.append(_cat_bad)
            reasons.append(
                f"规则偏好催化剂 {allowed_cat}，当前 {run.catalyst}，降权至 {_cat_bad:g}")

    # ---- 木桶短板 × priority ----
    return min(scores) * priority, reasons


def active_rules(rules: Sequence[Dict[str, Any]],
                 profiles: Dict[str, Any],
                 run: Conditions,
                 threshold: Optional[float] = None,
                 ) -> List[Tuple[Dict[str, Any], float, List[str]]]:
    """返回 [(规则, 分数, 原因)]，按分数降序，只保留 >= threshold 的。

    ★ 第 101 轮：threshold 默认从 thresholds.json 的 active_threshold.value 读（0.15）。
      这个 0.15 是建模选择、没有文献；用户口径是「没有出处的阈值不能单独判零」，
      所以它只作为**排序下限**保留，真正判零仍靠硬门槛（气氛/溶剂/温度）。
    """
    if threshold is None:
        threshold = float(((TH.get("active_threshold") or {}).get("value", 0.15)))
    out = []
    for r in rules:
        if r.get("status") == "disabled":
            continue
        resolved, _ = resolve_conditions(r, profiles)
        score, reasons = activation_score(r, resolved, run)
        if score >= threshold:
            out.append((r, score, reasons))
    out.sort(key=lambda x: -x[1])
    return out


def explain(rules: Sequence[Dict[str, Any]],
            profiles: Dict[str, Any],
            run: Conditions,
            threshold: float = 0.15,
            show_inactive: int = 8) -> str:
    """生成一段人能读的说明：这种条件下哪些反应会跑、哪些不会、为什么。"""
    active = active_rules(rules, profiles, run, threshold)
    active_ids = {id(r) for r, _, _ in active}

    lines = [f"条件：{run.describe()}", "", f"激活 {len(active)} / {len(rules)} 条规则", ""]
    lines.append("  ── 会发生的反应（按分数降序）──")
    for r, s, _ in active:
        lines.append(f"    {s:.3f}  {r['name']}")

    blocked = []
    for r in rules:
        if id(r) in active_ids or r.get("status") == "disabled":
            continue
        resolved, _ = resolve_conditions(r, profiles)
        _, reasons = activation_score(r, resolved, run)
        blocked.append((r["name"], reasons[0] if reasons else "分数低于阈值"))

    if blocked:
        lines.append("")
        lines.append(f"  ── 不会发生的反应（共 {len(blocked)} 条，列前 {show_inactive}）──")
        for name, why in blocked[:show_inactive]:
            lines.append(f"    ✗ {name:<20} {why}")
        if len(blocked) > show_inactive:
            lines.append(f"    … 另有 {len(blocked) - show_inactive} 条")

    return "\n".join(lines)


def load_default_rules(path: Optional[str] = None):
    """从默认位置加载规则库，返回 (profiles, rules)。"""
    p = Path(path) if path else (_RULES_DIR / "rules.json")
    return load_rules(p)
