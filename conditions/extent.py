# -*- coding: utf-8 -*-
r"""反应进程（extent）层：让 time / temperature / catalyst / pH 真正参与产物生成。

## 这是什么（一句话）

现有 `conditions/activator.py` 与 `SmartReactEngine.cond_activation()` 只回答
「这条反应在当前条件下**会不会**发生」（0/1 门控 + 降权）。它们不看时间，
pH/催化剂只在个别规则上降权，所以实测：5 min 与 1440 min 的产物**完全一样**。

本模块补的是**第二问**：「在当前条件下跑到**什么程度**」。
给出 extent ∈ [0,1]，产物层据此：
  * e < trace_below（0.05）→ 标 `none`（痕量，**不删除**）；
  * trace_below ≤ e < extent_major → 标 `minor`；
  * e ≥ extent_major（0.5）→ 标 `major`。

**判零门控已停用**（第一百一十六轮）：`kinetics.json` 的 `gates.extent_min` 从 0.10
（无文献出处）改为 0.0，所以即使有人强行打开 `extent_gate` 也不会删除任何产物；
`validation.gate_enabled` 仍是 false。痕量阈值 0.05 由已发表数据的最小可观测转化率
0.059 向下取整得到，只影响标注。

## 口径（写死，不许悄悄改）

* **参照点 = 规则自己的 condition_profile 的 default（温度、时间）**。
  在参照点上 e = 1 - 1/e ≈ 0.632。
  理由：profiles 来自 ORD 实测条件分布/人工整理，拿它当参照比另编一套
  绝对速率常数诚实；extent 因此读作「相对参照实验跑到什么程度」。
* 温度按 **Arrhenius** 放大速率：k(T)/k(T_ref) = exp(-Ea/R·(1/T − 1/T_ref))，
  Ea = 103.6 kJ/mol（第一百一十三轮实测，J Pharmacopuncture 2020，80/94/105 °C 拟合；
  另一条 80 % 甲醇数据给 68.0 kJ/mol，作为区间下界登记）。`arrhenius.enabled=false`
  时回退旧的 Q10 经验式（q10=2），仅供复现旧数字。
* 催化剂按数量级放大：acid/base 10×、metal 30×、enzyme 100×。
  只有**该反应窗口允许这类催化剂**时才放大（否则加了也没用）。
* pH 按高斯型折减：exp(-((pH - pH_opt) / span)**2)，下限 floor；optimum 取自
  规则窗口的 `pH_preference`（acid→2、base→12、acid_base→两侧取优、any→不折减）。
* 没有可用条件窗口 → e = 1.0（保守放行，与既有 no-data 策略一致）。

参数全在 `conditions/kinetics.json`，改那里就能整体调松/调紧。
**这些是建模选择，不是实测值**——文档里必须这么标注。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_HERE = Path(__file__).resolve().parent
_PARAMS_PATH = _HERE / "kinetics.json"
_CACHE: Dict[str, Any] = {}

# 催化剂可归并的写法（跑的条件里可能写 SMILES 名或中文，这里只归一化常见词）
_CAT_ALIASES = {
    "acid": {"acid", "h+", "hcl", "h2so4", "hno3", "h3po4", "tsoh", "tsOH",
             "酸", "酸性", "hydrochloric acid", "sulfuric acid", "p-toluenesulfonic acid"},
    "base": {"base", "naoh", "koh", "na2co3", "k2co3", "et3n", "tBuOK", "dbu",
             "碱", "碱性", "sodium hydroxide", "potassium hydroxide"},
    "metal": {"metal", "pd", "pt", "ni", "cu", "ru", "rh", "ir", "fe", "co",
              "pd/c", "pdc", "金属", "金属催化"},
    "enzyme": {"enzyme", "酶", "酶催化", "lipase", "amylase"},
    "photo": {"photo", "hv", "光", "光照", "光催化"},
}


def load_params(path: Optional[Path] = None) -> Dict[str, Any]:
    """载入 kinetics 参数（只读，缓存）。"""
    key = str(path or _PARAMS_PATH)
    if _CACHE.get("path") != key:
        p = Path(key)
        data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        _CACHE.clear()
        _CACHE["path"] = key
        _CACHE["params"] = data
    return _CACHE["params"]


def gating_allowed(params: Optional[Dict[str, Any]] = None) -> bool:
    """★ 第 101 轮（2026-11-04，用户口径）★ extent 能不能参与「门控/过滤」？

    用户原话：『禁止 AI 自己猜测哦，尤其是涉及底层反应逻辑的，起码得有参考文献。』

    extent 的每个参数（q10、催化剂倍数、pH 曲线、extent_min、温度容差/上限）
    目前**没有任何实测标定**，所以它们只允许「标注」：写进产物/台账给人看，
    不允许决定「有没有这个产物」。

    唯一放行的办法：在 `kinetics.json` 里补上文献标定，把
    `validation.gate_enabled` 改成 true（并在 validation.citations 里写 DOI）。
    """
    prm = params if params is not None else load_params()
    val = (prm.get("validation") or {}) if isinstance(prm, dict) else {}
    return bool(val.get("gate_enabled", False))


def _cat_class(value: Any) -> Optional[str]:
    """把催化剂写法归到 acid/base/metal/enzyme/photo/none 之一；认不出返回 None。"""
    if value is None:
        return "none"
    s = str(value).strip()
    if not s or s.lower() in ("none", "null", "无", "无催化", "no catalyst"):
        return "none"
    low = s.lower()
    for klass, names in _CAT_ALIASES.items():
        if low in {n.lower() for n in names}:
            return klass
    for klass, names in _CAT_ALIASES.items():
        for n in names:
            if len(n) >= 4 and n.lower() in low:
                return klass
    return None


def _catalyst_factor(run_catalyst: Any, allowed: Any,
                     params: Dict[str, Any]) -> Tuple[float, str]:
    """当前催化剂相对「无催化」的速率放大倍数。"""
    table = params.get("catalyst_speedup") or {}
    klass = _cat_class(run_catalyst)
    if klass is None or klass == "none":
        return 1.0, ""
    mult = float(table.get(klass, 1.0))
    if mult <= 1.0:
        return 1.0, ""

    names = {str(x).strip().lower() for x in (allowed or []) if x is not None}
    classes = {_cat_class(x) for x in (allowed or [])}
    if allowed is not None and klass not in classes:
        return 1.0, (f"催化剂 {run_catalyst} 不在这条反应的允许催化剂 "
                     f"{sorted(names)[:4]} 里，不加速")
    return mult, f"催化剂 {run_catalyst} 加速 {mult:g}×"


def _ph_curve(ph: float, preference: Any, params: Dict[str, Any]) -> float:
    """pH 对速率的绝对形状（未归一）：偏离最优值按高斯衰减，下限 floor。"""
    spec = params.get("ph") or {}
    span = float(spec.get("span", 3.0))
    floor = float(spec.get("floor", 0.15))
    opt = ((spec.get("optimum") or {}).get(str(preference))
           if preference is not None else None)

    def gauss(center: float) -> float:
        return math.exp(-((float(ph) - center) / span) ** 2)

    if preference in (None, "any"):
        return 1.0
    if preference == "acid":
        return max(gauss(opt if opt is not None else 2.0), floor)
    if preference == "base":
        return max(gauss(opt if opt is not None else 12.0), floor)
    if preference == "acid_base":
        return max(gauss(2.0), gauss(12.0), floor)
    if preference == "neutral":
        center = opt if opt is not None else 7.0
        return max(gauss(center), floor)
    return 1.0


def _ph_ceiling(params: Dict[str, Any]) -> float:
    """比值上限由曲线下限决定：cur ≥ floor、ref ≥ floor，故上界是 1/floor。

    第 144 轮修 C7：原代码硬编码 50.0，而 floor 默认 0.15 时实际饱和在 6.67，
    50 这个数永远取不到 —— 写一个到不了的阈值等于没写，还误导读者。
    """
    floor = float((params.get("ph") or {}).get("floor", 0.15))
    if floor <= 0:
        return float("inf")
    return 1.0 / floor


def _ph_factor(ph: float, preference: Any, ref_ph: Any = None,
               params: Dict[str, Any] = None) -> Tuple[float, str]:
    """pH 相对**参照点**的速率倍数（比值，不是绝对值）。

    归一化的理由：参照点（profile 的 pH default）本身就该是「e≈0.63 的参照实验」。
    不归一化的话，中性水解这类「profile 默认 pH=7」的反应会被 pH 折减误杀。
    """
    params = params or {}
    if preference in (None, "any"):
        return 1.0, ""
    cur = _ph_curve(ph, preference, params)
    if ref_ph is None:
        return cur, ("" if cur >= 0.99 else
                     f"pH {ph:g} 不利（偏好 {preference}），折减 {cur:.2f}")
    ref = _ph_curve(float(ref_ph), preference, params)
    mult = cur / ref if ref > 0 else 1.0
    mult = max(0.0, min(_ph_ceiling(params), mult))
    if abs(mult - 1.0) < 0.02:
        return 1.0, ""
    word = "加快" if mult > 1 else "折减"
    return mult, f"pH {ph:g}（参照 {float(ref_ph):g}）{word} {mult:.2f}×"


def _window_default(spec: Any) -> Optional[float]:
    """从 {min,max,default|median} 里取一个代表值。"""
    if not isinstance(spec, dict) or not spec:
        return None
    for key in ("default", "median"):
        v = spec.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    lo, hi = spec.get("min"), spec.get("max")
    if lo is not None and hi is not None:
        try:
            return (float(lo) + float(hi)) / 2.0
        except (TypeError, ValueError):
            return None
    return lo if lo is not None else hi


def _arrhenius_ea(params: Dict[str, Any],
                  profile: Optional[str] = None) -> Optional[float]:
    """启用且给了实测 Ea 时返回 kJ/mol，否则 None（回退 Q10）。

    优先级：`ea_by_profile[profile]` > `arrhenius.ea_kJ_per_mol`（全局）。
    为什么分层：糖苷水解与干热脱水的活化能差两倍以上（103.6 vs 215.7 kJ/mol），
    用同一个 Ea 会让高温档的 extent 系统性偏小/偏大。
    """
    a = params.get("arrhenius") or {}
    if not a.get("enabled"):
        return None
    if profile:
        hit = (params.get("ea_by_profile") or {}).get(str(profile)) or {}
        try:
            v = float(hit.get("ea_kJ_per_mol"))
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    try:
        ea = float(a.get("ea_kJ_per_mol"))
    except (TypeError, ValueError):
        return None
    return ea if ea > 0 else None


def temperature_factor(T: float, T_ref: float,
                       params: Optional[Dict[str, Any]] = None,
                       profile: Optional[str] = None) -> float:
    """k(T)/k(T_ref)：优先 Arrhenius（有实测活化能），否则回退 Q10 经验式。

    Arrhenius:  k(T)/k(T_ref) = exp(-Ea/R * (1/T - 1/T_ref))，T 用开尔文
    Q10:         k(T)/k(T_ref) = q10 ** ((T - T_ref) / 10)

    为什么换：Q10 是 10 °C 小区间内的经验近似，实测两条数据给 1.86 与 2.60，
    且分段 Q10 从 1.52 到 3.67 —— 单指数近似撑不住；Ea 是物理量，跨温度更稳
    （第一百一十三轮实测：Ea = 68.0 / 103.6 kJ/mol，见 kinetics.json）。
    profile 给定时优先用该 profile 自己的 Ea（`ea_by_profile`）。
    """
    params = params or load_params()
    T_k = float(T) + 273.15
    T_ref_k = float(T_ref) + 273.15
    if T_k <= 0 or T_ref_k <= 0:
        return 1.0
    ea = _arrhenius_ea(params, profile)
    if ea is not None:
        gas = float((params.get("arrhenius") or {}).get("R", 8.314462618))
        try:
            f = math.exp(-(ea * 1000.0) / gas * (1.0 / T_k - 1.0 / T_ref_k))
        except OverflowError:
            f = 1e6
    else:
        q10 = float((params.get("q10") or {}).get("value", 2.0))
        f = q10 ** ((float(T) - float(T_ref)) / 10.0)
    return max(1e-6, min(1e6, f))


def _concentration_factor(run, params: Dict[str, Any]) -> Tuple[float, str]:
    """浓度对表观速率的影响（二级动力学、伙伴过量的伪一级近似）。

    k_obs ∝ c / c_ref，所以 e 里的 k 乘 (c/c_ref)^order。
    为什么 linear（order=1）：绝大多数规则是「底物 + 试剂」二级反应，
    试剂过量时速率对底物是一级、对试剂浓度线性；这是教科书结论
    （Atkins' Physical Chemistry, 11th ed., ch.17），不是拟合出来的数。
    默认 ref_M = 0.1 M，超出 0.001~100 倍截断，避免荒谬输入放大结果。
    """
    blk = params.get("concentration") or {}
    if not blk.get("enabled", False):
        return 1.0, ""
    try:
        ref = float(blk.get("ref_M", 0.1))
        order = float(blk.get("order", 1.0))
        c = float(getattr(run, "concentration_M", ref) or ref)
    except (TypeError, ValueError):
        return 1.0, ""
    if ref <= 0 or c <= 0:
        return 1.0, ""
    ratio = max(1e-3, min(1e3, c / ref))
    f = ratio ** order
    return f, (f"浓度 {c:g} M / 参照 {ref:g} M → 速率 ×{f:.3g}"
               f"（二级动力学、过量伙伴近似）" if abs(f - 1.0) > 1e-9 else "")


def _extent_core(t_min: float, t_ref_min: float, T: float, T_ref: float,
                 cat_mult: float, ph_mult: float,
                 params: Dict[str, Any],
                 profile: Optional[str] = None,
                 conc_mult: float = 1.0) -> float:
    """e = 1 - exp(- (t / t_ref) * k(T)/k(T_ref) * cat * ph * conc)。"""
    if t_ref_min <= 0:
        return 1.0
    k = temperature_factor(T, T_ref, params, profile) * cat_mult * ph_mult * conc_mult
    e = 1.0 - math.exp(-(float(t_min) / float(t_ref_min)) * k)
    return max(0.0, min(1.0, e))


def calibrated_range(params: Optional[Dict[str, Any]] = None,
                     profile: Optional[str] = None) -> Optional[Tuple[float, float]]:
    """该 profile 的**实测标定温度区间**（℃）。没登记则 None。

    为什么需要它：第一百二十三轮的留一温度验证显示，三点拟合出来的 Ea
    外推到第四个温度时误差 0.6~3.3 倍 → 区间内可插值，区间外只能标注「外推」。
    数据来自 `kinetics.json` 的 `arrhenius.calibrated_range_C`，每项都指向具体数据集。
    """
    params = params or load_params()
    rng = (params.get("arrhenius") or {}).get("calibrated_range_C") or {}
    if not rng:
        return None
    hit = None
    if profile:
        hit = rng.get(str(profile))
    if hit is None:
        hit = rng.get("global")
    if not hit:
        return None
    if isinstance(hit, dict):
        hit = hit.get("range")
    try:
        lo, hi = float(hit[0]), float(hit[1])
    except (TypeError, ValueError, IndexError):
        return None
    return (lo, hi) if hi >= lo else (hi, lo)


def _pressure_effective(run, params: Dict[str, Any]) -> Tuple[float, str]:
    """压力 P2：溶液浴里 T_eff = min(T, T_sat(p))。其余浴型原样返回。"""
    T = float(getattr(run, "temperature", 100.0))
    try:
        from conditions import pressure as _P
    except Exception:
        return T, ""
    try:
        return _P.effective_temperature(run, params)
    except Exception:
        return T, ""


def extent_from_profile(resolved: Optional[Dict[str, Any]], run,
                        params: Optional[Dict[str, Any]] = None,
                        catalyst_allowed: Any = "auto",
                        profile: Optional[str] = None,
                        ) -> Tuple[float, str]:
    """按**规则的 condition_profile** 算 extent。

    resolved: schema.resolve_conditions() 的返回值（含 temperature/time_min/pH/
              catalyst/pH_preference 的窗口）。
    run:      conditions.model.Conditions（一次处理的真实条件）。
    profile:  profile 名（如 "hydrolysis"/"thermal"），用于取该族自己的 Ea；
              不给则用 kinetics.json 的全局 Ea。
    """
    params = params or load_params()
    if not resolved:
        return 1.0, "无可用条件窗口，保守放行"

    t_ref = _window_default(resolved.get("time_min"))
    T_ref = _window_default(resolved.get("temperature"))
    if t_ref is None or T_ref is None:
        return 1.0, "条件窗口缺时间或温度参照点，保守放行"

    allowed = resolved.get("catalyst") if catalyst_allowed == "auto" else catalyst_allowed
    cat_mult, cat_why = _catalyst_factor(getattr(run, "catalyst", None), allowed, params)
    ph_mult, ph_why = _ph_factor(float(getattr(run, "pH", 7.0)),
                                 resolved.get("pH_preference"),
                                 _window_default(resolved.get("pH")),
                                 params)

    T_eff, p_why = _pressure_effective(run, params)
    conc_mult, c_why = _concentration_factor(run, params)

    e = _extent_core(t_min=float(getattr(run, "time_min", t_ref)),
                     t_ref_min=t_ref,
                     T=T_eff,
                     T_ref=T_ref,
                     cat_mult=cat_mult, ph_mult=ph_mult, params=params,
                     profile=profile, conc_mult=conc_mult)
    parts = [f"参照 {T_ref:g}°C/{t_ref:g}min → 当前 "
             f"{T_eff:g}°C/"
             f"{float(getattr(run, 'time_min', t_ref)):g}min"]
    _ea = _arrhenius_ea(params, profile)
    if _ea is not None:
        _pfx = f"，profile={profile}" if profile else ""
        parts.append(f"温度按 Arrhenius（Ea={_ea:g} kJ/mol{_pfx}）")
    else:
        parts.append("温度按 Q10 经验式")
    _rng = calibrated_range(params, profile)
    if _rng is not None:
        _T = float(getattr(run, "temperature", T_ref))
        if not (_rng[0] <= _T <= _rng[1]):
            parts.append(
                f"温度 {_T:g}°C 在标定区间 {_rng[0]:g}~{_rng[1]:g}°C 之外，"
                f"属外推（第一百二十三轮：三点拟合的 Ea 外推误差 0.6~3.3 倍）")
    for w in (p_why, c_why, cat_why, ph_why):
        if w:
            parts.append(w)
    return e, "；".join(parts)


def extent_from_table(entry: Optional[Dict[str, Any]], run,
                      params: Optional[Dict[str, Any]] = None,
                      profile: Optional[str] = None,
                      ) -> Tuple[float, str]:
    """按**ORD 反应类的条件表**（reports/conditions_by_reaction_type.json 的一项）算 extent。

    表里只有 min/median/max，所以参照点用 median 温度与 median 时间。
    `entry["condition_profile"]` 存在时自动取它作为 profile（curated 规则的表里有这一项）。
    """
    params = params or load_params()
    if not entry:
        return 1.0, "该反应类无 ORD 条件数据，保守放行"
    if profile is None:
        profile = entry.get("condition_profile") or None
    t_ref = _window_default(entry.get("time_min"))
    T_ref = _window_default(entry.get("temp_C"))
    if t_ref is None or T_ref is None:
        return 1.0, "该反应类缺时间或温度中位数，保守放行"

    cat_mult, cat_why = _catalyst_factor(getattr(run, "catalyst", None),
                                         entry.get("catalysts"), params)
    ph_mult, ph_why = _ph_factor(float(getattr(run, "pH", 7.0)),
                                 entry.get("ph_preference"),
                                 _window_default(entry.get("ph")),
                                 params)
    T_eff, p_why = _pressure_effective(run, params)
    conc_mult, c_why = _concentration_factor(run, params)
    e = _extent_core(t_min=float(getattr(run, "time_min", t_ref)),
                     t_ref_min=t_ref,
                     T=T_eff,
                     T_ref=T_ref,
                     cat_mult=cat_mult, ph_mult=ph_mult, params=params,
                     profile=profile, conc_mult=conc_mult)
    parts = [f"ORD 中位 {T_ref:g}°C/{t_ref:g}min"]
    _ea = _arrhenius_ea(params, profile)
    if _ea is not None:
        _pfx = f"，profile={profile}" if profile else ""
        parts.append(f"温度按 Arrhenius（Ea={_ea:g} kJ/mol{_pfx}）")
    for w in (p_why, c_why, cat_why, ph_why):
        if w:
            parts.append(w)
    return e, "；".join(parts)


def band_of(extent: float, params: Optional[Dict[str, Any]] = None) -> str:
    """extent 的档位：none（痕量）/ minor / major。

    第一百一十六轮：分档边界从 `extent_min`（0.10，无出处）改为 `trace_below`（0.05，
    由已发表动力学数据的最小可观测转化率 0.059 向下取整得到）。
    `none` 现在表示「低于文献能观测到的量」而非「判为不发生」——它**不删除任何产物**，
    只是标注（`extent_min` 已改为 0.0，即使打开门控也不会丢产物）。
    """
    params = params or load_params()
    gates = params.get("gates") or {}
    lo = float(gates.get("trace_below", gates.get("extent_min", 0.05)))
    hi = float(gates.get("extent_major", 0.50))
    if extent < lo:
        return "none"
    if extent < hi:
        return "minor"
    return "major"


def explains(e: float, why: str = "", params: Optional[Dict[str, Any]] = None) -> str:
    """人能读的一行说明。"""
    b = band_of(e, params)
    zh = {"none": "痕量/低于可观测", "minor": "少量", "major": "主要"}[b]
    return f"转化程度 {e:.2f}（{zh}）" + (f"：{why}" if why else "")


def min_documented_conversion(path: Optional[Path] = None) -> Optional[float]:
    """已发表动力学数据里最小的非零转化率（用来钉住痕量阈值的下界）。"""
    p = Path(path) if path else (Path(__file__).resolve().parent / "kinetics_measurements.json")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    vals = [float(c) for ds in (d.get("datasets") or [])
            for c in (ds.get("conversion") or []) if float(c) > 0.0]
    return min(vals) if vals else None


# ---------------------------------------------------------------- 温度判据（第 85 轮）

def temperature_gate(lo: Optional[float], hi: Optional[float], T: float,
                     params: Optional[Dict[str, Any]] = None
                     ) -> Tuple[float, str, bool]:
    """温度判据：返回 (分数 0~1, 原因, 是否判死)。

    第 85 轮「A 案」：把两个温度层统一到同一套语义。

    旧行为（`SmartReactEngine.cond_activation`）把 ORD「这个反应类**实际做过**
    的温度范围」当成物理边界，实测方向是反的：

      · 250 °C 把水解判**关**（ORD 里水解的上限是 150 °C）—— 但高温只会让水解更快；
      · 25 °C 反而把缩合/Michael 判**开**（ORD 里这些反应有室温记录）—— 但室温下很慢。

    新语义（与 extent 同源）：

      · T < 下限 - 容差  → 判死（太冷，动力学上跑不动）
      · 下限附近          → 线性降权
      · 窗口内            → 1.0
      · 窗口之上          → **不罚**：高温只会加速；「跑过头」由 extent 饱和（→1.0）表达，
                            不再由"没被 ORD 记录过"来判死
      · T > hot_ceiling_C → 判死（超出模型适用范围；默认 400 °C ≈ 水的临界点 374 °C 之上）

    容差与上限都是**建模选择**，写在 kinetics.json 的 `temperature` 段，不是实测值。
    """
    if lo is None or hi is None:
        return 1.0, "", False
    params = params or load_params()
    tp = params.get("temperature") or {}
    tol = float(tp.get("gate_low_tolerance_C", 30.0))
    ceiling = float(tp.get("hot_ceiling_C", 400.0))
    lo, hi, T = float(lo), float(hi), float(T)

    if T > ceiling:
        return 0.0, (f"温度 {T:g}°C 高于模型适用范围上限 {ceiling:g}°C"
                     f"（近/超临界水，chemreact 的机理层不覆盖）"), True
    if T < lo - tol:
        return 0.0, (f"温度 {T:g}°C 低于该反应可行下限 {lo:g}°C（容差 {tol:g}），"
                     f"动力学上跑不动"), True
    if T < lo:
        s = max(0.0, 1.0 - (lo - T) / tol)
        return s, f"温度 {T:g}°C 略低于该反应惯用下限 {lo:g}°C，降权至 {s:.2f}", False
    if T <= hi:
        return 1.0, "", False
    return 1.0, (f"温度 {T:g}°C 高于惯用上限 {hi:g}°C，但在模型适用范围内："
                 f"按「高温加速」处理，不降权（程度见 extent）"), False
