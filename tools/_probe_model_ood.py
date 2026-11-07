# -*- coding: utf-8 -*-
r"""一次性探针：把【查询侧会遇到的条件】喂给已落盘的条件门控模型，看它是不是分布外。

只回答一个问题：水/无碱这类条件进模型后，模型还输出信息吗？
"""
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import joblib                                       # noqa: E402
import numpy as np                                  # noqa: E402
from rdkit import Chem, RDLogger                    # noqa: E402
from rdkit.Chem import rdFingerprintGenerator       # noqa: E402

RDLogger.DisableLog("rdApp.*")

D = joblib.load(STAGE / "models" / "condition_gate_bh.joblib")
MODEL, CATS, NBITS = D["model"], D["cats"], D["nbits"]
print("模型：%s" % D["trained_on"])
print("类别词表：%s" % {k: len(v) for k, v in CATS.items()})

GEN = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=NBITS)


def fp(sm):
    m = Chem.MolFromSmiles(sm)
    return (np.zeros(NBITS, dtype=np.float32) if m is None
            else np.array(GEN.GetFingerprint(m), dtype=np.float32))


def vec(solvent, catalyst, base, source, aryl, amine, add=None):
    parts, ood = [], []
    for k, v in (("solvent", solvent), ("catalyst", catalyst),
                 ("base", base), ("source", source)):
        one = np.zeros(len(CATS[k]), dtype=np.float32)
        if v in CATS[k]:
            one[CATS[k][v]] = 1.0
        else:
            ood.append("%s=%r" % (k, v))
        parts.append(one)
    parts.append(np.array(add if add else [0.0] * 8, dtype=np.float32))
    parts.append(fp(aryl))
    parts.append(fp(amine))
    return np.concatenate(parts)[None, :], ood


CASES = [
    ("训练分布内（HTE 常见组合）", "DMSO", "cphos-pd-g4", "P2Et", "JNJ HTE 2024"),
    ("查询侧典型：水 / 无催化剂 / 无碱", "water", "empty", "", "(查询入口)"),
    ("查询侧典型：乙醇回流 / 无催化剂 / 无碱", "EtOH", "empty", "", "(查询入口)"),
    ("查询侧典型：煎煮 100C / 水 / 无催化剂 / 无碱", "water", "empty", "", "(查询入口)"),
]

for name, sol, cat, base, src in CASES:
    X, ood = vec(sol, cat, base, src, "c1ccc(Br)cc1", "Nc1ccccc1")
    p = float(MODEL.predict_proba(X)[0, 1])
    print("")
    print("== %s" % name)
    print("   p(有产物) = %.4f   分布外字段：%s" % (p, ood if ood else "无"))
    print("   非零特征数 = %d / %d" % (int((X[0] != 0).sum()), X.shape[1]))

print("")
print("训练集正例率（先验）= 60.3%；若某组输入只反映先验，p 会贴近 0.6。")
