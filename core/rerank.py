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
DEFAULT_MODEL = ROOT / "reports" / "rank_model_20261107.pkl"
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
        self.sup = load_support_map()
        self._ext_cache: Dict[str, float] = {}
        try:
            with self.path.open("rb") as f:
                blob = pickle.load(f)
            self.model = blob["model"]
            self.features = list(blob.get("features") or [])
            self.top_rules = list(blob.get("top_rules") or [])
            self.curated_ids = set(blob.get("curated_ids") or [])
            self.meta = dict(blob.get("meta") or {})
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
    def _extent_of(self, eng: Any, rule: str, cond: Any) -> float:
        if rule in self._ext_cache:
            return self._ext_cache[rule]
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
        self._ext_cache[rule] = val
        return val

    def _features_of(self, products: Sequence[Any], eng: Any, cond: Any) -> List[List[float]]:
        rows: List[List[float]] = []
        for i, p in enumerate(products):
            cs = getattr(p, "smiles", "") or ""
            tpl = getattr(p, "template_smarts", "") or ""
            rule = getattr(p, "rule_id", "") or ""
            pha = _ha(cs)
            ssrc = getattr(p, "source_smiles", "") or ""
            spar = getattr(p, "partner_smiles", "") or ""
            shr = _ha(ssrc) + (_ha(spar) if spar else 0)
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
    def reorder(self, products: List[Any], eng: Any, cond: Any) -> List[Any]:
        if not self.ok or len(products) < 2:
            return products
        try:
            feats = self._features_of(products, eng, cond)
            if self.features and len(self.features) != len(feats[0]):
                return products
            proba = self.model.predict_proba(feats)[:, 1]
            order = sorted(range(len(products)), key=lambda k: (-float(proba[k]), k))
            return [products[k] for k in order]
        except Exception as exc:
            if not _WARNED["model"]:
                print("[rerank] 打分失败，保持发射序：%s" % exc, file=sys.stderr)
                _WARNED["model"] = True
            return products


def load(model_path: Optional[str] = None) -> Optional[Reranker]:
    r = Reranker(model_path)
    return r if r.ok else None
