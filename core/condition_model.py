# -*- coding: utf-8 -*-
r"""D2：条件可行性模型（HTE B-H）的**只打标记**接入组件（2026-10-13）。

口径与边界（写死）：
  * 模型口径 = tools/train_condition_model.py：y = 1 if Yield >= 0.5，
    特征 = solvent/catalyst/base/source one-hot + 8 个 Additive 布尔 + aryl/amine Morgan(r=2,2048)。
  * **只用于训练覆盖的反应类**（TRAINED_CLASSES = ("B-H",)）；其它类一律
    applicable=False，按类降级到规则层（不许外推）。
  * **不打分、不排序、不删产物**：只给「这套条件会不会有产物」的 p + 档位 + 分布外提示。
  * 分布外字段会逐条列出来（词表里没有的取值），因为实测：OOD 输入给的是
    0.8709 这类**常规高分**，不是异常值 —— 不提示就会被误当成可靠分数。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_STAGE = Path(__file__).resolve().parent.parent
for _p in (_STAGE / "core", _STAGE / "rules", _STAGE / "libs", _STAGE / "tools", _STAGE / "sources"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

MODEL_PATH = _STAGE / "models" / "condition_gate_bh.joblib"
TRAINED_CLASSES: Sequence[str] = ("B-H",)
ADD_COLS = ["Additive_" + x for x in
            ("present", "aromatic_rings", "heteroatom_count", "coordination_flag",
             "steric_bulk_flag", "pi_rich_flag", "Pd_poisoning", "competes_with_amine")]
# 档位（第三十七轮建议：不设单一阈值，先切低/中/高）
BAND_LOW = 0.30
BAND_HIGH = 0.70

_CACHE: Dict[str, Any] = {}


def load(model_path: Optional[Path] = None) -> Dict[str, Any]:
    """载入模型 + 词表（只读，缓存）。"""
    key = str(model_path or MODEL_PATH)
    if "model" not in _CACHE or _CACHE.get("path") != key:
        import joblib
        d = joblib.load(key)
        d["path"] = key
        d["_nbits"] = int(d.get("nbits", 2048))
        _CACHE.clear()
        _CACHE.update(d)
    return _CACHE


def available() -> bool:
    return Path(MODEL_PATH).exists()


def vocab() -> Dict[str, List[str]]:
    d = load()
    return {k: sorted(v) for k, v in (d.get("cats") or {}).items()}


def band_of(p: float) -> str:
    if p < BAND_LOW:
        return "低"
    if p <= BAND_HIGH:
        return "中"
    return "高"


def _fp(smiles: str, nbits: int):
    import numpy as np
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdFingerprintGenerator
    RDLogger.DisableLog("rdApp.*")
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=nbits)
    m = Chem.MolFromSmiles(smiles or "")
    if m is None:
        return np.zeros(nbits, dtype=np.float32)
    return np.array(gen.GetFingerprint(m), dtype=np.float32)


def score(solvent: str = "", catalyst: str = "", base: str = "", source: str = "",
          aryl: str = "", amine: str = "", additive: Optional[Sequence[float]] = None,
          reaction: str = "B-H") -> Dict[str, Any]:
    """给一套条件打分（**标记用**，不是门控）。

    返回 dict：applicable / note / p / band / ood / trained_classes
    """
    out: Dict[str, Any] = {"reaction": reaction, "applicable": False, "p": None,
                           "band": None, "ood": [], "trained_classes": list(TRAINED_CLASSES),
                           "model_path": str(MODEL_PATH)}
    if not available():
        out["note"] = "模型文件不存在（跑 tools/train_condition_model.py 生成）"
        return out
    if str(reaction) not in TRAINED_CLASSES:
        out["note"] = ("该类没有模型 -> **按类降级**：只用规则层（模型只在 "
                       + "/".join(TRAINED_CLASSES) + " 上训练过，不许外推）")
        return out
    out["applicable"] = True

    import numpy as np
    d = load()
    cats = d.get("cats") or {}
    vals = {"solvent": solvent, "catalyst": catalyst, "base": base, "source": source}
    parts = []
    ood = []
    for k in ("solvent", "catalyst", "base", "source"):
        v = str(vals.get(k) or "").strip()
        one = np.zeros(len(cats.get(k) or {}), dtype=np.float32)
        idx = (cats.get(k) or {}).get(v)
        if idx is None:
            ood.append(k + "=" + (v if v else "(空)"))
        else:
            one[idx] = 1.0
        parts.append(one)
    add = list(additive) if additive is not None else [0.0] * len(ADD_COLS)
    parts.append(np.array(add, dtype=np.float32))
    nbits = d["_nbits"]
    parts.append(_fp(aryl, nbits))
    parts.append(_fp(amine, nbits))
    X = np.concatenate(parts)[None, :]
    p = float(d["model"].predict_proba(X)[0, 1])
    out["p"] = round(p, 4)
    out["band"] = band_of(p)
    out["ood"] = ood
    if ood:
        out["note"] = ("有 %d 个字段不在训练词表里（**分布外**）：%s。"
                       "实测：这类输入给的是常规高分（约 0.87），不是异常值 —— 分数仅供参考，"
                       "别当门控用。" % (len(ood), "、".join(ood)))
    else:
        out["note"] = "全部字段都在训练词表里；仍只是标记（不删产物、不排序）。"
    return out


def describe() -> str:
    lines = ["条件可行性模型（D2，只打标记）", "  模型：" + str(MODEL_PATH),
             "  覆盖反应类：" + "/".join(TRAINED_CLASSES) + "（其它类按类降级到规则层）"]
    if available():
        d = load()
        lines.append("  训练：" + str(d.get("trained_on", "?")))
        lines.append("  接入状态：wired_into_production=" + str(d.get("wired_into_production", "?")))
        v = vocab()
        lines.append("  词表：solvent %d / catalyst %d / base %d / source %d" %
                     (len(v.get("solvent", [])), len(v.get("catalyst", [])),
                      len(v.get("base", [])), len(v.get("source", []))))
    else:
        lines.append("  模型文件缺失")
    lines.append("  档位：p<%.2f 低 / %.2f~%.2f 中 / >%.2f 高" % (BAND_LOW, BAND_LOW, BAND_HIGH, BAND_HIGH))
    return "\n".join(lines)
