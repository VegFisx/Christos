# -*- coding: utf-8 -*-
# One-shot: insert the herb-resolution audit section into the Chinese draft.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
         r"\Christos-system-paper-draft-20261019-zh-humanized.md")
ANCHOR = "### 中医药案例"

BLOCK = """### 药材解析审计

解析级联对一组固定的 27 个输入跑了一遍：10 个精确中文名、5 个别名、5 个炮制品、3 个拉丁双名，以及 4 个本不该解析成功的字符串。

| 输入组 | n | 解析成功 | 未解析 | 歧义 |
|---|---:|---:|---:|---:|
| 精确中文名 | 10 | 10 | 0 | 1 |
| 别名 | 5 | 5 | 0 | 1 |
| 炮制品 | 5 | 3 | 2 | 0 |
| 拉丁双名 | 3 | 1 | 2 | 0 |
| 非药材字符串 | 4 | 1 | 3 | 1 |

精确中文名和别名每次都解析成功，两组各有一个歧义结果。炮制品五个中成功三个：炒白术和姜半夏不在库里，返回的是炮制品闸的明确“库缺”，而不是被拆成基原。

拉丁名是整条级联里最弱的一环。三个双名里有两个完全没解析出来，唯一成功的 Glycyrrhiza uralensis 解析成了「甘草节」，也就是甘草的节，而不是「甘草」。这是一个错误解析，审计让它变得可见，当前代码没有修正它。

四个本不该解析的字符串里，三个返回空。「甘」这个单字返回了 40 个候选，正好撞上子串匹配的上限，因为它能匹配到很多药名。

审计脚本在仓库里（tools/audit_herb_resolution.py），用例表可以继续扩充。

"""


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("anchor hits=%d" % n)
    if n:
        s = s.replace(ANCHOR, BLOCK + ANCHOR, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("inserted, %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
