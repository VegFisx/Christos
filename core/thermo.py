# -*- coding: utf-8 -*-
"""
chemreact 核心：热力学层（接 xTB）
==================================

把项目里那个**没人调用的孤儿模块** `D:\\TCMAI\\src\\thermo_xtb.py` 接上，
用它算的真量子化学 ΔG 替换掉 scorer.py 里 `stability` 那个占位实现。

★ 三条纪律（都是踩过或差点踩的坑）

  1. **绝不往用户项目里写文件。**
     `thermo_xtb.py` 的 `CACHE_DIR` 硬编码指向 `D:\\TCMAI\\data\\xtb_cache`。
     本模块 import 后**立刻**把 CACHE_DIR 改到暂存区，再开始算。
     否则每算一个分子就往用户项目里塞一个 json。

  2. **预算必须按【次数】，不能按【时间】。**
     `--ohess` 是频率计算，很慢（单分子几秒到几分钟）。
     级联动辄几百个产物，不设限地全算会把程序挂死。

     ★ 但限制要用 max_computations（次数），不要用 budget_sec（墙钟）★
     按时间限制会让结果依赖机器负载：机器越忙、超预算越早、
     回退到启发式的分子越多，**同一批输入给出不同的分数和排序**。
     这和 rdchiral 用 set 收集产物（PYTHONHASHSEED 事故）是同一类问题。
     budget_sec 现在默认 None（关闭），只作紧急刹车用。

  3. **只给 top-k 算，不给全量算。**
     先按启发式打分排序，取前 k 个再上 xTB。
     这与 thermo_xtb.py 原本的用法一致，也是唯一可行的用法。

★ 方法学提醒（必须说清楚，免得过度解读数值）

  · GFN2-xTB 是**半经验**方法，ΔG 误差量级 ±10~20 kJ/mol，不能当精确值用。
  · `--ohess` 给的是**气相谐振子近似**的自由能，`--gbsa water` 只是隐式溶剂化修正，
    不等于真实水相自由能。
  · 所以本模块只把它当作**排序信号**（谁比谁更有利），不当**判据**（能不能发生）。

★★ 一个会系统性影响排序的已知局限：水解 —— 已处理 ★★

  实测（tools/refine_hydrolysis_boundary.py）：

      酯水解     +13.2 kJ/mol      糖苷水解   +11.0
      酰胺水解   +34.6             亚胺水解   +13.0
      内酰胺开环 +88.3

  而化学上这些在水溶液里都应该是【略负】的（乙酸乙酯实测 ≈ -4）。
  原因：气相计算没有水的溶剂化驱动，水解在气相里本来就不利。

  边界（实测）：
    ✗ 水【切断】一根键（酯/糖苷/酰胺/亚胺/内酰胺/硫酸酯/磷酸酯/缩醛/半缩醛）
       → 由溶剂化熵驱动，气相算不出，**符号系统性错误**
    ✓ 水【加成】上去（烯烃水合 -69.3、烯酮水合 -15.4）
      ✓ 张力释放型开环（环氧化物开环 -28.5）
       → 由键能/张力驱动，气相算得准

  处置：这 9 条规则在 rules.json 里标了 `thermo_unreliable: true`，
        scorer.assign_thermo 会【跳过】它们 ——
        不让一个已知系统性错误的信号去压低糖苷/酯水解产物
        （而这两类恰恰是中药煎煮里最常发生的反应）。

  知识写在【规则库】里而不是代码里，所以跟着数据走。
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rdkit import Chem

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent

# Optional xTB backend.  Set CHRISTOS_XTB to the xTB executable and
# CHRISTOS_TCMAI_SRC to the directory that holds ``thermo_xtb.py``.  If the
# executable is absent the whole layer marks itself unavailable and the rest of
# the pipeline keeps running without Delta-G estimates -- this is the normal
# state for anyone who has not installed xTB.
TCMAI_SRC = Path(os.environ.get("CHRISTOS_TCMAI_SRC", r"D:\TCMAI\src"))
TCMAI_XTB = Path(os.environ.get(
    "CHRISTOS_XTB", r"D:\TCMAI\tools\xtb\xtb-6.7.1\bin\xtb.exe"))

# 缓存放暂存区，不放用户项目
DEFAULT_CACHE = _STAGE / "xtb_cache"

# 分子式 → SMILES（用于补全陪跑试剂，让 ΔG 的原子守恒检查能通过）
FORMULA_TO_SMILES = {
    "H2O": "O",
    "O2": "O=O",
    "H2": "[H][H]",
    "CO2": "O=C=O",
    "NH3": "N",
    "CH4O": "CO",
    "CH4": "C",
    "CO": "[C-]#[O+]",
    "H2O2": "OO",
}

# ΔG → 分数 的映射阈值（kJ/mol）。文档化的建模选择，不是实验测定值。
DG_FAVORABLE = -30.0     # 更负 → 1.0
DG_UNFAVORABLE = 20.0    # 更正 → 0.0

# ★ 实测教训：大分子的 xTB 自由能不可靠且极慢。
# 实测中一个 40+ 重原子的乌头碱衍生物给出了 +300 kJ/mol 的荒唐 ΔG——
# 原因是柔性大分子的构象搜索（ETKDG + MMFF）找不到好构象，
# 再叠加上气相 RRHO 的谐振近似，结果就崩了。
MAX_HEAVY_FOR_XTB = 45

# ★ ΔG 合理性区间：超出就判为不可靠，宁可不给分，也不给一个错的数。
DG_SANE_MIN = -250.0
DG_SANE_MAX = 150.0


@dataclass
class ThermoStats:
    requested: int = 0
    computed: int = 0
    cache_hits: int = 0
    failures: int = 0
    budget_exhausted: int = 0     # 达到【次数】上限
    emergency_stop: int = 0       # 触到【时间】紧急刹车
    too_big: int = 0
    insane_dg: int = 0
    seconds: float = 0.0

    def summary(self) -> str:
        return (f"请求 {self.requested} / 新算 {self.computed} / 命中缓存 {self.cache_hits} "
                f"/ 失败 {self.failures} / 超次数上限 {self.budget_exhausted} "
                f"/ 紧急刹车 {self.emergency_stop} "
                f"/ 分子过大跳过 {self.too_big} / ΔG 不合理 {self.insane_dg} "
                f"/ 耗时 {self.seconds:.1f}s")


# 分子缓存（本地，避免循环导入）
_MOL_CACHE: Dict[str, Any] = {}


def _mol_of(smiles: str):
    """本地分子缓存，避免为了数重原子去 import engine（会绕成循环导入）。"""
    if smiles not in _MOL_CACHE:
        m = Chem.MolFromSmiles(smiles)
        _MOL_CACHE[smiles] = m
    return _MOL_CACHE[smiles]


class Thermo:
    """xTB 热力学接入层。不可用时优雅降级（返回 None，上层回退启发式）。"""

    def __init__(self,
                 cache_dir: Optional[Path] = None,
                 budget_sec: Optional[float] = None,
                 n_conf: int = 3,
                 enabled: bool = True,
                 max_computations: int = 300):
        """
        budget_sec        【紧急刹车】墙钟上限，**默认 None = 关闭**。
                          ★ 打开它会让结果依赖机器负载 ★
                          同一批输入，机器忙的时候会更早停下、更多分子回退启发式，
                          分数和排序就跟着变。要可复现就别打开。
                          它已经【不是】限制运行时间的主要手段了——
                          max_computations 就已经把总时间限定住了
                          （300 个分子 × 每个 1~2 秒 ≈ 5~10 分钟）。
        max_computations  ★ 正常的量限制（默认 300）★
                          按【次数】而不是【时间】→ 结果可复现。
        """
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE
        self.budget_sec = None if budget_sec is None else float(budget_sec)
        self.n_conf = int(n_conf)
        self.max_computations = int(max_computations)
        self.stats = ThermoStats()
        self._t0 = time.time()
        self._n_new = 0            # 本次新算了多少个（不含缓存命中）
        self._mod = None
        self._ok = False

        if not enabled:
            return
        if not TCMAI_XTB.exists():
            return

        try:
            if str(TCMAI_SRC) not in sys.path:
                sys.path.insert(0, str(TCMAI_SRC))
            import thermo_xtb as mod

            # ★ 第一件事：把缓存目录挪走，别往用户项目里写
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            mod.CACHE_DIR = self.cache_dir
            self._mod = mod
            self._ok = True
        except Exception:
            self._ok = False

    # ------------------------------------------------------------ 状态

    @property
    def available(self) -> bool:
        return self._ok

    def _budget_left(self) -> float:
        return self.budget_sec - (time.time() - self._t0)

    def _cached(self, smiles: str) -> bool:
        if self._mod is None:
            return False
        key = self._mod._inchikey(smiles)
        return bool(key) and (self.cache_dir / f"{key}.json").exists()

    # ------------------------------------------------------------ 单分子

    def gibbs(self, smiles: str) -> Optional[float]:
        """分子 G°(T)，单位 Hartree。带缓存、预算控制、分子大小闸门。"""
        if not self._ok:
            return None
        self.stats.requested += 1

        # ★ 大分子闸门：xTB 的 RRHO 自由能对柔性大分子不可靠（实测出过 +300 kJ/mol）
        mol = _mol_of(smiles)
        if mol is not None and mol.GetNumHeavyAtoms() > MAX_HEAVY_FOR_XTB:
            self.stats.too_big += 1
            return None

        was_cached = self._cached(smiles)
        # ★★ 预算必须【按次数】而不是【按时间】★★
        #
        # 原来是 `self._budget_left() <= 0` —— 看墙钟时间。
        # 那意味着：机器越忙，超预算越早，回退到启发式打分的分子越多，
        # **同一批输入在不同负载下给出不同的分数和排序**。
        #
        # 这和 rdchiral 用 set 收集产物（PYTHONHASHSEED 事故）是同一类问题：
        # 结果依赖运行环境。研究工具必须可复现。
        #
        # 改成按次数：算满 max_computations 个就不再算。
        # 时间预算保留为【紧急刹车】，默认值调到很大，正常跑不会触发。
        if not was_cached:
            if self._n_new >= self.max_computations:
                self.stats.budget_exhausted += 1
                return None
            # 紧急刹车：默认关闭。打开就会让结果依赖机器负载，见 __init__ 说明。
            if self.budget_sec is not None and self._budget_left() <= 0:
                self.stats.emergency_stop += 1
                return None

        t0 = time.time()
        try:
            g = self._mod.get_g(smiles, n_conf=self.n_conf, verbose=False)
        except Exception:
            g = None
        self.stats.seconds += time.time() - t0

        if g is None:
            self.stats.failures += 1
            return None
        if was_cached:
            self.stats.cache_hits += 1
        else:
            self.stats.computed += 1
            self._n_new += 1
        return g

    # ------------------------------------------------------------ 配平

    def build_equation(self, rule: Dict[str, Any], substrate_smiles: str,
                       product_smiles: Sequence[str],
                       ) -> Optional[Tuple[List[str], List[str]]]:
        """把「底物 + co_reagents → 产物 + byproducts」拼成可算 ΔG 的两侧。

        配平系数可能是小数（比如 O2: 0.5），要把整个方程乘到整数。
        """
        co = dict(rule.get("co_reagents") or {})
        by = dict(rule.get("byproducts") or {})

        # 收集所有系数，找最小分母
        coeffs = [1.0] + list(co.values()) + list(by.values())
        mult = 1
        for c in coeffs:
            for denom in (2, 3, 4, 5, 6):
                scaled = c * denom
                if abs(scaled - round(scaled)) < 1e-9:
                    mult = max(mult, denom)
                    break

        reactants: List[str] = [substrate_smiles] * mult
        products: List[str] = []
        for s in product_smiles:
            products.extend([s] * mult)

        for formula, n in co.items():
            smi = FORMULA_TO_SMILES.get(formula)
            if smi is None:
                return None
            reactants.extend([smi] * int(round(n * mult)))
        for formula, n in by.items():
            smi = FORMULA_TO_SMILES.get(formula)
            if smi is None:
                return None
            products.extend([smi] * int(round(n * mult)))

        return reactants, products

    # ------------------------------------------------------------ 反应 ΔG

    def reaction_dg(self, reactants: Sequence[str],
                    products: Sequence[str]) -> Optional[float]:
        """反应 ΔG (kJ/mol)。任一分子算不出来就返回 None。"""
        if not self._ok:
            return None
        gR = []
        for s in reactants:
            g = self.gibbs(s)
            if g is None:
                return None
            gR.append(g)
        gP = []
        for s in products:
            g = self.gibbs(s)
            if g is None:
                return None
            gP.append(g)
        dg = (sum(gP) - sum(gR)) * 2625.5     # Hartree → kJ/mol

        # ★ 合理性闸门：半经验方法在大/柔性分子上会给出荒唐值（实测出过 +300 kJ/mol）。
        # 宁可不给分，也不把错的数喂给排序。
        if not (DG_SANE_MIN <= dg <= DG_SANE_MAX):
            self.stats.insane_dg += 1
            return None
        return dg


# ---------------------------------------------------------------- ΔG → 分数

def favorability_from_dg(dg_kj: Optional[float]) -> Optional[float]:
    """把反应 ΔG 映射到 0~1。

    阈值（DG_FAVORABLE / DG_UNFAVORABLE）是**文档化的建模选择**，
    不是实验测定值。半经验方法的 ΔG 误差本来就有 ±10~20 kJ/mol，
    所以这里只做**排序信号**用，不要当判据。
    """
    if dg_kj is None:
        return None
    if dg_kj <= DG_FAVORABLE:
        return 1.0
    if dg_kj >= DG_UNFAVORABLE:
        return 0.0
    span = DG_UNFAVORABLE - DG_FAVORABLE
    return round((DG_UNFAVORABLE - dg_kj) / span, 4)
