#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""学习型重排序（可选，默认关闭）。

为什么会有这个模块
------------------
引擎是知识驱动的：模板 + 规则，产物可追溯，但从来没有学过"这么多候选里哪个最像正确答案"。
第 128 轮的离线实验证明瓶颈在排序 —— 候选内上限 92.56%，按发射序 top-1 只有 42.71%。

本模块把那个实验搬进生产路径，**只改顺序，不改候选集合**：
每个反应枚举完之后，用离线训练好的梯度提升树给候选打分并重排。

口径（与 `tools/build_rank_dataset.py` 严格一致，否则模型会错）
--------------------------------------------------------------
特征 10 个数值 + 规则族 one-hot：

    rank      候选在**重排前**发射序里的位置（0 起）
    log_sup   log1p(模板 support)，模板来自 mined 库统计
    act       条件激活分
    eng       引擎自身分数
    ext       反应进程标注
    cur       是否 curated 规则
    byp       是否伴生产物
    prod_ha   候选重原子数
    src_ha    底物重原子数（双底物 = 两个底物之和）
    keep      prod_ha / src_ha

**真产物不参与打分**，只用于离线训练时的标签。

安全策略
--------
- 模型文件缺失、损坏、特征长度不符、任何异常 → **静默退回发射序**（打印一次警告）。
- 默认关闭：`RunSpec.rerank = False`，CLI 用 `--rerank` 打开。
- 已记录的局限：训练集是 USPTO-50k，TCM 侧没有训练数据；跨类别泛化只有 2.24 倍（绝对 19.3%）。
"""
from __future__ import annotations

import json
import math
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
# v4：v2 的 59 维模型 + 模板命中率后处理。官方 4,993 条 top-1 73.72%（v2 72.62%，
# McNemar p=0.0002），去污染子集 73.24%（v2 72.19%）。见第一百五十三轮报告。
DEFAULT_MODEL = ROOT / "reports" / "rank_model_v4.pkl"
# v3 / v5（61 维，把模板统计当特征）内部有效但官方集崩到 26–66%，**不要设默认**；
# 它们的问题是同一类：依赖表内统计分布，不跨引擎配置迁移。见第一百五十二/一百五十四轮。
SUPPORT_JSONL = ROOT / "reports" / "mined_forward_templates_full_s5.jsonl"
RULES_JSON = ROOT / "rules" / "rules.json"

_WARNED = {"model": False, "support": False, "extent": False}


def _ha(smiles: str) -> int:
    if not smiles:
        return 0
    try:
        from rdkit import Chem
        m = Chem.MolFromSmiles(smiles)
        return m.GetNumHeavyAtoms() if m else 0
    except Exception:
        return 0


_DESC_CACHE: Dict[str, List[float]] = {}


def _desc(smiles: str) -> List[float]:
    """单分子 8 个结构量，顺序必须与 tools/train_ranker_v2.py 的 desc() 一致：
    [重原子, 环数, 芳环数, 立体中心, 氢键供体, 氢键受体, 分子量/100, 碎片数]。"""
    if not smiles:
        return [0.0] * 8
    hit = _DESC_CACHE.get(smiles)
    if hit is not None:
        return hit
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
        m = Chem.MolFromSmiles(smiles)
        if m is None:
            out = [0.0] * 8
        else:
            out = [
                float(m.GetNumHeavyAtoms()),
                float(rdMolDescriptors.CalcNumRings(m)),
                float(rdMolDescriptors.CalcNumAromaticRings(m)),
                float(rdMolDescriptors.CalcNumAtomStereoCenters(m)),
                float(rdMolDescriptors.CalcNumHBD(m)),
                float(rdMolDescriptors.CalcNumHBA(m)),
                float(Descriptors.MolWt(m)) / 100.0,
                float(len(smiles.split("."))),
            ]
    except Exception:
        out = [0.0] * 8
    if len(_DESC_CACHE) < 20000:
        _DESC_CACHE[smiles] = out
    return out


def load_support_map(path: Optional[Path] = None) -> Dict[str, int]:
    sup: Dict[str, int] = {}
    p = Path(path) if path else SUPPORT_JSONL
    try:
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                t = d.get("template") or ""
                if t:
                    sup[t] = int(d.get("support") or 0)
    except Exception:
        if not _WARNED["support"]:
            print("[rerank] 读不到模板 support 表，sup 特征按 0 处理：%s" % p, file=sys.stderr)
            _WARNED["support"] = True
    return sup


def load_curated_ids(path: Optional[Path] = None) -> set:
    p = Path(path) if path else RULES_JSON
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {r.get("id") for r in (d.get("rules") or []) if r.get("id")}
    except Exception:
        return set()


class Reranker:
    """加载离线模型；每次 `step` 结束后调用 `reorder`。"""

    def __init__(self, model_path: Optional[str] = None):
        self.path = Path(model_path) if model_path else DEFAULT_MODEL
        self.ok = False
        self.model = None
        self.features: List[str] = []
        self.top_rules: List[str] = []
        self.curated_ids: set = set()
        self.meta: Dict[str, Any] = {}
        # v3：模板先验（只在 train 切分上统计；统计量随模型一起发布）
        self.tpl_stats: Dict[str, Tuple[int, int]] = {}
        self.tpl_alpha: float = 20.0
        self.tpl_prior: float = 0.0
        # v4：把模板命中率当**后处理**与模型分数混合（不改特征）。
        # 直接当特征喂 GBM 会在官方集崩到 27.5%（第一百五十二轮）。
        self.blend_hitrate: float = 0.0
        self.sup = load_support_map()
        self._ext_cache: Dict[Tuple[Any, ...], float] = {}
        try:
            with self.path.open("rb") as f:
                blob = pickle.load(f)
            self.model = blob["model"]
            self.features = list(blob.get("features") or [])
            self.top_rules = list(blob.get("top_rules") or [])
            self.curated_ids = set(blob.get("curated_ids") or [])
            self.meta = dict(blob.get("meta") or {})
            self.tpl_stats = dict(blob.get("tpl_stats") or {})
            self.tpl_alpha = float(blob.get("tpl_alpha") or 20.0)
            self.tpl_prior = float(blob.get("tpl_prior") or 0.0)
            self.blend_hitrate = float(blob.get("blend_hitrate") or 0.0)
            # ★ 2026-11-13：加载自检。特征名单与模型维数不一致时**拒绝启用**，
            #   不再静默退回发射序（v5 开发期踩过：91 vs 61 导致基准白跑）。
            n_model = getattr(self.model, "n_features_in_", None)
            if self.features and n_model is not None and int(n_model) != len(self.features):
                print("[rerank] 致命：模型特征维数 %d 与特征名单 %d 不一致（%s），停用重排序"
                      % (int(n_model), len(self.features), self.path.name),
                      file=sys.stderr)
                self.ok = False
            elif self.blend_hitrate > 0.0 and not self.tpl_stats:
                print("[rerank] 致命：blend_hitrate=%.2f 但没有模板统计（%s），停用重排序"
                      % (self.blend_hitrate, self.path.name), file=sys.stderr)
                self.ok = False
            else:
                self.ok = True
        except FileNotFoundError:
            if not _WARNED["model"]:
                print("[rerank] 模型不存在（%s），保持发射序" % self.path, file=sys.stderr)
                _WARNED["model"] = True
        except Exception as exc:  # 损坏 / 版本不符 / 缺依赖
            if not _WARNED["model"]:
                print("[rerank] 模型加载失败（%s），保持发射序：%s" % (type(exc).__name__, exc), file=sys.stderr)
                _WARNED["model"] = True

    # ---------- 特征 ----------
    @staticmethod
    def _cond_key(cond: Any) -> Tuple[Any, ...]:
        """extent 依赖条件，缓存键必须带上条件。

        第 144 轮修 C6：旧实现只按规则 id 缓存，同一进程里先跑 25 °C 再跑 150 °C
        会拿到同一个 extent（按 Ea=103.6 估算约差 3.5e4 倍）。
        """
        def _g(name: str, default: Any) -> Any:
            v = getattr(cond, name, default)
            return default if v is None else v
        def _r(name: str, default: float, nd: int) -> float:
            try:
                return round(float(_g(name, default)), nd)
            except (TypeError, ValueError):
                return float(default)
        return (_r("temperature", 25.0, 2),
                _r("time_min", 60.0, 3),
                _r("pH", 7.0, 2),
                _r("pressure_atm", 1.0, 3),
                _r("concentration_M", 0.1, 4),
                str(_g("solvent", "") or ""),
                str(_g("catalyst", "") or ""),
                str(_g("atmosphere", "") or ""))

    def _extent_of(self, eng: Any, rule: str, cond: Any) -> float:
        key = (rule,) + self._cond_key(cond)
        if key in self._ext_cache:
            return self._ext_cache[key]
        val = 1.0
        try:
            import extent as _extent
            entry = (getattr(eng, "cond_table", {}).get(rule)
                     or getattr(eng, "curated_cond_table", {}).get(rule)
                     or getattr(eng, "mined_top_cond_table", {}).get(rule))
            per = _extent.extent_from_table(entry, cond, None)
            val = float(per[0])
        except Exception:
            if not _WARNED["extent"]:
                print("[rerank] extent 取不到，按 1.0 处理（不影响排序主线索）", file=sys.stderr)
                _WARNED["extent"] = True
        self._ext_cache[key] = val
        return val

    def _features_of(self, products: Sequence[Any], eng: Any, cond: Any) -> List[List[float]]:
        rows: List[List[float]] = []
        # ★ 第 145 轮：特征按模型自带的 features 列表逐项取值 ——
        #   这样「9 个旧特征」和「9+5 条件特征」两种模型都能跑，不必改模型文件。
        _names = list(self.features or [])
        _use_named = bool(_names)
        # v5：同一反应内每个模板产出多少个候选（模板越"滥"越不可信）
        _tpl_counts: Dict[str, int] = {}
        for _p in products:
            _t = getattr(_p, "template_smarts", "") or ""
            _tpl_counts[_t] = _tpl_counts.get(_t, 0) + 1
        for i, p in enumerate(products):
            cs = getattr(p, "smiles", "") or ""
            tpl = getattr(p, "template_smarts", "") or ""
            rule = getattr(p, "rule_id", "") or ""
            pha = _ha(cs)
            ssrc = getattr(p, "source_smiles", "") or ""
            spar = getattr(p, "partner_smiles", "") or ""
            shr = _ha(ssrc) + (_ha(spar) if spar else 0)
            if _use_named:
                _fit = float(getattr(p, "condition_fit", 1.0) or 1.0)
                _tm = float(getattr(cond, "time_min", 60.0) or 60.0)
                # v3 模板先验：与 tools/train_ranker_v3.py 的 tpl_feats 同公式
                _st = self.tpl_stats.get(tpl)
                if _st is None:
                    _hr, _hn = self.tpl_prior, 0
                else:
                    _hn = int(_st[1])
                    _hr = (float(_st[0]) + self.tpl_alpha * self.tpl_prior) / (_hn + self.tpl_alpha)
                vals = {
                    "rank": float(i),
                    "log_sup": math.log1p(float(self.sup.get(tpl, 0))),
                    "act": float(getattr(p, "activation", 0.0) or 0.0),
                    "ext": self._extent_of(eng, rule, cond),
                    "cur": 1.0 if rule in self.curated_ids else 0.0,
                    "byp": 1.0 if getattr(p, "is_byproduct", False) else 0.0,
                    "prod_ha": float(pha),
                    "src_ha": float(shr),
                    "keep": (pha / shr) if shr else 0.0,
                    "t_C": float(getattr(cond, "temperature", 0.0) or 0.0),
                    "log_time": math.log10(max(0.1, _tm)),
                    "fit": _fit,
                    "is_water": 1.0 if str(getattr(cond, "solvent", "") or "") == "water" else 0.0,
                    "has_cat": 1.0 if str(getattr(cond, "catalyst", "") or "") else 0.0,
                    "eng": float(getattr(p, "score", 0.0) or 0.0),
                    "tpl_hitrate": _hr,
                    "tpl_hitrate_n": math.log1p(_hn),
                    "tpl_in_rxn": math.log1p(_tpl_counts.get(tpl, 1)),
                    "rank_frac_tpl": float(i) / max(1, _tpl_counts.get(tpl, 1)),
                }
                # v2 的产物级 / 底物级结构量（与 tools/train_ranker_v2.py 的 desc() 同序）
                dp = _desc(cs)
                ds = _desc(("%s.%s" % (ssrc, spar)) if spar else ssrc)
                vals.update({
                    "p_rings": dp[1], "p_arom": dp[2], "p_stereo": dp[3],
                    "p_hbd": dp[4], "p_hba": dp[5], "p_mw": dp[6], "p_frags": dp[7],
                    "s_rings": ds[1], "s_arom": ds[2], "s_stereo": ds[3],
                    "s_hbd": ds[4], "s_hba": ds[5], "s_mw": ds[6], "s_frags": ds[7],
                    "d_ha": dp[0] - ds[0], "d_rings": dp[1] - ds[1],
                    "d_arom": dp[2] - ds[2], "d_stereo": dp[3] - ds[3],
                    "d_hbd": dp[4] - ds[4], "d_hba": dp[5] - ds[5],
                })
                rows.append([(1.0 if rule == n[5:] else 0.0) if n.startswith("rule:")
                             else float(vals.get(n, 0.0)) for n in _names])
                continue
            base = [
                float(i),
                math.log1p(float(self.sup.get(tpl, 0))),
                float(getattr(p, "activation", 0.0) or 0.0),
                self._extent_of(eng, rule, cond),
                1.0 if rule in self.curated_ids else 0.0,
                1.0 if getattr(p, "is_byproduct", False) else 0.0,
                float(pha),
                float(shr),
                (pha / shr) if shr else 0.0,
            ]
            for r in self.top_rules:
                base.append(1.0 if rule == r else 0.0)
            rows.append(base)
        return rows

    # ---------- 排序 ----------
    def _hitrate_of(self, tpl: str) -> float:
        st = self.tpl_stats.get(tpl)
        if st is None:
            return self.tpl_prior
        n = int(st[1])
        return (float(st[0]) + self.tpl_alpha * self.tpl_prior) / (n + self.tpl_alpha)

    def _blend(self, products: Sequence[Any], proba) -> List[float]:
        """反应内百分位混合：score = (1-λ)·pct(proba) + λ·pct(模板命中率)。"""
        n = len(products)
        hr = [self._hitrate_of(getattr(p, "template_smarts", "") or "") for p in products]

        def pct(vals):
            order = sorted(range(n), key=lambda i: (vals[i], i))
            out = [0.0] * n
            for r, i in enumerate(order):
                out[i] = r / (n - 1)
            return out

        pv = pct([float(x) for x in proba])
        ph = pct(hr)
        lam = self.blend_hitrate
        return [(1.0 - lam) * pv[i] + lam * ph[i] for i in range(n)]

    def reorder(self, products: List[Any], eng: Any, cond: Any) -> List[Any]:
        if not self.ok or len(products) < 2:
            return products
        try:
            feats = self._features_of(products, eng, cond)
            if self.features and len(self.features) != len(feats[0]):
                print("[rerank] 致命：实际特征行 %d 维与名单 %d 维不一致，停用重排序"
                      % (len(feats[0]), len(self.features)), file=sys.stderr)
                self.ok = False
                return products
            proba = self.model.predict_proba(feats)[:, 1]
            if self.blend_hitrate > 0.0 and self.tpl_stats:
                score = self._blend(products, proba)
            else:
                score = [float(x) for x in proba]
            order = sorted(range(len(products)), key=lambda k: (-float(score[k]), k))
            return [products[k] for k in order]
        except Exception as exc:
            if not _WARNED["model"]:
                print("[rerank] 打分失败，保持发射序：%s" % exc, file=sys.stderr)
                _WARNED["model"] = True
            return products


def load(model_path: Optional[str] = None) -> Optional[Reranker]:
    r = Reranker(model_path)
    return r if r.ok else None
