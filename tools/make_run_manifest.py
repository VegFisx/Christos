# -*- coding: utf-8 -*-
"""生成可复现运行清单（run manifest）。

审稿人问「你这 92.01% 是怎么跑出来的、配置是什么、代码是哪一版」时，
直接把 manifest 贴进补充材料即可。采集：

1. git 提交、是否有未提交改动、分支
2. Python / 关键库版本（rdkit、numpy、scipy 若存在）
3. 所有 `CHEMCREACT_*` 环境变量（排序后）
4. 命令行参数与 cwd
5. 关键数据文件的 sha256（rules.json / paozhi_evidence.json / thresholds.json /
   kinetics.json / candidate 基准结果目录里的文件可选）
6. 时间戳与主机信息（CPU 核数、内存）

用法：
    python -I tools/make_run_manifest.py --out reports/paper/results/xxx/manifest.json
    python -I tools/make_run_manifest.py --out m.json --note "wide 20k shard run"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
GIT = "D:/ProgramData/DSHNS/tools/git.cmd"

KEY_FILES = [
    "rules/rules.json",
    "rules/paozhi_evidence.json",
    "rules/paozhi_adjuvants.json",
    "conditions/thresholds.json",
    "conditions/kinetics.json",
    "conditions/template_provenance.json",
    "core/constants_provenance.json",
    "libs/smartreact/data/templates.txt",
]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    try:
        out = subprocess.run([GIT, *args], cwd=str(ROOT), capture_output=True,
                             text=True, timeout=60)
        return (out.stdout or "").strip()
    except Exception as e:  # pragma: no cover - 环境缺 git 时不影响主流程
        return "ERROR: %s" % e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--note", default="")
    ap.add_argument("--extra", nargs="*", default=[], help="额外要算 sha256 的文件（相对仓库根）")
    a = ap.parse_args()

    libs = {}
    for name in ("rdkit", "numpy", "scipy", "pandas", "zstandard"):
        try:
            mod = __import__(name)
            libs[name] = getattr(mod, "__version__", "?")
        except Exception:
            libs[name] = None

    env = {k: v for k, v in sorted(os.environ.items())
           if k.startswith("CHEMCREACT") or k in ("PYTHONHASHSEED", "TZ")}

    files = {}
    for rel in list(KEY_FILES) + list(a.extra):
        p = ROOT / rel
        files[rel] = {"sha256": _sha256(p), "bytes": p.stat().st_size} if p.exists() else None

    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "note": a.note,
        "cwd": os.getcwd(),
        "argv": sys.argv,
        "git": {
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_files": len([x for x in _git("status", "-s", "-uno").splitlines() if x.strip()]),
            "last_commit_subject": _git("log", "-1", "--pretty=%s"),
        },
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "cpu_count": os.cpu_count(),
            "machine": platform.machine(),
        },
        "libraries": libs,
        "env_CHEMCREACT": env,
        "files": files,
    }

    out = Path(a.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("manifest → %s" % out)
    print("  commit %s (dirty=%d)" % (manifest["git"]["commit"][:12], manifest["git"]["dirty_files"]))
    for k, v in libs.items():
        print("  %-8s %s" % (k, v))
    print("  env: %d 项" % len(env))
    print("  files: %d 项" % len([1 for v in files.values() if v]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
