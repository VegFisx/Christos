# -*- coding: utf-8 -*-
r"""用 git 对比优化前后：产物必须完全一致。

★ 这正是版本控制该有的用法

  优化前最后一次提交是 4209abc37998（ROUND25）。
  从那个提交里取出 core/engine.py，和当前的对比。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from dulwich.repo import Repo

repo = Repo(str(STAGE))

# 找 ROUND25 那个提交
target = None
for entry in repo.get_walker():
    c = entry.commit
    msg = c.message.decode("utf-8", "replace")
    if msg.startswith("ROUND25"):
        target = c
        break
if target is None:
    print("找不到 ROUND25 提交")
    raise SystemExit(1)
print(f"基线提交: {target.id.decode()[:12]}  {target.message.decode('utf-8').splitlines()[0]}")

# 从提交里取出 core/engine.py
tree = repo[target.tree]
core = repo[tree[b"core"][1]]
blob = repo[core[b"engine.py"][1]]
old_src = blob.data.decode("utf-8")
print(f"取到旧 engine.py: {len(old_src)} 字节")

# 当前文件
cur = (STAGE / "core" / "engine.py").read_text(encoding="utf-8")
print(f"当前 engine.py  : {len(cur)} 字节")

# 备份并替换
backup = STAGE / "core" / "_engine_new_backup.py"
backup.write_text(cur, encoding="utf-8")

driver = STAGE / "tools" / "_perf_compare_driver.py"
driver.write_text(textwrap.dedent('''
    import sys, json
    from pathlib import Path
    STAGE = Path(r"D:\\ProgramData\\DSHNS\\chemreact-staging")
    sys.path.insert(0, r"D:\\TCMAI\\src")
    sys.path.insert(0, str(STAGE / "api"))
    for d in ("core","conditions","rules","libs","sources"):
        p = STAGE/d
        if p.is_dir(): sys.path.insert(0, str(p))
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.error"); RDLogger.DisableLog("rdApp.warning")
    from engine import Compound, get_mol, load_engine
    import templates as T
    from tcm_ro import use_readonly; use_readonly()
    from db_utils import find_compounds
    def canon(s):
        m = Chem.MolFromSmiles(s) if s else None
        return Chem.MolToSmiles(m) if m else None
    eng, rules, profs = load_engine()
    cond = T.get_template("煎煮")
    comps = []
    for h in ("甘草","附子","干姜"):
        for r in find_compounds(h, limit=20):
            comps.append(dict(r))
    subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
            for c in comps if get_mol(c["smiles"])]
    ps = eng.step(subs, cond, 0.15, round_no=1)
    out = sorted({canon(p.smiles) for p in ps if canon(p.smiles)})
    print("RESULT " + json.dumps({"n": len(out), "set": out}, ensure_ascii=False))
'''), encoding="utf-8")

py = r"D:\TCMAI\venv\Scripts\python.exe"
results = {}

for label, src in (("旧（优化前）", old_src), ("新（优化后）", cur)):
    (STAGE / "core" / "engine.py").write_text(src, encoding="utf-8")
    r = subprocess.run([py, "-X", "utf8", str(driver)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT ")), None)
    if line is None:
        print(f"  {label} 跑失败:\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
        continue
    import json
    d = json.loads(line[7:])
    results[label] = set(d["set"])
    print(f"  {label}: {d['n']} 个产物")

# 还原成新版
(STAGE / "core" / "engine.py").write_text(cur, encoding="utf-8")
backup.unlink()
driver.unlink()

print()
print("=" * 88)
if len(results) == 2:
    a, b = list(results.values())
    both = a & b
    print(f"  共有     : {len(both)}")
    print(f"  仅旧有   : {len(a - b)}")
    print(f"  仅新有   : {len(b - b)}")
    print(f"  完全相同 : {a == b}")
    if a != b:
        print()
        print("  ★ 有差异！★")
        for s in list(a - b)[:5]:
            print(f"      仅旧有: {s[:74]}")
        for s in list(b - a)[:5]:
            print(f"      仅新有: {s[:74]}")
else:
    print("  对比未完成")
print("=" * 88)
