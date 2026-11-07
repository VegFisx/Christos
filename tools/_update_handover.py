# -*- coding: utf-8 -*-
"""更新交接单：把「下一步」段替换为②后半段已完成。"""
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

p = Path(r'D:/ProgramData/DSHNS/交接单.md')
src = p.read_text(encoding='utf-8')

anchor = '## 下一步（**待用户定**）'
i = src.index(anchor)
j = src.index('## ★ 必须避免的事', i)

BS = chr(92)
lines = [
    '## ★★ ②后半段已完成（2026-10-11 第四轮）★★',
    '',
    '详见 `reports' + BS + '逆模板重抽-报告.md`。**结论：模板质量问题解决了，瓶颈转移到搜索器。**',
    '',
    '**实测结果（留出集不重叠；命中判据 = 生成前体 ⊆ 真实反应物）**',
    '',
    '| 测试集 | 条数 | 新抽逆模板 | SmartReact反转模板（现状） |',
    '|---|---|---|---|',
    '| 全量 50% 处 | 40 | **39（97.5%）** | 4（10.0%） |',
    '| 全量 85% 处 | 24 | **20（83.3%）** | 3（12.5%） |',
    '',
    '另用**更严的精确相等判据**：新模板 recall = **21.75%**（1200 条测试）。',
    '',
    '- 训练 60,000 条 ORD -> 模板实例 **56,047** -> 按反应中心指纹聚类成 **3,228 条**',
    '  产物：`reports' + BS + 'retro_templates_clustered.jsonl`',
    '- 两个不同测试区间结论一致，不是单次运气。',
    '',
    '**★ 上次失败的真实原因（不是「漏了聚类」）**',
    '',
    '1. **rdchiral 的键名**：要 `{"reactants": ..., "products": ...}`（**复数 products**）。',
    '   上次传单数 `product` / `reaction_smiles` -> 全部 KeyError；',
    '   而批量脚本 `except Exception: continue` 把 40000 条失败全吞了 —— 这才是「抽不出模板」的元凶。',
    '2. **进程池/线程池会被个别分子整池挂死**（和 RDKit InChI 同一类问题，实测两次）。',
    '   解法：**独立进程分片**（每片自己 OFFSET/LIMIT 读 parquet、自己写 JSONL）。',
    '3. rdchiral 失败路径无条件 print，必须把 fd1 重定向到 devnull（放模块顶层无效）。',
    '',
    '**★★ 最重要的发现：瓶颈转移了 ★★**',
    '',
    '| 环节 | 实测 |',
    '|---|---|',
    '| 新模板的单步复现能力 | **83%~97%** |',
    '| 端到端逆合成一步到位率 | **仍 5.0%**（160 个 ORD 产物） |',
    '',
    '-> **再堆模板没有意义了。下一步应该换搜索器**：用新的 3,228 条模板 + 更好的排序 + 多步回溯。',
    '',
    '## 下一步（**待用户定**）',
    '',
    '- **换搜索器**（推荐）：现有 `retro_search.py` 是「9770 条反转模板全跑一遍」的暴力做法，',
    '  换成新模板库 + 打分排序 + 多步搜索。**这是现在唯一还卡着端到端成功率的地方。**',
    '- **接入 TCMAI**：技术成本极低（只需 `smartreact` 纯 Python，rdkit 已有），',
    '  但要先决定拿哪一版模板接（新模板库还没接进 `retro_search.py`）。',
    '- **①的收尾项**（可选，便宜）',
    '  - 互变异构体归一化（实测 41/30,000 有此现象）',
    '  - 试剂类 265,446 个纳入终端集合（`--with-reagents`）',
    '',
    '',
]
src = src[:i] + chr(10).join(lines) + src[j:]
p.write_text(src, encoding='utf-8')
print('交接单已更新')