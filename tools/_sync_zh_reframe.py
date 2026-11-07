# -*- coding: utf-8 -*-
# One-shot: mirror the intro/conclusion reframe into the Chinese draft.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
         r"\Christos-system-paper-draft-20261019-zh-humanized.md")

INTRO_OLD = "Christos 因此围绕四项要求设计："
INTRO_NEW = (
    "本系统是在逐层审计中医药数据处理管线之后才建起来的：每一层先确认可信，再往上叠。"
    "这次审计得到四条发现，每一条都改变了设计——64 条人工整理规则里加载器只用了 6 条；"
    "条件门在空气气氛下放行了还原反应；出处字段结构完整，但带实质条件证据的只有 1.2%；"
    "拉丁名字段把植物学名和药典药材名混在一列。第 5 节逐条给出测量。\n\n"
    "Christos 因此围绕四项要求设计："
)

CONC_OLD = "Christos 为天然产物和中医药研究提供了一个可溯源、只读的反应预测工作流"
CONC_NEW = "\n".join([
    "Christos 的目的就是让反应预测可以被审计，而审计查出来的问题比设计时预想的多。",
    "",
    "管线能抵达文献记载的煎煮化学：五条涵盖糖苷水解和酯水解的转化全部在第一轮出现，"
    "两级筛选把一次 3,210 条候选的煎煮运行压到 6 个有文献身份的成分。",
    "",
    "它也暴露了四个本来会被「系统级声明」掩盖的缺陷：64 条规则里有 58 条从未被加载；"
    "还原规则通过了只允许空气的气氛门；出处字段完整而实质条件证据只覆盖 1.2%；"
    "拉丁名列存的是药材名而不是植物名。",
    "",
    "那些基准数字——82.32% 的正向召回，以及两种配置下 94.74% 和 79.81% 的逆向覆盖——"
    "描述的是引擎，不是中药层。中药层是按输入解析与出处层评估的，它的局限和结果并列呈现。",
    "",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    print("intro=%d conc=%d" % (s.count(INTRO_OLD), s.count(CONC_OLD)))
    s = s.replace(INTRO_OLD, INTRO_NEW, 1)
    start = s.index(CONC_OLD)
    end = s.index("\n\n## 数据与代码可用性", start)
    s = s[:start] + CONC_NEW.rstrip() + s[end:]
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
