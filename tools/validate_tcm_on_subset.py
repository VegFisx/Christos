"""Re-run the three TCM-side validations against the bundled subset database.

The paper's TCM claims (literature consistency, processed-herb cases, decoction
formulas) were produced against the full `tcm.db`. This repository ships a small
subset containing only the rows those cases touch, so the numbers can be
re-checked without the full database.

Usage::

    python -I tools/validate_tcm_on_subset.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUB = ROOT / "data" / "tcm_subset.db"

SCRIPTS = [
    ("literature", "tools/validate_literature_paths.py"),
    ("paozhi", "tools/validate_paozhi_paths.py"),
    ("formula", "tools/validate_formula_decoction.py"),
]


def main() -> int:
    if not SUB.is_file():
        print("找不到子集库：%s" % SUB)
        print("用 tools/build_tcm_subset.py 从 tcm.db 重新生成。")
        return 2
    env = dict(os.environ)
    env["CHEMCREACT_TCM_DB"] = str(SUB)
    env["PYTHONIOENCODING"] = "utf-8"

    fail = 0
    for label, rel in SCRIPTS:
        print("=" * 60)
        print("[%s] %s" % (label, rel))
        rc = subprocess.call([sys.executable, "-I", rel], cwd=str(ROOT), env=env)
        print("[%s] exit=%d" % (label, rc))
        if rc != 0:
            fail += 1
    print("=" * 60)
    print("失败 %d 个" % fail)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
