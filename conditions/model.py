# -*- coding: utf-8 -*-
"""
chemreact 条件层：一次"煎煮/提取"的完整条件描述
================================================

这是整个引擎从"玩具"变成"工具"的关键一层。

⚠ 文件名说明：本文件原本叫 schema.py，但 `rules/schema.py` 也叫 schema，
  Python 按模块名缓存，两个同名模块同时 import 时后者会静默拿到前者——是个很难查的坑。
  故改名为 model.py。（等规则模块迁进 core/ 之后，可以再改回 schema.py 以对齐简报的目录结构。）

没有它的时候：23 条规则**无条件全开**，
煎煮（100°C 水）和醇提（78°C 乙醇回流）跑出来**结果一模一样**——
这在化学上是荒谬的。

有了它：条件决定哪些规则被激活、以什么权重参与，
于是"换个煎法，产物清单就变了"。

字段与项目简报 §7 一致。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- 溶剂词表
# ★ 2026-10-11 第十二轮：扩溶剂词表（细类别 + 粗类别 双层）★
#
# 动机（实测，不是推断）：引擎真正加载的 reports/conditions_normalized.json 里，
#   ORD 用的是它自己的 26 个溶剂名（DMF / DCM / THF / toluene / MeCN …）；
#   而旧 SOLVENTS 只有 8 个粗类别，旧 _solvent_class() 把 DMF/DCM/THF/toluene
#   **全部压成 "organic"** -> 只要条件写 organic（或任何有机溶剂）就必然"匹配"，
#   溶剂门控的区分力≈0（见 reports/D-条件门控-报告.md 第 126 行）。
#
# 现在分两层：
#   - 细类别（fine）：thf / dcm / dmf / toluene / mecn …（用户写细的，就按细的判）
#   - 粗类别（coarse）：water / aqueous / alcohol / oil / none / organic
# 匹配规则（solvent_matches）：
#   1) 两边归一后同名 -> 匹配；
#   2) 任一边是【粗类别】且父类相同 -> 匹配（**这是向后兼容的关键**：
#      旧行为下 organic 与 DMF 必然匹配，现在仍然匹配）；
#   3) 两边都是【细类别】且不同 -> 不匹配（**这就是新增的区分力**：
#      thf 不再匹配 "ORD 偏好 toluene"）。
SOLVENT_COARSE = ("water", "aqueous", "alcohol", "oil", "none", "organic")

# 原始写法（小写、去空白后）-> 规范细类别
SOLVENT_ALIAS = {
    # —— 水 / 醇 ——
    "water": "water", "h2o": "water", "distilled water": "water",
    "meoh": "methanol", "methanol": "methanol",
    "etoh": "ethanol", "ethanol": "ethanol",
    "ipa": "isopropanol", "isopropanol": "isopropanol", "2-propanol": "isopropanol",
    "isopropyl alcohol": "isopropanol", "iproh": "isopropanol",
    # —— 醚类 ——
    "thf": "thf", "tetrahydrofuran": "thf",
    "et2o": "et2o", "ether": "et2o", "ethyl ether": "et2o",
    "diethyl ether": "et2o", "dme": "dme", "dimethoxyethane": "dme",
    "1,2-dimethoxyethane": "dme",
    "dioxane": "dioxane", "1,4-dioxane": "dioxane",
    # —— 卤代 ——
    "dcm": "dcm", "ch2cl2": "dcm", "dichloromethane": "dcm",
    "methylene chloride": "dcm",
    "chcl3": "chcl3", "chloroform": "chcl3",
    "dce": "dce", "1,2-dichloroethane": "dce",
    # —— 极性非质子 ——
    "dmf": "dmf", "dimethylformamide": "dmf", "n,n-dimethylformamide": "dmf",
    "dma": "dma", "n,n-dimethylacetamide": "dma",
    "nmp": "nmp", "n-methylpyrrolidone": "nmp", "n-methylpyrrolidinone": "nmp",
    "dmso": "dmso", "mecn": "mecn", "acetonitrile": "mecn",
    "acetone": "acetone",
    # —— 酯 / 烃 / 芳烃 ——
    "etoac": "etoac", "ethyl acetate": "etoac",
    "toluene": "toluene", "benzene": "benzene",
    "hexane": "hexane", "hexanes": "hexane", "petroleum ether": "hexane",
    # —— 碱性 / 酸性 / 盐类（ORD 会把它们写进 solvent 字段，实测）——
    "pyridine": "pyridine", "quinoline": "quinoline",
    "et3n": "et3n", "triethylamine": "et3n",
    "dipea": "dipea", "n,n-diisopropylethylamine": "dipea",
    "acoh": "acoh", "acetic acid": "acoh",
    "nh4cl": "nh4cl", "ammonium chloride": "nh4cl",
    "pocl3": "pocl3", "phosphorus oxychloride": "pocl3",
    # —— 粗类别本身 ——
    "alcohol": "alcohol", "aqueous": "aqueous", "oil": "oil",
    "none": "none", "organic": "organic", "": "none",
}

# 细类别 -> 父（粗）类别。粗类别是自己的父。
SOLVENT_PARENT = {c: c for c in SOLVENT_COARSE}
SOLVENT_PARENT.update({
    "methanol": "alcohol", "ethanol": "alcohol", "isopropanol": "alcohol",
    "thf": "organic", "et2o": "organic", "dme": "organic", "dioxane": "organic",
    "dcm": "organic", "chcl3": "organic", "dce": "organic",
    "dmf": "organic", "dma": "organic", "nmp": "organic", "dmso": "organic",
    "mecn": "organic", "acetone": "organic", "etoac": "organic",
    "toluene": "organic", "benzene": "organic", "hexane": "organic",
    "pyridine": "organic", "quinoline": "organic",
    "et3n": "organic", "dipea": "organic",
    "acoh": "organic", "nh4cl": "organic", "pocl3": "organic",
})

SOLVENT_FINE = tuple(sorted(set(SOLVENT_PARENT) - set(SOLVENT_COARSE)))

# 允许取值（粗 + 细；校验用）
SOLVENTS = set(SOLVENT_PARENT)
CATALYSTS = {None, "acid", "base", "enzyme", "metal", "light"}
ATMOSPHERES = {"air", "O2", "N2", "H2", "vacuum", "CO2"}


def solvent_class(name) -> str:
    """把任意溶剂写法归一成规范类别（细类别优先，认不出兜底 organic —— 与旧版一致）。"""
    if not name:
        return "none"
    s = str(name).strip().lower()
    if s in SOLVENT_ALIAS:
        return SOLVENT_ALIAS[s]
    if s in SOLVENT_PARENT:
        return s
    return "organic"


def is_known_solvent(name) -> bool:
    """这个词表认不认识这个写法？（认不出 -> 校验时给提示，不再静默当 organic）"""
    if name is None:
        return False
    s = str(name).strip().lower()
    return s in SOLVENT_ALIAS or s in SOLVENT_PARENT


def solvent_matches(run_solvent, allowed) -> bool:
    """条件里的溶剂与 ORD 偏好溶剂集合是否相容？

    规则见文件顶部注释：同名匹配；任一边粗类别且父类相同则匹配；
    两边都是细类别且不同则不匹配（新增区分力）。
    """
    if not allowed:
        return True
    g = solvent_class(run_solvent)
    for w0 in allowed:
        w = solvent_class(w0)
        if g == w:
            return True
        if g in SOLVENT_COARSE and SOLVENT_PARENT[g] == SOLVENT_PARENT[w]:
            return True
        if w in SOLVENT_COARSE and SOLVENT_PARENT[w] == SOLVENT_PARENT[g]:
            return True
    return False


@dataclass(frozen=True)
class Conditions:
    """一次处理过程的全部条件。不可变，改条件请用 .with_() 生成新对象。"""

    solvent: str = "water"            # 溶剂
    temperature: float = 100.0        # 摄氏温度
    time_min: float = 60.0            # 处理时长（分钟）
    pH: float = 7.0
    catalyst: Optional[str] = None    # 催化剂
    reagent: Optional[str] = None     # 额外试剂（单个，旧字段，保留兼容）
    # ★ 第十一轮新增：辅助试剂集合（可多个）★
    #   动机：Mitsunobu 需要 PPh3 + DEAD，Suzuki 需要碱 —— 它们不是"催化剂"也不是"溶剂"，
    #   旧模型只能塞进单个 reagent 字段里，门控也没查过它。
    #   数据来源：ORD 里"声明为 REACTANT 但原子没进产物"的组分（见
    #   tools/extract_aux_reagent_coverage.py 的覆盖率统计）。
    reagents: Tuple[str, ...] = ()    # 本批处理里加入的辅助试剂（SMILES 或名字）
    atmosphere: str = "air"           # 气氛：决定氧化/还原反应能不能发生
    pressure_atm: float = 1.0
    concentration_M: float = 0.1

    # ------------------------------------------------------------ 校验

    def validate(self) -> List[str]:
        """返回问题列表，空列表 = 合法。"""
        p: List[str] = []
        if not is_known_solvent(self.solvent):
            p.append(f"未知溶剂 {self.solvent!r}，允许粗类别 {list(SOLVENT_COARSE)} "
                     f"或 {len(SOLVENT_FINE)} 个细类别（{list(SOLVENT_FINE[:8])} …）")
        if self.catalyst not in CATALYSTS:
            p.append(f"未知催化剂 {self.catalyst!r}，允许：{sorted(x for x in CATALYSTS if x)}")
        if self.atmosphere not in ATMOSPHERES:
            p.append(f"未知气氛 {self.atmosphere!r}，允许：{sorted(ATMOSPHERES)}")
        if not (-50 <= self.temperature <= 500):
            p.append(f"温度 {self.temperature} 超出合理范围 [-50, 500] °C")
        if not (0 <= self.pH <= 14):
            p.append(f"pH {self.pH} 超出 [0, 14]")
        if self.time_min <= 0:
            p.append(f"时间必须为正，收到 {self.time_min}")
        if self.pressure_atm <= 0:
            p.append(f"压力必须为正，收到 {self.pressure_atm}")
        if self.concentration_M <= 0:
            p.append(f"浓度必须为正，收到 {self.concentration_M}")
        return p

    # ------------------------------------------------------------ 构造 / 转换

    # ------------------------------------------------------------ 辅助试剂

    def has_reagent(self, smi_or_name: str) -> bool:
        """条件里有没有这个辅助试剂？（先按 SMILES 规范化比对，再退回字符串匹配）

        ★ 第十二轮：规范化一律去立体（isomericSmiles=False）★
        否则 DEAD 的 "/N=N/" 与 "N=N" 两种写法会被当成两个不同试剂（实测，
        见 tools/probe_canon_variants.py）：对"有没有这个试剂"来说这是同一个东西。
        同时补上"组分级"比较：K2CO3 整体 SMILES 与它的碎片 [K+]/碳酸根要能互相认出。
        """
        if not smi_or_name:
            return False
        want_raw = str(smi_or_name).strip()

        def _canon(s: str):
            try:
                from rdkit import Chem
                m = Chem.MolFromSmiles(s)
                if m is None:
                    return None
                for a in m.GetAtoms():
                    a.SetAtomMapNum(0)
                return Chem.MolToSmiles(m, isomericSmiles=False)
            except Exception:
                return None

        want_canon = _canon(want_raw)
        want_parts = {p for p in want_canon.split(".") if p} if want_canon else set()
        for r in (self.reagents or ()) + ((self.reagent,) if self.reagent else ()):
            if not r:
                continue
            s = str(r).strip()
            if s == want_raw:
                return True
            # 名字匹配（不区分大小写、去空格）
            if s.lower().replace(" ", "") == want_raw.lower().replace(" ", ""):
                return True
            got_canon = _canon(s)
            if want_canon and got_canon:
                if want_canon == got_canon:
                    return True
                got_parts = {p for p in got_canon.split(".") if p}
                if want_parts & got_parts:
                    return True
        return False

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Conditions":
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"Conditions 不认识的字段：{sorted(unknown)}")
        return cls(**d)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def with_(self, **changes: Any) -> "Conditions":
        """基于当前条件派生一个新条件，例如 cond.with_(temperature=60)。"""
        return replace(self, **changes)

    # ------------------------------------------------------------ 展示

    def describe(self) -> str:
        bits = [f"{self.solvent}", f"{self.temperature:g}°C", f"{self.time_min:g}min",
                f"pH {self.pH:g}", f"{self.atmosphere}"]
        if self.catalyst:
            bits.append(f"催化:{self.catalyst}")
        if self.reagent:
            bits.append(f"试剂:{self.reagent}")
        return " / ".join(bits)


# 合法的条件字段（供外部校验用）
CONDITION_FIELDS = tuple(Conditions.__dataclass_fields__)
