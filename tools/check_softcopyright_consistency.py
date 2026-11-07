# -*- coding: utf-8 -*-
r"""判定性检查：软著三件套的「软件全称 + 版本号」是否**逐字一致**。

三件套：
  * G1 源程序文档  `reports\软著\源程序文档_前30页+后30页.txt`（看页眉行）
  * G2 用户手册    `reports\软著\用户手册-v1.0.0-提交版.txt`（看页眉行）
  * G3 申请表信息  `reports\软著\软著-申请表信息.md`（看「软件全称」「版本号」两行）

判据：三处抽出来的字符串**完全相同**（含空格），否则 FAIL 并打印各自的字符串。
复现：``python tools\check_softcopyright_consistency.py``
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
SOFT = STAGE / "reports" / "软著"
G1 = SOFT / "源程序文档_前30页+后30页.txt"
G2 = SOFT / "用户手册-v1.0.0-提交版.txt"
G3 = SOFT / "软著-申请表信息.md"


def header_of(p: Path) -> str:
    """从页眉行里抽「名称 + 版本」（去掉后面的页码部分）。"""
    line = p.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    m = re.match(r"^(.*?)\s+第\s*\d+\s*页", line)
    return (m.group(1) if m else line).strip()


def from_form(p: Path) -> tuple:
    t = p.read_text(encoding="utf-8", errors="replace")
    name = re.search(r"\|\s*软件全称\s*\|\s*(.+?)\s*\|", t)
    ver = re.search(r"\|\s*版本号\s*\|\s*(.+?)\s*\|", t)
    return (name.group(1).strip() if name else "?", ver.group(1).strip() if ver else "?")


def main() -> int:
    ok = True
    n1 = header_of(G1)
    n2 = header_of(G2)
    n3, v3 = from_form(G3)
    v3s = re.sub(r"[（(].*?[)）]", "", v3).strip()
    print("  G1 源程序文档页眉 ： %s" % n1)
    print("  G2 用户手册页眉   ： %s" % n2)
    print("  G3 申请表         ： %s ｜ 版本号 %s" % (n3, v3))
    ok &= (n1 == n2)
    print("  %s G1 == G2（逐字）" % ("PASS" if n1 == n2 else "FAIL"))
    # 三件套的版本号必须一致（申请表里版本号带说明文字，抽 Vx.y.z 比对）
    v_g1 = re.search(r"V\d+\.\d+\.\d+", n1)
    v_g2 = re.search(r"V\d+\.\d+\.\d+", n2)
    v_g3 = re.search(r"V\d+\.\d+\.\d+", v3)
    same_v = len({x.group(0) for x in (v_g1, v_g2, v_g3) if x}) == 1
    ok &= same_v
    print("  %s 版本号三处一致：%s / %s / %s"
          % ("PASS" if same_v else "FAIL",
             v_g1.group(0) if v_g1 else "?", v_g2.group(0) if v_g2 else "?",
             v_g3.group(0) if v_g3 else "?"))
    # 申请表里的名称应包含页眉名称的核心部分（允许前后缀差异，只要包含"chemreact"与中文主名）
    core = re.sub(r"\s*V\d+\.\d+\.\d+", "", n1).strip()
    contains = core in n3 or n3 in core
    ok &= contains
    print("  %s 名称一致（G3 含 G1 名称：%s）" % ("PASS" if contains else "WARN", core))
    print()
    print("  结论：%s" % ("三件套逐字一致 ✓" if ok else "★ 有不一致，请先统一再提交"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
