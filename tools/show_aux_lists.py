# -*- coding: utf-8 -*-
import json, sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
d = json.loads((STAGE / "reports" / "conditions_normalized.json").read_text(encoding="utf-8"))
print(f"{'反应类型':<34}{'辅助试剂 top4':<70}")
for k in sorted(d, key=lambda x: -d[x]["n_ord_matched"])[:20]:
    e = d[k]
    aux = e.get("auxiliary_reagents") or []
    print(f"{k[:33]:<34}{str(aux[:4])[:68]:<70}")
print()
n_aux = sum(1 for e in d.values() if e.get("auxiliary_reagents"))
print(f"有辅助试剂清单的类型: {n_aux}/{len(d)}")
