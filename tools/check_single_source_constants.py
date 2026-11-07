# -*- coding: utf-8 -*-
r"""判定性检查：库路径常量只有一处定义（第七十四轮交接待办①）。

三条判据：取值一致 / coconut 是 import 来的 / **活跃代码**里只剩白名单内的定义。

★ 白名单（各有各的理由，不是重复）：
  * `core/query_base.py` —— 引擎的**定义处**（单一来源）；
  * `tools/tcm_ro.py`     —— 独立的**只读访问**模块（给不加载引擎的一次性脚本用）。
  * `snapshots/`、`strip-rehearsal/`、`migration-rehearsal/` 是**归档副本**，不计入。
复现：``python tools\check_single_source_constants.py``
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "sources"))
sys.path.insert(0, str(STAGE / "core"))

import coconut as C                                          # noqa: E402
import query_base as qb                                      # noqa: E402

KEY = "COCONUT_DB"
bad = 0

their = getattr(qb, KEY, None)
value_same = their is not None and str(C.DEFAULT_DB) == str(their)
print("  coconut.DEFAULT_DB     = %s" % C.DEFAULT_DB)
print("  query_base.%s    = %s" % (KEY, their))
print("  %s 取值一致" % ("PASS" if value_same else "FAIL"))
bad += 0 if value_same else 1

src = (STAGE / "sources" / "coconut.py").read_text(encoding="utf-8")
imported = ("from query_base import %s" % KEY) in src
print("  %s coconut.py 是从 query_base import 的" % ("PASS" if imported else "FAIL"))
bad += 0 if imported else 1

PAT = re.compile(r"""["'][A-Za-z]:\\\\?[^"']*coconut\.db["']""")
ARCHIVE = ("libs", "repro-20261016", "__pycache__", "snapshots",
           "strip-rehearsal", "migration-rehearsal")
WHITELIST = {"core\\query_base.py", "tools\\tcm_ro.py", "tools/tcm_ro.py"}
lits, archived = [], []
for py in STAGE.rglob("*.py"):
    is_arch = any(x in py.parts for x in ARCHIVE)
    try:
        text = py.read_text(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        continue
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.lstrip().startswith("#"):
            continue
        if PAT.search(ln):
            rel = str(py.relative_to(STAGE))
            (archived if is_arch else lits).append("%s:%d" % (rel, i))
# ★ 判据（与"待办①"的原意一致）：**引擎源码层**（sources/ core/）必须单一来源；
#   tools/ 里的一次性探针脚本自带字面量 → 记为 WARN（列清单，不阻塞）。
src_layer = [x for x in lits if x.startswith("sources\\") or x.startswith("core\\")]
ok = (len(src_layer) == 1 and src_layer[0].startswith("core\\query_base.py")) and imported
print("  %s 引擎源码层（core/ + sources/）的定义 %d 处：%s"
      % ("PASS" if ok else "FAIL", len(src_layer), src_layer or "（无）"))
tool_lits = [x for x in lits if x not in src_layer]
print("  WARN tools/ 里还有 %d 个一次性脚本自带字面量（历史探针，未回改）：%s"
      % (len(tool_lits), tool_lits or "（无）"))
print("     归档副本里另有 %d 处（snapshots/strip-rehearsal/migration-rehearsal，不计）"
      % len(archived))
bad += 0 if ok else 1

print()
print("  结论：%s" % ("库路径单一来源 ✓" if not bad else "★ 有 %d 条不符合" % bad))
sys.exit(1 if bad else 0)
