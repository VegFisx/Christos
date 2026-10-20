# -*- coding: utf-8 -*-
r"""★ 逆合成最小闭环 ★

思路（用现有资产，不新建数据）：
  1. ★ 把 SmartReact 的 9770 条【正向】模板反过来 -> 9770 条【逆合成】模板 ★
     （reaction_template 是 "底物>>产物"，swap 成 "产物>>底物" 即可）
  2. 把目标分子套逆模板 -> 得到前体
  3. 递归拆解，直到前体命中【可获得集合】= COCONUT 26.9万 + tcm.db 2.9万
  4. ★ 每一步正向验证 ★：把前体喂回 SmartReact 正向引擎，确认真能产出目标

为什么先走这条路：RDChiral 抽 ORD 模板那一步我失败过（漏了聚类），
而反转 SmartReact 模板**立刻可用**，能先把搜索机器搭起来、验证闭环，
模板质量之后再换。

用法: python retro_search.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Windows 控制台是 GBK：脚本自己兜住编码，不依赖调用方设 PYTHONIOENCODING
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (_STAGE / "core", _STAGE / "conditions", _STAGE / "rules", _STAGE / "libs",
           _STAGE / "tools", r"D:\TCMAI\src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdChemReactions, rdMolDescriptors  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TEMPLATES = _STAGE / "libs" / "smartreact" / "data" / "templates.txt"
COCO_INDEX = _STAGE / "reports" / "coconut_inchikey_index.jsonl"
# ★ ① 可购砌块集合（由 tools/build_purchasable_blocks.py 从 ORD 抽出）★
BLOCKS_FULL = _STAGE / "reports" / "purchasable_blocks_index.jsonl"
BLOCKS_SKEL = _STAGE / "reports" / "purchasable_blocks_skeleton.jsonl"
# ★ 逆模板库（生产）——2026-10-15 用户拍板切换：
#   默认 = v2·freq>=10（L1 全量挖矿重聚类、频次门槛 10；18,914 条，可编译约 1.7 万）。
#   实测（5,002 目标 s10）：any-hit 78~79% -> 91.9%、top-50 68.65%（与全量库相同）、
#   加载 1.1 s / 595 MB（全量库为 5.8 s / 2.8 GB）；黑名单（默认关）沿用。
#   旧库（3,228 条）保留作回退；切换方式：环境变量 CHEMCREACT_RETRO_LIB 指向任一 jsonl。
RDCHIRAL_TEMPLATES_V1 = _STAGE / "reports" / "retro_templates_clustered.jsonl"   # 旧生产库（回退用）
RDCHIRAL_TEMPLATES_V2 = _STAGE / "reports" / "retro_templates_freq10.jsonl"      # 新生产库（默认）
RDCHIRAL_TEMPLATES = RDCHIRAL_TEMPLATES_V2   # 兼容旧引用；实际解析见 _resolve_rdchiral_lib()
# ★ D7（2026-10-14）：逆模板黑名单（**默认关**）——
#   来源：reports/retro_template_blacklist.json（tools/build_retro_blacklist.py 从体检 jsonl 冻结）
#   判据：n_try>=5 且 n_usable==0（56 个目标体检里 54 条"从没产出过可用路线"；
#   ★ 第四十三轮：留出复测（COCONUT 64 目标）里 3 条产出过可用 -> 已豁免移出，生效 51 条）
#   ★ 第四十二轮并入 3 条「全等 no-op」（同一分子原样两边穿过；质检员 tools/audit_template_identity.py 产出）
#   打开方式：load_rdchiral_templates(drop_blacklisted=True) / pool_query.py --retro-blacklist
#   只影响本次搜索；reports/retro_templates_clustered.jsonl 一个字不动。
RETRO_BLACKLIST = _STAGE / "reports" / "retro_template_blacklist.json"


def canon(smi: str) -> Optional[str]:
    m = Chem.MolFromSmiles(smi)
    return Chem.MolToSmiles(m) if m is not None else None


def ik(smi: str) -> Optional[str]:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    try:
        return Chem.MolToInchiKey(m)
    except Exception:
        return None


# ---------------------------------------------------------------- 可获得集合
def load_available() -> Dict[str, str]:
    """InChIKey -> 来源标签。COCONUT（天然产物）+ tcm.db（中药成分）。"""
    av: Dict[str, str] = {}
    if COCO_INDEX.exists():
        with open(COCO_INDEX, encoding="utf-8") as f:
            for line in f:
                k = line.split("\t", 1)[0].strip()
                if k and k not in av:
                    av[k] = "COCONUT"
    try:
        from tcm_ro import open_db  # ★ 只读（AGENTS.md 四）
        with open_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT inchi_key, name_en FROM compounds "
                        "WHERE inchi_key IS NOT NULL AND inchi_key != ''")
            for k, nm in cur.fetchall():
                if k and k not in av:
                    av[k] = f"tcm.db:{nm or '?'}"
    except Exception as ex:
        print(f"   [warn] tcm.db 读取失败: {ex}")
    return av


def load_purchasable_blocks(with_reagents: bool = False):
    """可购砌块索引 -> (full IK dict, skeleton dict)。

    这是 ① 的产物：ORD 里【只作反应物、从不作产物】的分子 = 化学家在市场上买的原料，
    比 COCONUT/tcm.db（天然产物）更接近逆合成真正需要的终止集合。
    with_reagents=False 只用核心砌块（映射率高 = 原子真进了产物 = 真底物）。
    """
    full, skel = {}, {}
    if not (BLOCKS_FULL.exists() and BLOCKS_SKEL.exists()):
        return full, skel
    for path, sink, key in ((BLOCKS_FULL, full, "inchikey"),
                            (BLOCKS_SKEL, skel, "skeleton")):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if not with_reagents and r.get("source") == "ORD_reagent":
                        continue
                    k = r.get(key)
                    if k:
                        sink[k] = f"{r.get('source', '?')}({r.get('n_as_reactant', 0)})"
        except Exception as ex:
            print(f"   [warn] 砌块索引读取失败 {path.name}: {ex}")
    return full, skel


# ---------------------------------------------------------------- 逆合成模板
@dataclass
class RetroTemplate:
    smarts: str          # 逆方向 SMARTS：产物>>底物
    name: str            # 反应类型
    tid: int
    rxn: object = None   # 编译后的 RDKit 反应


def load_retro_blacklist(path: Optional[Path] = None, verbose: bool = True) -> Dict[str, Dict]:
    """★ D7：读逆模板黑名单（smarts -> 元信息）。

    两种条目同一开关：
      * kind="never_usable"（缺省）：56 目标体检里"≥5 次切断、0 可用"的模板；
      * kind="noop"（★ 第四十二轮，质检员产出）：全等模板 —— 同一分子原样出现在反应两边，
        只会把目标自己当前体还回来，结构上不可能贡献有效路线。

    文件不存在 -> 返回空 dict 并**打警告**（不静默：静默会让"默认关"悄悄变成"永远没开成"）。
    """
    p = path or RETRO_BLACKLIST
    if not p.exists():
        if verbose:
            print(f"   [warn] 逆模板黑名单不存在：{p}"
                  f"（按不启用处理；生成用 tools/build_retro_blacklist.py）")
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        out = {}
        for e in obj.get("entries", []):
            s = str(e.get("smarts") or "").strip()
            if s:
                out[s] = e
        for e in obj.get("noop_entries", []):        # ★ 第四十二轮：全等 no-op 并入同一开关
            s = str(e.get("smarts") or "").strip()
            if s:
                e = dict(e)
                e.setdefault("kind", "noop")
                out[s] = e
        for e in obj.get("r2_family_entries", []):   # ★ B8：保护基/官能化添加逆用族（全 R2、0 可用）
            s = str(e.get("smarts") or "").strip()
            if s:
                e = dict(e)
                e.setdefault("kind", "r2_family")
                out[s] = e
        return out
    except Exception as ex:                          # noqa: BLE001 —— 打印，不静默
        print(f"   [warn] 逆模板黑名单读取失败：{type(ex).__name__}: {ex}")
        return {}


def apply_retro_blacklist(templates: List[RetroTemplate],
                          blacklist: Optional[Dict[str, Dict]] = None,
                          verbose: bool = True):
    """★ D7：把黑名单里的逆模板从列表里**临时**过滤掉（只影响本次搜索）。

    返回 (kept, info)；info 含 n_blacklist / n_dropped / n_missing_in_lib（黑名单条目在
    这份模板表里找不到的数量——模板库更新过的话要喊出来，否则黑名单会静默失配）。
    """
    bl = load_retro_blacklist(verbose=verbose) if blacklist is None else blacklist
    info = {"enabled": True, "path": str(RETRO_BLACKLIST),
            "n_blacklist": len(bl), "n_dropped": 0, "n_missing_in_lib": 0}
    if not bl:
        return list(templates), info
    present = {t.smarts for t in templates}
    kept, dropped = [], []
    for t in templates:
        if t.smarts in bl:
            dropped.append(t)
        else:
            kept.append(t)
    info["n_dropped"] = len(dropped)
    n_noop = sum(1 for t in dropped if (bl.get(t.smarts) or {}).get("kind") == "noop")
    n_r2 = sum(1 for t in dropped if (bl.get(t.smarts) or {}).get("kind") == "r2_family")
    info["n_dropped_noop"] = n_noop
    info["n_dropped_r2_family"] = n_r2
    info["n_dropped_never_usable"] = len(dropped) - n_noop - n_r2
    info["n_missing_in_lib"] = sum(1 for s in bl if s not in present)
    if verbose:
        if n_noop or n_r2:
            bits = [f"never-usable {len(dropped) - n_noop - n_r2}"]
            if n_r2:
                bits.append(f"R2家族 {n_r2}")
            bits.append(f"no-op {n_noop}")
            print(f"   ★ D7 黑名单（默认关；本次开）：丢弃 {len(dropped)} 条逆模板"
                  f"（{' · '.join(bits)}）（{len(templates)} -> {len(kept)}）")
        else:
            print(f"   ★ D7 黑名单（默认关；本次开）：丢弃 {len(dropped)} 条 never-usable 逆模板"
                  f"（{len(templates)} -> {len(kept)}）")
        if info["n_missing_in_lib"]:
            print(f"   [warn] 黑名单有 {info['n_missing_in_lib']} 条在本模板表里找不到"
                  f"（模板库更新过？黑名单对这些静默失配）")
    return kept, info


def _resolve_rdchiral_lib(path=None) -> Path:
    """解析生产模板库路径：显式参数 > 环境变量 CHEMCREACT_RETRO_LIB > 默认（v2·freq10；缺则回退旧库）。"""
    if path is not None:
        return Path(path)
    env = os.environ.get("CHEMCREACT_RETRO_LIB", "").strip()
    if env:
        return Path(env)
    if RDCHIRAL_TEMPLATES_V2.exists():
        return RDCHIRAL_TEMPLATES_V2
    return RDCHIRAL_TEMPLATES_V1


def load_rdchiral_templates(path: Optional[Path] = None,
                            drop_blacklisted: bool = False) -> List[RetroTemplate]:
    """★ 生产模板库 ★：2026-10-15 起默认 = v2·freq>=10（18,914 条；旧库 3,228 条可回退）。

    已经是"产物>>前体"方向，**不需要反转**。
    实测：v2·freq10 在 5,002 目标上 any-hit 91.9%（旧库 78~79%）；见 reports/第五十轮/结果汇总。

    ★ D7：drop_blacklisted=True 时过滤「never-usable 黑名单」（**默认 False = 不过滤**）。
    """
    out: List[RetroTemplate] = []
    p = _resolve_rdchiral_lib(path)
    if not p.exists():
        return out
    bad = 0
    with open(p, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                smarts = r["template"]
                rx = rdChemReactions.ReactionFromSmarts(smarts)
            except Exception:
                bad += 1
                continue
            if rx is None or rx.GetNumReactantTemplates() != 1:
                bad += 1
                continue          # 逆模板必须是"1 个目标 -> 前体"
            out.append(RetroTemplate(smarts=smarts, name="rdchiral_retro", tid=i, rxn=rx))
    if bad:
        print(f"   [warn] rdchiral 模板库跳过 {bad} 条无法编译/多目标的模板")
    if drop_blacklisted:
        out, _info = apply_retro_blacklist(out, verbose=True)
    return out


def load_retro_templates(limit: Optional[int] = None) -> List[RetroTemplate]:
    """旧模板库：SmartReact 正向模板【反转】。保留用于对照/回退，默认不再使用。"""
    out: List[RetroTemplate] = []
    if not TEMPLATES.exists():
        return out
    for line in TEMPLATES.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        f = line.split("\t")
        if len(f) != 5:
            continue
        name, tid, _ex, smarts, _cats = f
        if ">>" not in smarts:
            continue
        lhs, rhs = smarts.split(">>", 1)
        retro = f"{rhs}>>{lhs}"          # ★ 反向 ★
        try:
            rx = rdChemReactions.ReactionFromSmarts(retro)
        except Exception:
            continue
        if rx is None or rx.GetNumReactantTemplates() != 1:
            continue                      # 逆模板必须是"1 个目标 -> 前体"
        try:
            t = int(tid)
        except ValueError:
            continue
        out.append(RetroTemplate(smarts=retro, name=name, tid=t, rxn=rx))
        if limit and len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- 搜索
# ★ ② 前体可信度过滤 ★
# 反转模板会给出一批化学上不可能是"买来原料"的前体，实测两类最突出：
#   1) 含【试剂元素】：B/Si/Sn/Zn/Mg/Li/Al/Ti
#      实测：suzuki 132 条 + chan_lam 112 条 + negishi_batch 44 条 + ART 12 条 = 300 条模板
#      例：chan_lam 反转给出 BC(C)=O（酰基硼）、BCC（烷基硼）
#   2) 带电荷的【小碎片】且电荷配平不成立
#      例：CC[NH-]（酰胺负离子）——真实反应里需要 NaH 之类的碱，不是你要买的原料
# 注意：负离子是电荷平衡反应（如脱质子）的正常产物，所以只在它无法被电荷平衡时才判怪，
#       否则会把"羧酸 -> 羧酸根"这种正常步骤也误杀。
REAGENT_ELEMENTS = {5, 14, 50, 30, 12, 3, 13, 22}   # B Si Sn Zn Mg Li Al Ti


# 带电小碎片（S4）单独一档：默认【不】过滤，因为羰基负离子可能来自"脱质子"这种正常步骤。
# 要用它必须显式开 weird_charged=True，并且必须用数据证明过滤后不掉分（见 bench_blocks_value.py --charged-filter）。
CHARGED_SMALL_HAC = 8

# ★ ② 惰性小分子前体（S5）—— 实测最要命的一类 ★
# 依据（tools/measure_inert_precursors.py，5 个中药成分，764 条"全部前体可得"的路线）：
#   前体重原子数分布呈双峰：2 原子的占 42.7%（CCl/CC/CO/H2O…），19 原子的占 42.0%
#   且 snar_alcohol / esterification / mitsunobu / williamson / ullmann_phenol /
#   ester_schotten_baumann 这几个类型里，100% 的路线都带一个 2 原子前体。
# 为什么这是错的：这类路线的另一个前体【把整个目标骨架原样保留了】，
#   只是在末端换了个基团（如 5-methoxymarmesin <- 去甲基黄酮 + CCl）。
#   这是"给已有骨架加甲基"，不是"怎么造这个骨架"，对合成没有价值。
# 判据：目标本身足够大（>15 重原子）时，不允许用 <=2 重原子的前体；
#   小目标不做此限制（对甲酚 <- 甲酚 + 甲醇 这类是合理的）。
INERT_PRECURSOR_HAC = 2
INERT_CHECK_TARGET_HAC = 15


def prec_is_weird(smi: str, charged_small: bool = False):
    """返回 (是否怪, 原因)；正常返回 (False, '')。"""
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return True, "无法解析"
    if any(a.GetAtomicNum() in REAGENT_ELEMENTS for a in m.GetAtoms()):
        return True, "含试剂元素(B/Si/Sn/Zn/Mg/Li/Al/Ti)"
    if m.GetNumHeavyAtoms() <= 6 and any(a.GetNumRadicalElectrons() > 0
                                          for a in m.GetAtoms()):
        return True, "小自由基"
    if charged_small and Chem.GetFormalCharge(m) != 0             and m.GetNumHeavyAtoms() <= CHARGED_SMALL_HAC             and any(a.GetFormalCharge() != 0 and a.GetTotalNumHs() == 0
                    and a.GetDegree() == 0 for a in m.GetAtoms()):
        return True, "自由离子(无氢无键)"
    return False, ""


# ★ ② 路线化学可用性判据（2026-10-11 第七轮）★
# 判据已用 6 条【已知化学合法】的路线校准（tools/check_usability_criteria.py，9/10 符合期望）：
#   v1 用"前体重原子数之和 >= 目标"判"无进展" -> 把 6 条合法路线全误杀（缩合反应本来就脱水）
#   v2/v3 改用【结构层面】：前体是不是"目标本身换个基团"
# 实际命中率（100 个 ORD 产物，depth3 beam4，120 条路线）：R1 89 次 / R2 32 次
USABILITY_MIN_TARGET_HAC = 12
USABILITY_RESIDUE_MCS_FRAC = 0.80
USABILITY_INERT_HAC = 2
# ★ D7（2026-10-13）标定结果：R1 的 MCS 在天然产物尺寸上 94% 超时、结果随负载变。
#   标定（tools/calib_r1_criterion.py，2,090 对 12~30 重原子分子，MCS 0 超时）：
#     元素重叠比 Σmin/目标 >= 0.95  ->  precision 0.976 / recall 0.900 / F1 0.937
#     重原子比 >= 0.95              ->  precision 0.966 / recall 0.915 / F1 0.940
#   所以：**大分子（> MCS_MAX_HAC）改用确定性的元素重叠比**，中小分子仍用 MCS。
USABILITY_MCS_MAX_HAC = 40
USABILITY_ELEM_RATIO_BIG = 0.95


# ★ R4（2026-10-11 B 轮新增）：荒谬前体 ★
# 实测动机（tools/audit_route_sanity.py，60 个目标 115 条路线）：
#   **38.3% 的路线含"极端小分子/无机碳"前体**，最典型的是 O=C=O（CO2）：
#       目标 …c1cnc(Cl)nc1C(=O)O  <-  …c1cnc(Cl)nc1Cl  +  O=C=O
#   即"往芳环上插一个二氧化碳"。结构判据（R1/R2/R3）完全抓不住它 ——
#   每步前体都比目标小、都"可购买"（CO2 当然买得到），但没人这么合成。
# 判据：以下前体不允许当作"骨架来源"（除非目标本身只有碳+氧且很小）
ABSURD_PRECURSORS = {
    "O=C=O",            # CO2
    "O=C(O)O",          # 碳酸
    "O=C([O-])O",       # 碳酸氢根
    "O=C([O-])[O-]",    # 碳酸根
    "O=CO", "O=C[O-]",  # 甲酸/甲酸根
    "N", "O", "O=O", "S", "Cl", "Br", "I", "F",   # 单质/无机小分子
    "[H][H]", "O", "N#N", "C",
}
ABSURD_MAX_TARGET_HAC = 20      # 目标很大时，绝不允许这些当骨架来源


# ---------------------------------------------------------------- D7：让 R1 判据算得起
# 体检脚本（tools/audit_retro_templates.py）第一次跑 60 个目标 × 3,228 条模板 >10 分钟没完，
# 热点就是下面这次 MCS。这里加两样**不改判据语义**的东西：
#   ① 便宜的"公共原子数上界"：任何公共子结构的原子数 <= Σ_元素 min(目标计数, 前体计数)；
#      上界都够不到阈值 -> MCS 不可能命中 -> 直接跳过（不调 rdFMCS）。
#   ② MCS 结果缓存：同一个 (目标, 前体) 会被很多条模板重复产出。
_ELEM_CACHE: Dict[str, Dict[str, int]] = {}
_MCS_CACHE: Dict[Tuple[str, str], int] = {}
USTAT: Dict[str, int] = {"mcs_calls": 0, "mcs_skipped_by_bound": 0, "mcs_cache_hit": 0,
                        "mcs_timeout": 0, "big_molecule_deterministic": 0,
                        "r1_pass_available": 0, "avail_check_error": 0,
                        "r1_deterministic": 0}


def reset_usability_stats() -> None:
    USTAT.update({"mcs_calls": 0, "mcs_skipped_by_bound": 0, "mcs_cache_hit": 0,
                  "mcs_timeout": 0, "big_molecule_deterministic": 0,
                  "r1_pass_available": 0, "avail_check_error": 0,
                  "r1_deterministic": 0})


def _elem_counts(smi: str) -> Dict[str, int]:
    """分子 -> 元素计数（缓存）。解析失败返回空 dict。"""
    hit = _ELEM_CACHE.get(smi)
    if hit is not None:
        return hit
    out: Dict[str, int] = {}
    try:
        from rdkit.Chem import rdMolDescriptors
        m = Chem.MolFromSmiles(smi)
        if m is not None:
            f = rdMolDescriptors.CalcMolFormula(m)
            import re as _re
            for el, num in _re.findall(r"([A-Z][a-z]?)(\d*)", f):
                # ★ 排除 H：MCS 数的是**重原子**，把 H 算进去只会让上界更松（更慢）
                if el and el != "H":
                    out[el] = out.get(el, 0) + (int(num) if num else 1)
    except Exception:
        out = {}
    _ELEM_CACHE[smi] = out
    return out


def _common_atom_upper_bound(a: Dict[str, int], b: Dict[str, int]) -> int:
    """公共原子数的**上界**（Σ_元素 min）——只用来安全地跳过 MCS。"""
    if not a or not b:
        return 10 ** 9                                # 拿不到计数就不跳过（保守）
    return sum(min(v, b.get(k, 0)) for k, v in a.items())


def step_usability(target: str, precursors, available_fn=None,
                   strict_elem_complete: bool = True) -> Tuple[bool, str]:
    """单步是否化学可用。返回 (可用?, 原因)。不可用原因见 R1~R4。

    ★ 第四十三轮（用户口径 2026-10-14）：「只在前体不可得时才判假」——
    给 available_fn 时，R1（残基路线）触发后先查该近同前体**可得性**：
      可得（COCONUT/tcm.db/砌块/池里买的到）-> 这是真实终步（"买烯烃→加氢"），放行并计数
      不可得 -> 维持 R1 判假。
    默认 available_fn=None = 旧行为（体检/评估脚本不受影响）。

    ★ B6（2026-10-14 建好；2026-10-15 **用户拍板：翻默认**）：
    strict_elem_complete=True（**现为默认**）时，任何"元素全覆盖"
    （Σ元素min = 目标重原子数，即前体原样保留目标全部重原子）的近同前体一律确定性判 R1，
    不再走限时 MCS——堵住"环上编辑型"漏判与机器依赖。
    复现旧行为（论文对照/消融）：显式传 strict_elem_complete=False。
    """
    def _r1_pass(ps_: str) -> bool:
        if available_fn is None:
            return False
        try:
            if available_fn(ps_):
                USTAT["r1_pass_available"] = USTAT.get("r1_pass_available", 0) + 1
                return True
        except Exception:                             # noqa: BLE001 —— 计数，不静默
            USTAT["avail_check_error"] = USTAT.get("avail_check_error", 0) + 1
        return False

    t = Chem.MolFromSmiles(target)
    if t is None:
        return False, "目标无法解析"
    t_hac = t.GetNumHeavyAtoms()
    for ps in precursors:
        p = Chem.MolFromSmiles(ps)
        if p is None:
            return False, "前体无法解析"
        p_hac = p.GetNumHeavyAtoms()
        if p_hac > t_hac:
            return False, "R2_前体大于目标"
        if t_hac >= USABILITY_MIN_TARGET_HAC and p_hac >= t_hac - 2:
            need = t_hac * USABILITY_RESIDUE_MCS_FRAC
            # ★ D7 ①：先算便宜的公共原子数上界；够不到阈值就不调 MCS（语义不变）
            ub = _common_atom_upper_bound(_elem_counts(target), _elem_counts(ps))
            # ★ B6（默认关）：元素全覆盖 -> 确定性残基，免 MCS、免机器依赖
            if strict_elem_complete and ub >= t_hac:
                USTAT["r1_deterministic"] = USTAT.get("r1_deterministic", 0) + 1
                if _r1_pass(ps):
                    continue
                return False, "R1_残基路线"
            if t_hac > USABILITY_MCS_MAX_HAC:
                # ★ D7 ③（标定后）：大分子上 MCS 基本必然超时 -> 直接用**确定性**的元素重叠比，
                #   口径见文件头常量注释（precision 0.976 / recall 0.900）。
                USTAT["big_molecule_deterministic"] = USTAT.get("big_molecule_deterministic", 0) + 1
                if ub / float(t_hac) >= USABILITY_ELEM_RATIO_BIG:
                    if _r1_pass(ps):
                        continue
                    return False, "R1_残基路线"
            elif ub < need:
                USTAT["mcs_skipped_by_bound"] += 1
            else:
                key = (target, ps)
                if key in _MCS_CACHE:                  # ★ D7 ②：结果复用
                    USTAT["mcs_cache_hit"] += 1
                    na = _MCS_CACHE[key]
                else:
                    na, canceled = 0, False
                    try:
                        from rdkit.Chem import rdFMCS
                        mcs = rdFMCS.FindMCS([t, p], timeout=2,
                                             atomCompare=rdFMCS.AtomCompare.CompareElements,
                                             bondCompare=rdFMCS.BondCompare.CompareOrder,
                                             ringMatchesRingOnly=True, completeRingsOnly=True)
                        na = int(mcs.numAtoms)
                        # ★ 关键：MCS 是"限时"搜索 —— 超时(canceled)时结果是**机器负载的产物**，
                        #   不是分子的性质。缓存它会让这个 pair 永久判错（实测踩过：
                        #   target == precursor 的大分子被缓存成 0，R1 从此不再触发）。
                        canceled = bool(getattr(mcs, "canceled", False))
                    except Exception:
                        na, canceled = 0, True
                    if canceled:
                        USTAT["mcs_timeout"] += 1
                    else:
                        _MCS_CACHE[key] = na
                    USTAT["mcs_calls"] += 1
                if na >= need:
                    if _r1_pass(ps):
                        continue
                    return False, "R1_残基路线"
        if t_hac > 15 and p_hac <= USABILITY_INERT_HAC:
            return False, "R3_惰性小分子"
        # R4：荒谬前体（CO2/碳酸盐/单质小分子）当骨架来源
        if ps in ABSURD_PRECURSORS and t_hac > ABSURD_MAX_TARGET_HAC:
            return False, "R4_荒谬前体(CO2/无机小分子)"
    return True, "ok"


def route_usability(route, available_fn=None) -> Tuple[bool, str]:
    """整条路线是否化学可用（所有步骤都要干净）。available_fn 语义见 step_usability。"""
    for st in route.steps:
        ok, why = step_usability(st.target, st.precursors, available_fn=available_fn)
        if not ok:
            return False, why
    return True, "ok"


@dataclass
class Step:
    target: str                      # 要造的东西
    precursors: Tuple[str, ...]      # 前体
    template: str                    # 用了哪条逆模板
    reaction_name: str
    forward_ok: Optional[bool] = None   # 正向验证结果
    weird: Tuple[str, ...] = ()      # ★ ② 不可信前体（空 = 干净）


@dataclass
class Route:
    steps: List[Step] = field(default_factory=list)
    terminals: List[str] = field(default_factory=list)   # 命中可获得集合的前体
    score: float = 0.0
    usable: bool = True              # ★ ② 化学可用性（所有步骤都不触发 R1/R2/R3）
    unusable_reason: str = "ok"      # 不可用的原因（R1_残基路线 / R2_前体大于目标 / …）


class RetroSearch:
    def __init__(self, templates: List[RetroTemplate], available: Dict[str, str],
                 max_precursors_per_step: int = 8, verbose: bool = False,
                 blocks_full: Optional[Dict[str, str]] = None,
                 blocks_skel: Optional[Dict[str, str]] = None,
                 filter_weird: bool = True, weird_charged: bool = False,
                 skel_tol: int = 1, filter_inert: bool = True,
                 filter_upsizing: bool = True, avoid_residue: bool = True,
                 mcs_topk: int = 40):
        self.templates = templates
        self.available = available
        self.max_prec = max_precursors_per_step
        self.verbose = verbose
        # ★ ② 默认丢掉含"不可信前体"的切断方案（可用 filter_weird=False 关掉做对比）
        self.filter_weird = filter_weird
        self.weird_charged = weird_charged
        # ★ ② 骨架匹配的重原子数容差：0 = 必须完全相同；1 = 允许差一个原子
        #   （换一个取代基的类似物；碘代胸苷 vs 胸苷 差 1 个碘）
        self.skel_tol = skel_tol
        # ★ ② S5：大目标不许靠"<="2 重原子的惰性小分子"当另一个前体
        self.filter_inert = filter_inert
        # ★ B 两项搜索层过滤（把"可用性判据"从排序层下沉到搜索层）★
        #   filter_upsizing：切断阶段就丢掉"前体比目标还大"的方案（逆向放大，不是拆解）
        #   avoid_residue ：递归时不去拆"基本等于目标本身"的前体（换基团路线，拆它没意义）
        self.filter_upsizing = filter_upsizing
        self.avoid_residue = avoid_residue
        # ★ C-1：只对前 mcs_topk 个候选算 MCS 残基度（0 = 关闭该排序）
        self.mcs_topk = mcs_topk
        self.n_upsizing_dropped = 0
        self.n_residue_skipped = 0
        self._mcs_cache: Dict[tuple, int] = {}
        self.n_inert_dropped = 0
        self.n_weird_dropped = 0
        self.weird_reasons = {}
        self.blocks_meta: Dict[str, tuple] = {}
        self.blocks_skel_props: Dict[str, set] = {}
        self._meta_loaded = False
        # ① 可购砌块（full InChIKey / 骨架 两套）
        self.blocks_full = blocks_full or {}
        self.blocks_skel = blocks_skel or {}
        self._avail_cache: Dict[str, Optional[str]] = {}
        self._match_level: Dict[str, str] = {}

    # ---- 砌块索引附加信息（自检用，首次调用时载入） ----
    def _blocks_meta(self):
        if self._meta_loaded:
            return
        self._meta_loaded = True
        path = _STAGE / "reports" / "purchasable_blocks_index.jsonl"
        if not path.exists():
            return
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    k = r.get("inchikey")
                    if k:
                        hac = int(r.get("heavy_atoms", -1))
                        chg = int(r.get("charge", 0))
                        self.blocks_meta[k] = (hac, chg, r.get("smiles", ""))
                        self.blocks_skel_props.setdefault(
                            k.split("-")[0], set()).add((hac, chg))
        except Exception:
            pass

    def is_available(self, smi: str) -> Optional[str]:
        """返回来源标签；None = 不在任何终止集合里。

        四级判定（★ 2026-10-11 ② 修正：加了两条"不许乱匹配"的护栏）★
          1. full InChIKey 命中 COCONUT/tcm.db       -> 化学上同一分子
          2. 砌块 full InChIKey 命中
              2b. 且【电荷一致】—— 负离子不可得，除非砌块库本身就是那个离子
          3. 砌块【骨架】命中，标 '~' 前缀，且必须
              3a.【重原子数相同】（碘代胸苷 ≠ 胸苷，差一个碘就不算同一物质）
              3b.【电荷一致】
        ★ 含试剂元素(B/Si/Sn/Zn/Mg/Li/Al/Ti) 的分子【永不】靠骨架命中算可得。
          实测依据：chan_lam 反转给出的 BC(C)=O 会因骨架匹配到阿司匹林(重原子13)
          被误判"可得"；BCC 骨架匹配到对甲酚。这两类不是能买的原料。
        """
        if smi in self._avail_cache:
            return self._avail_cache[smi]
        m = Chem.MolFromSmiles(smi)
        hac = m.GetNumHeavyAtoms() if m else -1
        chg = Chem.GetFormalCharge(m) if m else 0
        has_reag = bool(m) and any(a.GetAtomicNum() in REAGENT_ELEMENTS
                                   for a in m.GetAtoms())
        k = ik(smi)
        v = self.available.get(k) if k else None
        level = "old_terminal" if v else ""
        if v is None and k:
            v = self.blocks_full.get(k)
            level = "block_full" if v else ""
            if v:
                self._blocks_meta()
                bm = self.blocks_meta.get(k)
                if bm and bm[1] != chg:
                    v, level = None, ""          # 2b 电荷不一致 -> 不算
        if v is None and k and not has_reag:
            sk = k.split("-")[0]
            b = self.blocks_skel.get(sk)
            if b:
                self._blocks_meta()
                # 3a/3b：骨架命中必须电荷一致，且重原子数在容差内
                ok = any(c == chg and abs(h - hac) <= self.skel_tol
                         for h, c in self.blocks_skel_props.get(sk, ()))
                if ok:
                    v = f"~{b}"              # ~ = 骨架命中（构型/立体可能不同）
                    level = "block_skel"
        self._avail_cache[smi] = v
        self._match_level[smi] = level
        return v

    def disconnections(self, target: str) -> List[Step]:
        """对目标分子套所有逆模板，返回所有单步切断方案。

        filter_weird=True 时，含【不可信前体】的方案直接不进结果
        （判定见 prec_is_weird：含 B/Si/Sn/Zn/Mg/Li/Al/Ti，或小自由基）。
        """
        m = Chem.MolFromSmiles(target)
        if m is None:
            return []
        target_hac = m.GetNumHeavyAtoms()
        out: List[Step] = []
        for t in self.templates:
            try:
                results = t.rxn.RunReactants((m,))
            except Exception:
                continue
            for tup in results[:self.max_prec]:
                pres = []
                ok = True
                for pm in tup:
                    try:
                        Chem.SanitizeMol(pm)
                    except Exception:
                        ok = False
                        break
                    cs = canon(Chem.MolToSmiles(pm))
                    if not cs:
                        ok = False
                        break
                    pres.append(cs)
                if not ok or not pres:
                    continue
                prec = tuple(sorted(set(pres)))
                weird = tuple(f"{p}[{why}]" for p in prec
                              for bad, why in (prec_is_weird(p, self.weird_charged),)
                              if bad)
                for w in weird:
                    why = w.split("[", 1)[1].rstrip("]")
                    self.weird_reasons[why] = self.weird_reasons.get(why, 0) + 1
                if weird and self.filter_weird:
                    self.n_weird_dropped += 1
                    continue
                # ★ B-1：前体比目标还大 = 逆向放大，不是拆解 -> 直接丢
                if self.filter_upsizing:
                    t_m = Chem.MolFromSmiles(target)
                    t_hac2 = t_m.GetNumHeavyAtoms() if t_m else -1
                    if t_hac2 > 0 and any(
                            (Chem.MolFromSmiles(p).GetNumHeavyAtoms()
                             if Chem.MolFromSmiles(p) else 0) > t_hac2
                            for p in prec):
                        self.n_upsizing_dropped += 1
                        continue
                # S5：大目标 + 有惰性小分子前体 -> 丢掉（"给已有骨架加个甲基"不是路线）
                if self.filter_inert and target_hac > INERT_CHECK_TARGET_HAC:
                    smalls = [p for p in prec
                              if (Chem.MolFromSmiles(p).GetNumHeavyAtoms()
                                  if Chem.MolFromSmiles(p) else 99) <= INERT_PRECURSOR_HAC]
                    if smalls and len(prec) > 1:
                        self.n_inert_dropped += 1
                        continue
                out.append(Step(target=target, precursors=prec,
                                template=t.smarts, reaction_name=t.name,
                                weird=weird))
            if len(out) > 2000:
                break
        return out

    def _residue_frac(self, target_smi: str, precursors) -> float:
        """方案里最大的「残基度」：某前体与目标的最大公共子结构 / 目标重原子数。

        返回 0.0 表示所有前体都明显小于目标（真拆解）；接近 1.0 表示"换个基团"。
        带缓存（MCS 很贵），只对 HAC 差 <=2 的前体算。
        """
        t = Chem.MolFromSmiles(target_smi)
        if t is None:
            return 0.0
        t_hac = t.GetNumHeavyAtoms()
        if t_hac < USABILITY_MIN_TARGET_HAC:
            return 0.0
        worst = 0.0
        for ps in precursors:
            p = Chem.MolFromSmiles(ps)
            if p is None:
                continue
            p_hac = p.GetNumHeavyAtoms()
            if p_hac < t_hac - 2:
                continue                  # 明显小，不可能是"换个基团"
            key = (target_smi, ps)
            n = self._mcs_cache.get(key)
            if n is None:
                try:
                    from rdkit.Chem import rdFMCS
                    mcs = rdFMCS.FindMCS([t, p], timeout=2,
                                         atomCompare=rdFMCS.AtomCompare.CompareElements,
                                         bondCompare=rdFMCS.BondCompare.CompareOrder,
                                         ringMatchesRingOnly=True, completeRingsOnly=True)
                    n = mcs.numAtoms
                except Exception:
                    n = 0
                self._mcs_cache[key] = n
            worst = max(worst, n / t_hac)
        return worst

    def _is_residue(self, target_smi: str, prec_smi: str) -> bool:
        """前体是不是"基本等于目标本身"（只换了个基团）——最大公共子结构占比 >= 80%。

        与 eval_route_usability.judge_step 的 R1 同一判据（避免两处口径不一致）。
        带缓存：同 (目标, 前体) 只算一次。
        """
        t = Chem.MolFromSmiles(target_smi)
        p = Chem.MolFromSmiles(prec_smi)
        if t is None or p is None:
            return False
        t_hac = t.GetNumHeavyAtoms()
        if t_hac < USABILITY_MIN_TARGET_HAC:
            return False
        p_hac = p.GetNumHeavyAtoms()
        if p_hac < t_hac - 2:
            return False                    # 明显小很多，不可能是"换个基团"
        key = (target_smi, prec_smi)
        if key in self._mcs_cache:
            return self._mcs_cache[key] >= t_hac * USABILITY_RESIDUE_MCS_FRAC
        try:
            from rdkit.Chem import rdFMCS
            mcs = rdFMCS.FindMCS([t, p], timeout=2,
                                 atomCompare=rdFMCS.AtomCompare.CompareElements,
                                 bondCompare=rdFMCS.BondCompare.CompareOrder,
                                 ringMatchesRingOnly=True, completeRingsOnly=True)
            n = mcs.numAtoms
        except Exception:
            n = 0
        self._mcs_cache[key] = n
        if n >= t_hac * USABILITY_RESIDUE_MCS_FRAC:
            self.n_residue_skipped += 1
            return True
        return False

    def _tractability(self, smi: str, cache: Dict[str, int]) -> int:
        """可拆性启发式：这个分子作为【目标】时能套出多少个切断方案。

        ★ ② 新打分依据（实测动机）：旧启发式"挑最不可得的、分子量最大的前体"，
        会优先去拆那些【模板库根本拆不动】的大中间体，白耗节点预算。
        实测（reports/①③诊断）：失败目标的缺失前体里 86% 重原子数 >15，
        它们是复杂中间体 —— 该继续拆，但如果模板拆不动，就该换别的分支。
        这里用"能套出多少方案"作为可拆性的廉价近似（结果缓存）。
        """
        if smi in cache:
            return cache[smi]
        n = len(self.disconnections(smi))
        cache[smi] = n
        return n

    def search(self, target: str, max_depth: int = 3,
               beam: int = 4, max_dis: int = 400,
               time_limit_s: float = 60.0,
               node_budget: int = 3000,
               max_routes: int = 3,
               heuristic: int = 1) -> Tuple[List[Route], Dict[str, int]]:
        """★ 多步束搜索（2026-10-11 第五轮重写）★

        实测（reports/新搜索器-报告.md，100 个 ORD 真实产物）：
            旧库+单步 4.0%  ->  新库+单步 15.0%  ->  深度2 30.0%  ->  深度3 45.0%
        旧实现是"单步扫全部方案、找到就返回"，只能拿 5% 左右。

        与旧实现的三处关键差别：
          1. 真正递归：一步到位找不到时，挑【最不可得的、分子量最大的】前体继续拆
          2. 硬上限：节点预算 + 单目标时间上限（失败也不会挂死）
          3. 一步到位优先：先扫【全部】方案（不截断到前 200 个），有就直接收口

        ★ 关键设计：「可获得」是【前体】的终止条件，不是【目标】的。
          目标本身在 COCONUT 里（是天然产物）恰恰说明它值得拆解。
        """
        stat = defaultdict(int)
        routes: List[Route] = []
        t0 = time.time()
        budget = [node_budget]
        tract_cache: Dict[str, int] = {}
        route_sigs = set()
        stat["启发式"] = heuristic

        def expand(mol: str, path: List[Step], depth: int):
            if time.time() - t0 > time_limit_s:
                stat["时间上限触发"] += 1
                return
            if budget[0] <= 0:
                stat["节点预算耗尽"] += 1
                return
            budget[0] -= 1
            dis = self.disconnections(mol)
            stat[f"深度{depth}_切断方案"] += len(dis)
            if not dis:
                stat["无切断方案"] += 1
                return

            # 打分：全部前体可得的方案优先，其次可得前体多的
            scored = []
            for st in dis[:max_dis]:
                avs = [self.is_available(p) for p in st.precursors]
                n_av = sum(1 for a in avs if a)
                scored.append((n_av == len(st.precursors), n_av, st, avs))
            scored.sort(key=lambda x: (not x[0], -x[1]))

            # ★ C-1：在【候选里】再按"残基度"排（残基度 = 与目标的最大公共子结构占比）
            #   动机：R1 残基路线是最大头（138~164 次），"一步到位"时仍会命中
            #        —— 把目标换个基团 + 一个可买小分子，就成了一条「路线」。
            #   做法：让【拆得干净】的方案优先成路，换基团类排后面。
            #   ⚠ 性能：MCS 很贵，实测全量算会让耗时从 417s 涨到 647s（+55%）。
            #     所以只对前 mcs_topk 个候选算（默认 40），把成本压回 ~0.4s/目标。
            if self.mcs_topk > 0 and len(scored) > 1:
                head = scored[:self.mcs_topk]
                tail = scored[self.mcs_topk:]
                head.sort(key=lambda x: (not x[0], -x[1],
                                         self._residue_frac(mol, x[2].precursors)))
                scored = head + tail

            for full, n_av, st, avs in scored[:beam]:
                if full:
                    # ★ 路线去重：同一条切断（前体集合相同）只保留一次，
                    #   否则 max_routes=3 可能给出 3 条一模一样的路线（实测过）。
                    sig = (st.reaction_name, st.precursors)
                    if sig in route_sigs:
                        stat["重复路线跳过"] += 1
                        continue
                    route_sigs.add(sig)
                    rt = Route(
                        steps=list(path) + [st],
                        terminals=[f"{p} [{a}]" for p, a in zip(st.precursors, avs)],
                        score=round(1.0 / (len(path) + 1) + 0.5, 4))
                    # ★ ② 化学可用性打分：不可用的路线降权（但仍然返回，标注原因）
                    # ★ 第四十三轮：引擎内传 is_available —— R1 只在前体不可得时才判假
                    ok_u, why_u = route_usability(rt, available_fn=self.is_available)
                    rt.usable = ok_u
                    rt.unusable_reason = why_u
                    if ok_u:
                        stat["可用路线"] += 1
                    else:
                        stat[f"不可用:{why_u}"] += 1
                    routes.append(rt)
            # ★ ③ 多路线：收够 max_routes 条才收口（默认 6 -> 找 1~3 条）
            if len(routes) >= max_routes:
                stat["达路线上限"] += 1
                return
            if depth >= max_depth:
                return

            # 递归：挑要继续拆的前体
            cands = []
            for full, n_av, st, avs in scored[:beam * 8]:
                un = [p for p in st.precursors if not self.is_available(p)]
                # ★ B-2：别去拆"基本等于目标本身"的前体（那是换基团路线，拆它没意义）
                if self.avoid_residue and un:
                    un = [p for p in un if not self._is_residue(mol, p)]
                if not un:
                    continue
                if heuristic >= 3:
                    # ★ ② 改进：优先递归【只差一个前体】的方案（差得越少越可能收口）
                    un.sort(key=lambda s: -Descriptors.MolWt(Chem.MolFromSmiles(s)))
                    cands.append((un[0], st, len(un)))
                else:
                    un.sort(key=lambda s: -Descriptors.MolWt(Chem.MolFromSmiles(s)))
                    cands.append((un[0], st, 0))
            if heuristic >= 3:
                # 缺口小的方案排前面（稳定排序，缺口相同则保持原顺序=分子量优先）
                cands.sort(key=lambda x: x[2])
            seen, picked = set(), []
            for item in cands:
                mol2, st = item[0], item[1]
                if mol2 in seen:
                    continue
                seen.add(mol2)
                picked.append((mol2, st))
                if len(picked) >= beam:
                    break
            stat[f"深度{depth}_递归分支"] += len(picked)
            for mol2, st in picked:
                expand(mol2, path + [st], depth + 1)
                if len(routes) >= max_routes:
                    return

        expand(target, [], 1)
        # ★ ② 排序：可用路线优先，其次步数少
        routes.sort(key=lambda r: (not r.usable, len(r.steps), -len(r.terminals)))
        stat["耗时秒"] = round(time.time() - t0, 2)
        return routes[:max_routes], dict(stat)


# ---------------------------------------------------------------- 正向验证
def forward_validate(step: Step) -> Optional[bool]:
    """把前体喂回 SmartReact 正向引擎，看能否产出目标。"""
    from smartreact import ReactionEnumerator
    global _ENUM
    try:
        _ENUM
    except NameError:
        _ENUM = ReactionEnumerator()
    pres = list(step.precursors)
    if len(pres) < 2:
        return None      # 单前体（分子内）暂不验证
    try:
        res = _ENUM.enumerate_pair(pres[0], pres[1])
    except Exception:
        return None
    tgt = step.target
    for r in res:
        for p in r.products:
            if canon(p) == tgt:
                return True
    return False


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    if os.environ.get("CHRISTOS_RESEARCH_MODE") != "1":
        print("公开版已关闭任意目标逆合成路线；内部研究请设置 CHRISTOS_RESEARCH_MODE=1。")
        raise SystemExit(3)
    import argparse
    _ap = argparse.ArgumentParser(description="逆合成最小闭环")
    _ap.add_argument("--blocks", action="store_true",
                     help="把 ① 可购砌块集合并进终止集合（默认开，用 --no-blocks 关）")
    _ap.add_argument("--no-blocks", dest="blocks", action="store_false")
    _ap.add_argument("--with-reagents", action="store_true",
                     help="砌块集合里连试剂/溶剂一起算终点（更宽）")
    _ap.add_argument("--old-templates", action="store_true",
                     help="用旧的 SmartReact 反转模板库（默认用新的 rdchiral 库）")
    _ap.add_argument("--depth", type=int, default=3, help="搜索深度上限（默认 3）")
    _ap.add_argument("--beam", type=int, default=4, help="每层候选数（默认 4）")
    _ap.set_defaults(blocks=True)
    _args = _ap.parse_args()

    print("=" * 94)
    print("逆合成最小闭环自检")
    print("=" * 94)

    t0 = time.time()
    av = load_available()
    print(f"可获得集合(旧): {len(av):,} 个 InChIKey ({time.time()-t0:.1f}s)")

    bf, bs = ({}, {})
    if _args.blocks:
        t0 = time.time()
        bf, bs = load_purchasable_blocks(with_reagents=_args.with_reagents)
        print(f"可购砌块(①)  : {len(bf):,} 个 full InChIKey / {len(bs):,} 个骨架"
              f"  ({time.time()-t0:.1f}s)"
              + ("  [含试剂]" if _args.with_reagents else "  [仅核心砌块]"))
    else:
        print("可购砌块(①)  : 未启用")

    t0 = time.time()
    if _args.old_templates:
        tmpl = load_retro_templates()
        from collections import Counter
        by_type = Counter(t.name for t in tmpl)
        print(f"逆合成模板(旧): {len(tmpl):,} 条（正向模板反转，{len(by_type)} 种类型）"
              f"  ({time.time()-t0:.1f}s)")
    else:
        tmpl = load_rdchiral_templates()
        print(f"逆合成模板(新): {len(tmpl):,} 条（ORD 逆方向抽取 + 反应中心聚类）"
              f"  ({time.time()-t0:.1f}s)")

    eng = RetroSearch(tmpl, av, verbose=True, blocks_full=bf, blocks_skel=bs)

    # ---------- 先做机制正确性核对 ----------
    # CCNC(C)=O 的已知正向制法：乙酸 + 乙胺（我们之前在正向引擎里见过）
    print()
    print("=" * 94)
    print("机制核对：目标 CCNC(C)=O 的逆合成切断方案")
    print("（已知正确答案：CC(=O)O + CCN，来自 amide_coupling）")
    print("=" * 94)
    dis = eng.disconnections("CCNC(C)=O")
    want = {canon("CC(=O)O"), canon("CCN")}
    hit = [s for s in dis if set(s.precursors) == want]
    print(f"   共 {len(dis)} 个切断方案")
    print(f"   ★ 是否找到已知答案 {'CC(=O)O + CCN'}：{'✓ 找到' if hit else '✗ 没找到'}")
    if hit:
        print(f"      命中模板类型: {hit[0].reaction_name}")
    # 看看这 402 个方案里前体的可获得性
    n_all_av = sum(1 for s in dis if all(eng.is_available(p) for p in s.precursors))
    n_any_av = sum(1 for s in dis if any(eng.is_available(p) for p in s.precursors))
    print(f"   其中【全部前体都可获得】的 {n_all_av} 个；"
          f"【有任一前体可获得】的 {n_any_av} 个")
    print(f"   前 6 个方案（标注前体是否在可获得集合里）：")
    for s in dis[:6]:
        tags = [f"{p}{'✓' if eng.is_available(p) else '✗'}" for p in s.precursors]
        print(f"      [{s.reaction_name:<24}] {tags}")
    print(f"   已知答案那个方案的前体可获得性：")
    for p in sorted(want):
        print(f"      {p:<20} -> {eng.is_available(p) or '✗ 不在可获得集合'}")

    # 目标选一个我们【已知正向能产出】的分子，便于核对
    TARGETS = ["CCNC(C)=O", "O=C(NCCc1ccc(O)cc1)c1ccccc1O"]
    for tgt in TARGETS:
        print()
        print("=" * 94)
        print(f"目标: {tgt}   （{rdMolDescriptors.CalcMolFormula(Chem.MolFromSmiles(tgt))}, "
              f"MW {Descriptors.MolWt(Chem.MolFromSmiles(tgt)):.1f}）")
        print("=" * 94)
        t0 = time.time()
        routes, stat = eng.search(tgt, max_depth=_args.depth, beam=_args.beam)
        print(f"搜索耗时 {time.time()-t0:.1f}s   统计: {stat}")
        if not routes:
            print("   ✗ 没找到完整路线")
            continue
        for i, rt in enumerate(routes[:3], 1):
            print(f"\n   路线 {i}（{len(rt.steps)} 步）:")
            for j, st in enumerate(rt.steps, 1):
                fv = forward_validate(st)
                mark = {True: "✓正向验证通过", False: "✗正向验证失败",
                        None: "—未验证"}[fv]
                print(f"      {j}. [{st.reaction_name}]")
                print(f"         目标 {st.target[:56]}")
                print(f"         前体 {list(st.precursors)}   {mark}")
            print(f"      终点: {rt.terminals}")
