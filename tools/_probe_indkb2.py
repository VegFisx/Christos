# -*- coding: utf-8 -*-
"""一次性探针：indkb.zip 的成方制剂条数 / 有正文的条数 / 正文里有没有【处方】。"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

Z = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\_probe_net\indkb.zip")
SUB = "一部/成方制剂和单味制剂/"


def main() -> None:
    z = zipfile.ZipFile(Z)
    names = [i.filename for i in z.infolist() if i.filename.endswith(".md")]
    cf = [n for n in names if SUB in n]
    print("md 总数 = %d ；其中「成方制剂和单味制剂」= %d" % (len(names), len(cf)))
    # 一部其他分节
    sec = {}
    for n in names:
        if "/一部/" in n:
            part = n.split("/一部/")[1].split("/")[0]
            sec[part] = sec.get(part, 0) + 1
    print("一部的分节：", sorted(sec.items(), key=lambda t: -t[1]))

    ok = fail = empty = has_rx = 0
    fails = []
    rx_samples = []
    for n in cf:
        try:
            t = z.read(n).decode("utf-8", "replace")
        except Exception as ex:                            # noqa: BLE001
            print("   [warn] 读 %s 失败：%s" % (n, ex))
            continue
        if "内容获取失败" in t:
            fail += 1
            if len(fails) < 6:
                fails.append(Path(n).stem)
            continue
        body = t.split("---", 2)[-1] if t.startswith("---") else t
        if len(body.strip()) < 200:
            empty += 1
            continue
        ok += 1
        if re.search(r"【\s*处方\s*】", t):
            has_rx += 1
            if len(rx_samples) < 3:
                p = re.search(r"【\s*处方\s*】", t).start()
                rx_samples.append((Path(n).stem, re.sub(r"\s+", " ", t[p:p + 260])))
    print()
    print("有正文 = %d ｜ 内容获取失败 = %d ｜ 过短(空) = %d" % (ok, fail, empty))
    print("失败样例：", fails)
    print("有正文者里含【处方】的 = %d（%.1f%%）"
          % (has_rx, 100.0 * has_rx / max(1, ok)))
    print()
    for nm, seg in rx_samples:
        print("【%s】%s" % (nm, seg[:240]))
        print()


if __name__ == "__main__":
    main()
