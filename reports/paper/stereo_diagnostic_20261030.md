# 立体层诊断：为什么只有槲皮素案例拿到 exact stereo

生成时间：2026-10-30 18:26:35

做法：五个案例都用 PubChem 的 isomeric SMILES 作底物，按与文献一致性验证相同的运行配置（煎煮、100 C、60 min、pH 6.5、空气、一轮、cap 64/pair、strict_redox_gate）重跑当前引擎；只统计与 PubChem 参考产物在连接层一致的候选，检查候选自身的手性中心数与已指定数。

| 案例 | 参考产物手性中心/已指定 | 候选最大已指定数 | 连接层候选 | exact |
|---|---:|---:|---:|---:|
| 18beta-Glycyrrhetinic acid | 9/9 | 9 | 1 | 1 |
| 20(S)-Ginsenoside Rg3 | 20/20 | 20 | 1 | 1 |
| Benzoylaconine | 15/15 | 14 | 1 | 0 |
| Aconine | 15/14 | 15 | 1 | 0 |
| Quercetin | 0/0 | 0 | 1 | 1 |

判定口径：连接层一致 = InChIKey 第一段相同；exact = isomeric SMILES 规范化后与 PubChem 参考产物完全相同；“已指定”用 RDKit FindMolChiralCenters(includeUnassigned=True) 统计，tag 不是 ? 才算指定。

逐案例细节见同目录 JSON。
