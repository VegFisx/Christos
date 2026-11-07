# -*- coding: utf-8 -*-
# One-shot: mirror the downstream-gap note into the Chinese draft.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
         r"\Christos-system-paper-draft-20261019-zh-humanized.md")

LIM_ANCHOR = "9. **拉丁名路径不可靠。**"
LIM_ADD = "\n".join([
    "9. **下游风险标注止步于已知化合物。** 预测产物如果不在任何化合物表里，就没有标识符"
    "可以去关联毒性或疾病记录。ADMET 缓存用 InChIKey 匹配，覆盖一次煎煮运行产物的 2.6%；"
    "CTD 用化学品名字匹配，几乎覆盖不到，因为新结构根本没有名字可对。同一对方剂上，"
    "ADMET 缓存能把温和方与含附子的方分得很清楚——84 个有标注的产物里 0 个超过急性毒性"
    "第 90 百分位，而对含附子的方是 169 个里 65 个——但只对其中被既往整理收录的少数产物成立。",
    "10. **拉丁名路径不可靠。**",
])

OLD_OUTLOOK = "## 展望"
NEW_OUTLOOK = "\n".join([
    "## 展望",
    "",
    "要补上这条标注链，需要的是基础设施而不是更好的模型：要么为天然产物骨架给出预测靶点谱，"
    "要么建立结构到 MeSH、结构到 RxNorm 的映射表，让新产物能够接上现有的毒性与不良反应表。"
    "这两样目前都不存在，都属于数据工程问题，也都可以做。",
    "",
    "此外还有三项眼前的扩展。",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    print("lim=%d outlook=%d" % (s.count(LIM_ANCHOR), s.count(OLD_OUTLOOK)))
    s = s.replace(LIM_ANCHOR, LIM_ADD, 1)
    s = s.replace(OLD_OUTLOOK, NEW_OUTLOOK, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
