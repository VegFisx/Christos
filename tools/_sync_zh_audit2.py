# -*- coding: utf-8 -*-
# One-shot: replace the 27-case audit with the 75-case version.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
         r"\Christos-system-paper-draft-20261019-zh-humanized.md")

OLD_HEAD = "解析级联对一组固定的 27 个输入跑了一遍：10 个精确中文名、5 个别名、5 个炮制品、3 个拉丁双名，以及 4 个本不该解析成功的字符串。"

NEW_HEAD = "解析级联对 75 个输入跑了一遍：20 个精确中文名、10 个别名、10 个炮制品、25 个从药材表里抽出的拉丁名，以及 10 个本不该解析成功的字符串。"

OLD_TABLE = "\n".join([
    "| 输入组 | n | 解析成功 | 未解析 | 歧义 |",
    "|---|---:|---:|---:|---:|",
    "| 精确中文名 | 10 | 10 | 0 | 1 |",
    "| 别名 | 5 | 5 | 0 | 1 |",
    "| 炮制品 | 5 | 3 | 2 | 0 |",
    "| 拉丁双名 | 3 | 1 | 2 | 0 |",
    "| 非药材字符串 | 4 | 1 | 3 | 1 |",
])

NEW_TABLE = "\n".join([
    "| 输入组 | n | 解析成功 | 未解析 | 歧义 |",
    "|---|---:|---:|---:|---:|",
    "| 精确中文名 | 20 | 20 | 0 | 1 |",
    "| 别名 | 10 | 9 | 1 | 1 |",
    "| 炮制品 | 10 | 3 | 7 | 0 |",
    "| 拉丁名（取自表内） | 25 | 25 | 0 | 0 |",
    "| 非药材字符串 | 10 | 1 | 9 | 1 |",
])

OLD_LATIN = "拉丁名是整条级联里最弱的一环。三个双名里有两个完全没解析出来，唯一成功的 Glycyrrhiza uralensis 解析成了「甘草节」，也就是甘草的节，而不是「甘草」。这是一个错误解析，审计让它变得可见，当前代码没有修正它。"

NEW_LATIN = "\n\n".join([
    "拉丁名这条路径要分两种情况看。从药材表里直接抽出的 25 个双名全部回指到自己的药材，因为这些条目存的是植物学双名。常见中药存的却是生药拉丁名：甘草那条存的是 Radix et Rhizoma Glycyrrhizae，不是 Glycyrrhiza uralensis。用户按植物学名输入因此会失败或者落到别的条目上——Glycyrrhiza uralensis 解析成了「甘草节」，也就是甘草的节。当前代码没有修正这个问题；要修，得把这一列拆成生药名和植物名两列。",
    "同一次审计还发现两处：「生地黄」解析成「鲜地黄」「干地黄」两个候选，而不是单一药材，因为表里没有这个名字；「寸冬」（麦冬的别名）完全没解析出来。",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    for label, old, new in (
        ("head", OLD_HEAD, NEW_HEAD),
        ("table", OLD_TABLE, NEW_TABLE),
        ("latin", OLD_LATIN, NEW_LATIN),
    ):
        n = s.count(old)
        print("%s hits=%d" % (label, n))
        if n:
            s = s.replace(old, new, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
