# -*- coding: utf-8 -*-
r"""源更新监视：查药典/模板数据源仓库有没有新动静（不下载、只报告，网络只读）。

监视对象（可自行增改）：
  * cliviali/Independent-KBs      —— 药典 2025 知识库（判据链源）
  * flyrae/PPRC                   —— 药典 2020 docx（旧源，留档）
  * cutcutjust/PharmaScanAI-v2-final —— 2025 版部目录

状态存 reports\_probe_net\source_watch.json；发现 pushed_at 变化 → 提示重跑流水线。
用法: python tools\check_source_updates.py     （需联网）
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
STATE = STAGE / "reports" / "_probe_net" / "source_watch.json"
REPOS = {
    "cliviali/Independent-KBs": "药典2025判据链（build_chp_markers_2025 → curate → link）",
    "flyrae/PPRC": "药典2020（旧源，留档）",
    "cutcutjust/PharmaScanAI-v2-final": "2025 版部目录 CSV",
}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def main() -> int:
    old = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    new, alerts = dict(old), []
    for repo, what in REPOS.items():
        try:
            req = urllib.request.Request("https://api.github.com/repos/" + repo, headers=UA)
            d = json.load(urllib.request.urlopen(req, timeout=25))
            cur = {"pushed_at": d.get("pushed_at"), "size_kb": d.get("size"),
                   "checked": time.strftime("%Y-%m-%d %H:%M")}
            prev = old.get(repo) or {}
            if prev.get("pushed_at") and prev["pushed_at"] != cur["pushed_at"]:
                alerts.append("%s 有更新：%s -> %s（重跑：%s）"
                              % (repo, prev["pushed_at"], cur["pushed_at"], what))
                mark = "（有更新!）"
            else:
                mark = "（首次记录）" if not prev else "（无变化）"
            print("%-42s pushed=%s size=%sKB %s"
                  % (repo, cur["pushed_at"], cur["size_kb"], mark))
            new[repo] = cur
        except Exception as ex:
            print("%-42s 查询失败：%s" % (repo, str(ex)[:80]))
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + ("⚠ " + "\n⚠ ".join(alerts) if alerts else "全部源无更新。"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
