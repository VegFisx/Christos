# -*- coding: utf-8 -*-
import sys
from pathlib import Path
p = Path(r'D:/ProgramData/DSHNS/交接单.md')
src = p.read_text(encoding='utf-8')
anchor = '## ★ 必须避免的事'
i = src.index(anchor)
L = []
L.append("## ⚠ 引号纪律（2026-10-11 用户要求列入报告）")
L.append("")
L.append("**一次任务连踩 5 次**，全是工具用法错误（不是化学问题），详见：")
L.append("- `AGENTS.md` 第八节（长期纪律）")
L.append("- `reports/引号纪律-踩坑记录.md`（完整实例与写法）")
L.append("")
L.append("| # | 写法 | 报错 | 根因 |")
L.append("|---|---|---|---|")
L.append("| 1 | `String.raw` 里写含反斜杠n 的 Python print | `unterminated string literal` | **`String.raw` 不转义** |")
L.append("| 2 | 单引号 JS 串里出现反引号 | `Expected a semicolon` | 模板串被提前结束 |")
L.append("| 3 | f-string 塞进单引号 JS 串 | `unterminated f-string` | 双引号配对错乱 |")
L.append("| 4 | Python 里写 `&&` 或 `L.push` | `invalid syntax` / `AttributeError` | 脑子在写 JS（本轮又犯一次） |")
L.append("| 5 | 中英文引号混用 | `unterminated string` | 配对不上 |")
L.append("")
L.append("**三条硬规矩**：")
L.append("1. 不用 `String.raw` 写 Python 代码；要多行就做成 `string[]` 再 join；")
L.append("2. 要嵌含引号的文本一律 `JSON.stringify`，不手写引号；")
L.append("3. **写完立刻 `ast.parse` 语法检查**，别等运行。")
L.append("")
L.append("写法与「先打印原始数据」是同一条纪律：**30 秒的检查，换掉一整轮的返工。**")
L.append("")