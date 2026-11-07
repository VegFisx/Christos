# 第七十五轮 · mined 模板条件窗口（Top100）

> 按 support 取 top 模板；对 ORD 索引前 20000 条等距样本试跑；只有产物与记录一致才收集条件。
> 这是 per-template 条件窗口，不依赖 37 类反应表。
> ★ 实时引擎已接入 **Top100**（`mined_top_001..100`；65 双底物 + 34 单底物）。

| # | support | 模板 | fired | match | 温度 | 催化剂 | 溶剂 | 试剂 |
|---|---:|---|---:|---:|---|---|---|---|
| 1 | 21400 | `O=[N+;H0;D3:1](-[O-])-[c:2]>>[NH2;D1;+0:1]-[c:2]` | 1535 | 345 | 66 | 254 | 329 | 0 |
| 2 | 14521 | `C-[O;H0;D2;+0:1]-[C:2]=[O;D1;H0:3]>>[O;D1;H0:3]=[C:2]-[OH;D1;+0:1]` | 7455 | 743 | 166 | 30 | 651 | 0 |
| 3 | 12618 | `C-C-[O;H0;D2;+0:1]-[C:2]=[O;D1;H0:3]>>[O;D1;H0:3]=[C:2]-[OH;D1;+0:1]` | 5301 | 405 | 89 | 11 | 348 | 0 |
| 4 | 10316 | `C-C(-C)(-C)-O-C(=O)-[N;H0;D3;+0:1](-[C:2])-[C:3]>>[C:2]-[NH;D2;+0:1]-[C:3]` | 900 | 206 | 16 | 1 | 181 | 0 |
| 5 | 7497 | `C-[O;H0;D2;+0:1]-[c:2]>>[OH;D1;+0:1]-[c:2]` | 5224 | 240 | 54 | 50 | 211 | 0 |
| 6 | 6158 | `Br-[CH2;D2;+0:1]-[C:2].[OH;D1;+0:3]-[c:4]>>[C:2]-[CH2;D2;+0:1]-[O;H0;D2;+0:3]-[c` | 162 | 115 | 41 | 9 | 103 | 0 |
| 7 | 5381 | `C-C(-C)(-C)-O-C(=O)-[NH;D2;+0:1]-[C:2]>>[C:2]-[NH2;D1;+0:1]` | 584 | 105 | 11 | 1 | 86 | 0 |
| 8 | 4994 | `Cl-[c;H0;D3;+0:1](:[#7;a:2]):[#7;a:3].[NH2;D1;+0:4]-[c:5]>>[#7;a:2]:[c;H0;D3;+0:` | 113 | 59 | 21 | 10 | 26 | 0 |
| 9 | 4335 | `Cl-[S;H0;D4;+0:1](-[C;D1;H3:2])(=[O;D1;H0:3])=[O;D1;H0:4].[C:5]-[OH;D1;+0:6]>>[C` | 115 | 69 | 19 | 1 | 61 | 0 |
| 10 | 4268 | `C-[O;H0;D2;+0:1]-[C;H0;D3;+0:2](-[C:3])=[O;H0;D1;+0:4]>>[C:3]-[C;H0;D3;+0:2](=[O` | 3739 | 443 | 87 | 25 | 389 | 0 |
| 11 | 4028 | `C-C-[O;H0;D2;+0:1]-[C;H0;D3;+0:2](-[C:3])=[O;H0;D1;+0:4]>>[C:3]-[C;H0;D3;+0:2](=` | 2579 | 262 | 52 | 10 | 230 | 0 |
| 12 | 4010 | `O=[C;H0;D3;+0:1](-[OH;D1;+0:2])-[c:3].[C:4]-[NH2;D1;+0:5]>>[C:4]-[NH;D2;+0:5]-[C` | 331 | 236 | 23 | 13 | 134 | 0 |
| 13 | 3646 | `[c:1]-[O;H0;D2;+0:2]-C-c1:c:c:c:c:c:1>>[OH;D1;+0:2]-[c:1]` | 535 | 62 | 7 | 45 | 59 | 0 |
| 14 | 3481 | `Br-[CH2;D2;+0:1]-[C:2].[C:3]-[NH;D2;+0:4]-[C:5]>>[C:3]-[N;H0;D3;+0:4](-[CH2;D2;+` | 212 | 142 | 29 | 6 | 109 | 0 |
| 15 | 3462 | `C-C(-C)(-C)-[O;H0;D2;+0:1]-[C:2]=[O;D1;H0:3]>>[O;D1;H0:3]=[C:2]-[OH;D1;+0:1]` | 2117 | 78 | 8 | 0 | 60 | 0 |
| 16 | 3192 | `O-[C;H0;D3;+0:1](=[O;D1;H0:2])-[c:3].[C:4]-[NH2;D1;+0:5]>>[C:4]-[NH;D2;+0:5]-[C;` | 464 | 272 | 28 | 14 | 149 | 0 |
| 17 | 3178 | `Cl-[C;H0;D3;+0:1](=[O;D1;H0:2])-[c:3].[NH2;D1;+0:4]-[c:5]>>[O;D1;H0:2]=[C;H0;D3;` | 114 | 87 | 6 | 9 | 58 | 0 |
| 18 | 3070 | `O=[N+;H0;D3:1](-[O-])-[c:2]:[c:3]:[#7;a:4]>>[#7;a:4]:[c:3]:[c:2]-[NH2;D1;+0:1]` | 217 | 61 | 15 | 43 | 57 | 0 |
| 19 | 3039 | `Cl-[CH2;D2;+0:1]-[C:2].[C:3]-[NH;D2;+0:4]-[C:5]>>[C:3]-[N;H0;D3;+0:4](-[CH2;D2;+` | 161 | 81 | 20 | 3 | 59 | 0 |
| 20 | 2653 | `C-C(-C)(-C)-[Si](-C)(-C)-[O;H0;D2;+0:1]-[C:2]>>[C:2]-[OH;D1;+0:1]` | 152 | 34 | 7 | 1 | 34 | 0 |
| 21 | 2633 | `Br-[c;H0;D3;+0:1](:[c:2]):[c:3].O-B(-O)-[c;H0;D3;+0:4](:[c:5]):[c:6]>>[c:2]:[c;H` | 265 | 210 | 97 | 130 | 154 | 0 |
| 22 | 2627 | `Cl-[C;H0;D3;+0:1](-[C:2])=[O;D1;H0:3].[NH2;D1;+0:4]-[c:5]>>[C:2]-[C;H0;D3;+0:1](` | 172 | 92 | 13 | 2 | 71 | 0 |
| 23 | 2543 | `[C:1]-[CH2;D2;+0:2]-[OH;D1;+0:3]>>[C:1]-[CH;D2;+0:2]=[O;H0;D1;+0:3]` | 1431 | 47 | 15 | 2 | 45 | 0 |
| 24 | 2513 | `O-[CH3;D1;+0:1].[O;D1;H0:2]=[C:3]-[OH;D1;+0:4]>>[CH3;D1;+0:1]-[O;H0;D2;+0:4]-[C:` | 813 | 70 | 15 | 2 | 21 | 0 |
| 25 | 2484 | `O=[CH;D2;+0:1]-[c:2].[C:3]-[NH2;D1;+0:4]>>[C:3]-[NH;D2;+0:4]-[CH2;D2;+0:1]-[c:2]` | 163 | 77 | 6 | 7 | 56 | 0 |
| 26 | 2428 | `Br-[c;H0;D3;+0:1](:[c:2]):[c:3].[C:4]#[CH;D1;+0:5]>>[C:4]#[C;H0;D2;+0:5]-[c;H0;D` | 77 | 57 | 15 | 34 | 35 | 0 |
| 27 | 2386 | `[C:1]-[N;H0;D3;+0:2](-C-c1:c:c:c:c:c:1)-[C:3]>>[C:1]-[NH;D2;+0:2]-[C:3]` | 1094 | 60 | 7 | 35 | 55 | 0 |
| 28 | 2376 | `C-[O;H0;D2;+0:1]-[C;H0;D3;+0:2](=[O;H0;D1;+0:3])-[c:4]>>[O;H0;D1;+0:1]=[C;H0;D3;` | 1672 | 298 | 79 | 5 | 260 | 0 |
| 29 | 2294 | `O=[C;H0;D3;+0:1](-[OH;D1;+0:2])-[c:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[C:4]-[N;H0;D3;+` | 232 | 122 | 5 | 1 | 58 | 0 |
| 30 | 2281 | `[O-]-[N+;H0;D3:1](=[O;D1;H0:2])-[OH;D1;+0:3].[c:4]:[cH;D2;+0:5]:[c:6]>>[O-;H0;D1` | 90 | 72 | 29 | 1 | 57 | 0 |
| 31 | 2252 | `[C:1]-[N;H0;D2;+0:2]=[N+]=[N-]>>[C:1]-[NH2;D1;+0:2]` | 106 | 39 | 4 | 22 | 33 | 0 |
| 32 | 2199 | `Cl-[c;H0;D3;+0:1](:[#7;a:2]):[c:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[#7;a:2]:[c;H0;D3;+` | 132 | 74 | 31 | 4 | 50 | 0 |
| 33 | 2175 | `O=[CH;D2;+0:1]-[c:2].[C:3]-[NH;D2;+0:4]-[C:5]>>[C:3]-[N;H0;D3;+0:4](-[CH2;D2;+0:` | 193 | 80 | 3 | 7 | 57 | 0 |
| 34 | 2121 | `I-[c;H0;D3;+0:1](:[c:2]):[c:3].[C:4]#[CH;D1;+0:5]>>[C:4]#[C;H0;D2;+0:5]-[c;H0;D3` | 58 | 53 | 7 | 36 | 35 | 0 |
| 35 | 2085 | `O=C1-C-C-C(=O)-N-1-[Br;H0;D1;+0:1].[CH3;D1;+0:2]-[c:3]>>[Br;H0;D1;+0:1]-[CH2;D2;` | 52 | 32 | 4 | 10 | 32 | 0 |
| 36 | 2073 | `O=[C;H0;D3;+0:1](-[C:2])-[OH;D1;+0:3].[C:4]-[NH2;D1;+0:5]>>[C:2]-[C;H0;D3;+0:1](` | 434 | 197 | 27 | 1 | 135 | 0 |
| 37 | 2065 | `Cl-[S;H0;D4;+0:1](=[O;D1;H0:2])(=[O;D1;H0:3])-[c:4].[NH2;D1;+0:5]-[c:6]>>[O;D1;H` | 99 | 76 | 4 | 5 | 42 | 0 |
| 38 | 2025 | `Cl-[S;H0;D4;+0:1](=[O;D1;H0:2])(=[O;D1;H0:3])-[c:4].[C:5]-[OH;D1;+0:6]>>[C:5]-[O` | 78 | 32 | 7 | 7 | 31 | 0 |
| 39 | 2016 | `Cl-[CH2;D2;+0:1]-[C:2].[OH;D1;+0:3]-[c:4]>>[C:2]-[CH2;D2;+0:1]-[O;H0;D2;+0:3]-[c` | 108 | 58 | 19 | 3 | 49 | 0 |
| 40 | 1994 | `O-[c;H0;D3;+0:1](:[c:2]):[c:3].[C:4]-[OH;D1;+0:5]>>[C:4]-[O;H0;D2;+0:5]-[c;H0;D3` | 1398 | 92 | 16 | 2 | 72 | 0 |
| 41 | 1988 | `O=[C;H0;D3;+0:1](-[#7:2])-[C:3]>>[#7:2]-[CH2;D2;+0:1]-[C:3]` | 2981 | 50 | 15 | 0 | 47 | 0 |
| 42 | 1910 | `Cl-[C;H0;D3;+0:1](=[O;D1;H0:2])-[c:3].[C:4]-[NH2;D1;+0:5]>>[C:4]-[NH;D2;+0:5]-[C` | 68 | 53 | 6 | 1 | 44 | 0 |
| 43 | 1864 | `O-[C;H0;D3;+0:1](=[O;D1;H0:2])-[c:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[C:4]-[N;H0;D3;+0` | 357 | 131 | 5 | 1 | 63 | 0 |
| 44 | 1858 | `Br-[Br;H0;D1;+0:1].[c:2]:[cH;D2;+0:3]:[c:4]>>[Br;H0;D1;+0:1]-[c;H0;D3;+0:3](:[c:` | 92 | 41 | 10 | 4 | 39 | 0 |
| 45 | 1853 | `C-C(=O)-[O;H0;D2;+0:1]-[C:2]>>[C:2]-[OH;D1;+0:1]` | 3739 | 46 | 12 | 0 | 43 | 0 |
| 46 | 1834 | `O=[C;H0;D3;+0:1](-[C:2])-[OH;D1;+0:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[C:2]-[C;H0;D3;+` | 586 | 146 | 21 | 9 | 107 | 0 |
| 47 | 1829 | `O=[C;H0;D3;+0:1](-[C:2])-[OH;D1;+0:3].[#8:4]-[C:5](=[O;D1;H0:6])-[C:7]-[NH2;D1;+` | 78 | 43 | 5 | 1 | 24 | 0 |
| 48 | 1817 | `Cl-[S;H0;D4;+0:1](=[O;D1;H0:2])(=[O;D1;H0:3])-[c:4].[C:5]-[NH2;D1;+0:6]>>[C:5]-[` | 46 | 36 | 10 | 1 | 32 | 0 |
| 49 | 1797 | `O=[C;H0;D3;+0:1](-[OH;D1;+0:2])-[c:3].[NH2;D1;+0:4]-[c:5]>>[O;H0;D1;+0:2]=[C;H0;` | 151 | 96 | 23 | 8 | 61 | 0 |
| 50 | 1779 | `[OH;D1;+0:1]-[CH2;D2;+0:2]-[c:3]>>[O;H0;D1;+0:1]=[CH;D2;+0:2]-[c:3]` | 341 | 36 | 6 | 25 | 35 | 0 |
| 51 | 1760 | `F-[c;H0;D3;+0:1](:[c:2]):[c:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[C:4]-[N;H0;D3;+0:5](-[` | 364 | 55 | 30 | 0 | 43 | 0 |
| 52 | 1747 | `O=C1-[N;H0;D3;+0:1](-[C:2])-C(=O)-c2:c:c:c:c:c:2-1>>[C:2]-[NH2;D1;+0:1]` | 145 | 39 | 7 | 0 | 33 | 0 |
| 53 | 1742 | `O-[C;H0;D3;+0:1](-[C:2])=[O;D1;H0:3].[NH2;D1;+0:4]-[c:5]>>[C:2]-[C;H0;D3;+0:1](=` | 570 | 157 | 39 | 12 | 118 | 0 |
| 54 | 1739 | `O-[C;H0;D3;+0:1](-[C:2])=[O;D1;H0:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[C:4]-[N;H0;D3;+0` | 1030 | 170 | 30 | 9 | 124 | 0 |
| 55 | 1719 | `O-[C;H0;D3;+0:1](-[C:2])=[O;H0;D1;+0:3]>>[C:2]-[CH2;D2;+0:1]-[OH;D1;+0:3]` | 6305 | 89 | 28 | 1 | 83 | 0 |
| 56 | 1679 | `Br-[c;H0;D3;+0:1](:[c:2]):[c:3].O-B(-O)-[c;H0;D3;+0:4](:[c:5]):[c:6]>>[c:5]:[c;H` | 265 | 210 | 97 | 130 | 154 | 0 |
| 57 | 1658 | `F-[c;H0;D3;+0:1](:[c:2]):[c:3].[C:4]-[OH;D1;+0:5]>>[C:4]-[O;H0;D2;+0:5]-[c;H0;D3` | 649 | 21 | 5 | 0 | 16 | 0 |
| 58 | 1623 | `Br-[c;H0;D3;+0:1](:[c:2]):[c:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[C:4]-[N;H0;D3;+0:5](-` | 179 | 34 | 19 | 27 | 29 | 0 |
| 59 | 1609 | `[O;H0;D1;+0:1]=[CH;D2;+0:2]-[c:3]>>[OH;D1;+0:1]-[CH2;D2;+0:2]-[c:3]` | 927 | 34 | 9 | 1 | 33 | 0 |
| 60 | 1591 | `Br-[CH2;D2;+0:1]-[c:2].[OH;D1;+0:3]-[c:4]>>[c:2]-[CH2;D2;+0:1]-[O;H0;D2;+0:3]-[c` | 58 | 33 | 4 | 1 | 25 | 0 |
| 61 | 1567 | `O-[C;H0;D3;+0:1](=[O;D1;H0:2])-[c:3].[NH2;D1;+0:4]-[c:5]>>[O;D1;H0:2]=[C;H0;D3;+` | 227 | 111 | 25 | 8 | 67 | 0 |
| 62 | 1565 | `Cl-[C;H0;D3;+0:1](-[#8:2])=[O;D1;H0:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[#8:2]-[C;H0;D3` | 76 | 26 | 4 | 1 | 23 | 0 |
| 63 | 1565 | `Cl-S(=O)-[Cl;H0;D1;+0:1].O-[C;H0;D3;+0:2](=[O;D1;H0:3])-[c:4]>>[Cl;H0;D1;+0:1]-[` | 100 | 34 | 7 | 2 | 16 | 0 |
| 64 | 1564 | `[NH2;D1;+0:1]-[c:2].[O;D1;H0:3]=[C;H0;D2;+0:4]=[N;H0;D2;+0:5]-[c:6]>>[O;D1;H0:3]` | 56 | 44 | 4 | 0 | 24 | 0 |
| 65 | 1560 | `O=[C;H0;D3;+0:1](-[OH;D1;+0:2])-[c:3]:[c:4]:[#7;a:5].[C:6]-[NH2;D1;+0:7]>>[#7;a:` | 76 | 59 | 5 | 5 | 32 | 0 |
| 66 | 1559 | `Cl-[C;H0;D3;+0:1](-[#8:2])=[O;D1;H0:3].[C:4]-[NH2;D1;+0:5]>>[#8:2]-[C;H0;D3;+0:1` | 69 | 32 | 5 | 1 | 29 | 0 |
| 67 | 1550 | `O-[C;H0;D3;+0:1](-[C:2])=[O;D1;H0:3].[C:4]-[NH2;D1;+0:5]>>[C:4]-[NH;D2;+0:5]-[C;` | 785 | 243 | 32 | 4 | 165 | 0 |
| 68 | 1533 | `Br-[CH2;D2;+0:1]-[C:2](-[#8:3])=[O;D1;H0:4].[OH;D1;+0:5]-[c:6]>>[#8:3]-[C:2](=[O` | 26 | 19 | 6 | 1 | 19 | 0 |
| 69 | 1510 | `O-[CH2;D2;+0:1]-[C:2].[OH;D1;+0:3]-[c:4]>>[C:2]-[CH2;D2;+0:1]-[O;H0;D2;+0:3]-[c:` | 429 | 67 | 16 | 1 | 54 | 0 |
| 70 | 1503 | `O-[NH3+;D1:1].[N;H0;D1;+0:2]#[C;H0;D2;+0:3]-[c;H0;D3;+0:4](:[c:5]):[c:6].[O-]-[C` | 0 | 0 | 0 | 0 | 0 | 0 |
| 71 | 1496 | `O=C1-C-C-C(=O)-N-1-[Br;H0;D1;+0:1].[c:2]:[cH;D2;+0:3]:[c:4]>>[Br;H0;D1;+0:1]-[c;` | 113 | 26 | 6 | 0 | 25 | 0 |
| 72 | 1488 | `[C:1]-[C;H0;D2;+0:2]#[N;H0;D1;+0:3]>>[C:1]-[CH2;D2;+0:2]-[NH2;D1;+0:3]` | 665 | 30 | 5 | 11 | 29 | 0 |
| 73 | 1481 | `[O;D1;H0:1]=[C:2]-[OH;D1;+0:3]>>[O-;H0;D1:3]-[C:2]=[O;D1;H0:1]` | 4302 | 45 | 10 | 2 | 38 | 0 |
| 74 | 1469 | `C-C(-C)(-C)-O-C(=O)-[NH;D2;+0:1]-[C:2]-[C:3](-[#7:4])=[O;D1;H0:5]>>[#7:4]-[C:3](` | 73 | 27 | 6 | 0 | 23 | 0 |
| 75 | 1452 | `[C:1]-[C;H0;D3;+0:2](=[O;H0;D1;+0:3])-[c:4]>>[C:1]-[CH;D3;+0:2](-[OH;D1;+0:3])-[` | 1017 | 47 | 14 | 1 | 44 | 0 |
| 76 | 1447 | `O=[C;H0;D3;+0:1](-[C:2])-[OH;D1;+0:3].[NH2;D1;+0:4]-[c:5]>>[C:2]-[C;H0;D3;+0:1](` | 286 | 113 | 33 | 11 | 93 | 0 |
| 77 | 1432 | `Cl-[c;H0;D3;+0:1](:[#7;a:2]):[#7;a:3].[C:4]-[NH2;D1;+0:5]>>[#7;a:2]:[c;H0;D3;+0:` | 68 | 29 | 5 | 0 | 16 | 0 |
| 78 | 1429 | `I-[CH3;D1;+0:1].[C:2]-[OH;D1;+0:3]>>[C:2]-[O;H0;D2;+0:3]-[CH3;D1;+0:1]` | 79 | 40 | 8 | 3 | 36 | 0 |
| 79 | 1401 | `O-[C;H0;D3;+0:1](-[C:2])=[O;D1;H0:3].[C:4]-[NH2;D1;+0:5]>>[C:2]-[C;H0;D3;+0:1](=` | 785 | 243 | 32 | 4 | 165 | 0 |
| 80 | 1370 | `C-[Si](-C)(-C)-[C;H0;D2;+0:1]#[C:2]>>[C:2]#[CH;D1;+0:1]` | 64 | 19 | 2 | 1 | 19 | 0 |
| 81 | 1363 | `C-C(=O)-O-[C;H0;D3;+0:1](-[C;D1;H3:2])=[O;D1;H0:3].[C:4]-[OH;D1;+0:5]>>[C:4]-[O;` | 83 | 28 | 3 | 9 | 25 | 0 |
| 82 | 1349 | `Cl-[c;H0;D3;+0:1](:[#7;a:2]):[#7;a:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[#7;a:2]:[c;H0;D` | 78 | 31 | 9 | 0 | 24 | 0 |
| 83 | 1341 | `Cl-[Si;H0;D4;+0:1](-[C:2])(-[C;D1;H3:3])-[C;D1;H3:4].[C:5]-[OH;D1;+0:6]>>[C:5]-[` | 56 | 35 | 10 | 3 | 32 | 0 |
| 84 | 1340 | `O=[CH;D2;+0:1]-[c:2]:[#7;a:3].[#7:4]-[C:5](=[O;D1;H0:6])-[CH2;D2;+0:7]-[c:8]>>[#` | 4 | 4 | 1 | 2 | 3 | 0 |
| 85 | 1328 | `O-[C;H0;D3;+0:1](-[C:2])=[O;D1;H0:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[C:2]-[C;H0;D3;+0` | 1030 | 170 | 30 | 9 | 124 | 0 |
| 86 | 1325 | `O=C(-O-C-c1:c:c:c:c:c:1)-[N;H0;D3;+0:1](-[C:2])-[C:3]>>[C:2]-[NH;D2;+0:1]-[C:3]` | 133 | 22 | 1 | 17 | 21 | 0 |
| 87 | 1293 | `Cl-[c;H0;D3;+0:1](:[#7;a:2]):[c:3].[C:4]-[NH2;D1;+0:5]>>[#7;a:2]:[c;H0;D3;+0:1](` | 167 | 91 | 30 | 7 | 52 | 0 |
| 88 | 1281 | `C-C-O-[C;H0;D3;+0:1](-[C:2])=[O;H0;D1;+0:3]>>[C:2]-[CH2;D2;+0:1]-[OH;D1;+0:3]` | 2579 | 34 | 10 | 0 | 32 | 0 |
| 89 | 1273 | `Cl-[S;H0;D4;+0:1](=[O;D1;H0:2])(=[O;D1;H0:3])-[c:4].[C:5]-[NH;D2;+0:6]-[C:7]>>[C` | 51 | 24 | 1 | 0 | 21 | 0 |
| 90 | 1272 | `Br-[c;H0;D3;+0:1](:[c:2]):[c:3]:[#7;a:4].O-B(-O)-[c;H0;D3;+0:5](:[c:6]):[c:7]>>[` | 71 | 52 | 25 | 28 | 36 | 0 |
| 91 | 1222 | `C-C(-C)(-C)-[O;H0;D2;+0:1]-[C;H0;D3;+0:2](-[C:3])=[O;H0;D1;+0:4]>>[C:3]-[C;H0;D3` | 337 | 59 | 7 | 0 | 51 | 0 |
| 92 | 1215 | `O=[C;H0;D3;+0:1](-[C:2])-[OH;D1;+0:3].[C:4]-[NH2;D1;+0:5]>>[C:4]-[NH;D2;+0:5]-[C` | 434 | 197 | 27 | 1 | 135 | 0 |
| 93 | 1204 | `Cl-[c;H0;D3;+0:1](:[#7;a:2]):[c:3]:[c:4]:[#7;a:5].[NH2;D1;+0:6]-[c:7]>>[#7;a:5]:` | 70 | 40 | 10 | 1 | 27 | 0 |
| 94 | 1193 | `O=C(-O-C-c1:c:c:c:c:c:1)-[NH;D2;+0:1]-[C:2]>>[C:2]-[NH2;D1;+0:1]` | 149 | 27 | 2 | 21 | 23 | 0 |
| 95 | 1167 | `Cl-[C;H0;D3;+0:1](-[#8:2])=[O;D1;H0:3].[NH2;D1;+0:4]-[c:5]>>[#8:2]-[C;H0;D3;+0:1` | 63 | 30 | 5 | 0 | 28 | 0 |
| 96 | 1148 | `C-C(=O)-[NH;D2;+0:1]-[c:2]>>[NH2;D1;+0:1]-[c:2]` | 662 | 35 | 13 | 0 | 28 | 0 |
| 97 | 1141 | `[N;H0;D1;+0:1]#[C;H0;D2;+0:2]-[c:3]>>[NH2;D1;+0:1]-[CH2;D2;+0:2]-[c:3]` | 993 | 24 | 4 | 15 | 23 | 0 |
| 98 | 1135 | `Cl-[c;H0;D3;+0:1](:[#7;a:2]):[c:3].[OH;D1;+0:4]-[c:5]>>[#7;a:2]:[c;H0;D3;+0:1](-` | 51 | 33 | 14 | 0 | 26 | 0 |
| 99 | 1125 | `[O;D1;H0:1]=[C:2]-[O;H0;D2;+0:3]-C-c1:c:c:c:c:c:1>>[O;D1;H0:1]=[C:2]-[OH;D1;+0:3` | 677 | 28 | 4 | 19 | 28 | 0 |
| 100 | 1124 | `Br-[CH2;D2;+0:1]-[c:2].[OH;D1;+0:3]-[c:4]>>[c:4]-[O;H0;D2;+0:3]-[CH2;D2;+0:1]-[c` | 58 | 33 | 4 | 1 | 25 | 0 |

## 有条件的模板（前 30）

### support 21400 · `O=[N+;H0;D3:1](-[O-])-[c:2]>>[NH2;D1;+0:1]-[c:2]`

* fired 1535 / match 345；温度 66 / 催化剂 254 / 溶剂 329 / 试剂 0
* 温度：{'80 1': 14, '70 1': 7, '100 1': 6, '90 1': 6, '60 1': 6, '50 1': 6, '75 1': 5, '65 1': 4, '0 1': 2, '45 1': 1, '95 1': 1, '105 1': 1, '55 1': 1, '22.5 1': 1, '20 1': 1, '30 1': 1, '52.5 1': 1, '110 1': 1, '25 1': 1}
* 催化剂：{'Pd/C': 52, 'iron': 47, 'palladium on carbon': 22, 'zinc': 11, 'Iron': 10, 'Raney nickel': 8, 'Raney Nickel': 8, 'palladium on charcoal': 7, 'palladium-carbon': 7, 'palladium carbon': 7, 'Ni': 6, 'Fe': 6, 'Pd—C': 6, 'platinum on carbon': 5, 'palladium': 5, 'palladium-on-carbon': 5, 'Pd-C': 3, 'Palladium on carbon': 3, 'Pd': 3, 'Pd on carbon': 3}
* 溶剂：{'ethanol': 76, 'methanol': 56, 'water': 42, 'MeOH': 37, 'ethyl acetate': 35, 'EtOH': 22, 'acetic acid': 19, 'tetrahydrofuran': 17, 'EtOAc': 15, 'THF': 14, 'H2O': 6, 'Water': 5, 'acetonitrile': 4, 'toluene': 4, 'HCl': 4, 'AcOH': 4, 'dioxane': 3, 'hydrochloric acid': 3, 'DMF': 3, 'dichloromethane': 2}
* 示例：[{'rid': 'ord-67ec3bcdf85a4cd095b46cc07afa68ed', 'temp': '45 1', 'catalysts': ['Pd/C'], 'solvents': ['water'], 'reagents': []}]

### support 14521 · `C-[O;H0;D2;+0:1]-[C:2]=[O;D1;H0:3]>>[O;D1;H0:3]=[C:2]-[OH;D1;+0:1]`

* fired 7455 / match 743；温度 166 / 催化剂 30 / 溶剂 651 / 试剂 0
* 温度：{'50 1': 30, '60 1': 23, '80 1': 14, '0 1': 13, '25 1': 12, '70 1': 8, '40 1': 7, '55 1': 7, '90 1': 6, '100 1': 6, '65 1': 4, '120 1': 4, '45 1': 4, '30 1': 3, '20 1': 3, '75 1': 2, '35 1': 2, '68 1': 2, '95 1': 2, '23 1': 2}
* 催化剂：{'Pd(PPh3)4': 5, 'palladium on carbon': 4, 'Pd/C': 4, 'palladium carbon': 3, 'zinc': 3, 'palladium on charcoal': 3, 'palladium': 2, 'acetic acid': 1, 'palladium-on-carbon': 1, 'Pd(Ph3P)4': 1, 'Pd on carbon': 1, 'palladium-on-charcoal': 1, 'Pd on activated charcoal': 1}
* 溶剂：{'water': 129, 'methanol': 111, 'ethanol': 101, 'THF': 88, 'tetrahydrofuran': 68, 'MeOH': 55, 'dioxane': 28, 'H2O': 22, 'dichloromethane': 22, 'EtOH': 18, 'NaOH': 14, 'CH2Cl2': 12, 'ethyl acetate': 11, 'HCl': 10, 'EtOAc': 9, 'hydrochloric acid': 9, 'trifluoroacetic acid': 8, 'acetic acid': 7, 'THF MeOH': 7, '1,4-dioxane': 7}
* 示例：[{'rid': 'ord-4f8eca8686f04fab850d92ff0dd05c7a', 'temp': '75 1', 'catalysts': [], 'solvents': ['THF'], 'reagents': []}]

### support 12618 · `C-C-[O;H0;D2;+0:1]-[C:2]=[O;D1;H0:3]>>[O;D1;H0:3]=[C:2]-[OH;D1;+0:1]`

* fired 5301 / match 405；温度 89 / 催化剂 11 / 溶剂 348 / 试剂 0
* 温度：{'50 1': 13, '80 1': 10, '60 1': 10, '0 1': 10, '40 1': 5, '55 1': 5, '25 1': 4, '100 1': 4, '70 1': 3, '30 1': 3, '65 1': 3, '20 1': 3, '45 1': 3, '95 1': 2, '90 1': 2, '130 1': 2, '120 1': 2, '75 1': 1, '35 1': 1, '140 1': 1}
* 催化剂：{'Pd(PPh3)4': 4, 'zinc': 3, 'acetic acid': 1, 'PdCl2': 1, 'Pd(Ph3P)4': 1, 'palladium on charcoal': 1}
* 溶剂：{'ethanol': 75, 'water': 63, 'methanol': 39, 'THF': 38, 'tetrahydrofuran': 25, 'dichloromethane': 21, 'dioxane': 16, 'MeOH': 15, 'EtOH': 12, 'CH2Cl2': 10, 'H2O': 8, 'hydrochloric acid': 8, 'HCl': 7, 'trifluoroacetic acid': 7, 'DCM': 5, 'NaOH': 5, 'acetic acid': 5, 'ethyl acetate': 5, 'acetonitrile': 4, 'methylene chloride': 4}
* 示例：[{'rid': 'ord-4f8eca8686f04fab850d92ff0dd05c7a', 'temp': '75 1', 'catalysts': [], 'solvents': ['THF'], 'reagents': []}]

### support 10316 · `C-C(-C)(-C)-O-C(=O)-[N;H0;D3;+0:1](-[C:2])-[C:3]>>[C:2]-[NH;D2;+0:1]-[C:3]`

* fired 900 / match 206；温度 16 / 催化剂 1 / 溶剂 181 / 试剂 0
* 温度：{'0 1': 4, '20 1': 2, '45 1': 2, '42.5 1': 1, '100 1': 1, '50 1': 1, '60 1': 1, '80 1': 1, '-78 1': 1, '90 1': 1, '40 1': 1}
* 催化剂：{'zinc bromide': 1}
* 溶剂：{'DCM': 34, 'dioxane': 27, 'dichloromethane': 27, 'CH2Cl2': 15, 'MeOH': 14, 'methanol': 11, 'ethyl acetate': 11, '1,4-dioxane': 11, 'methylene chloride': 9, 'chloroform': 5, 'EtOAc': 4, 'ether': 4, 'HCl': 3, 'ethanol': 3, 'trifluoroacetic acid': 3, 'TFA': 3, 'THF': 2, '1,4-Dioxane': 2, 'Et2O': 2, 'CHCl3': 2}
* 示例：[{'rid': 'ord-e90368ffd2234df394e85e5cab1a5b4f', 'temp': '42.5 1', 'catalysts': [], 'solvents': ['methanol'], 'reagents': []}]

### support 7497 · `C-[O;H0;D2;+0:1]-[c:2]>>[OH;D1;+0:1]-[c:2]`

* fired 5224 / match 240；温度 54 / 催化剂 50 / 溶剂 211 / 试剂 0
* 温度：{'0 1': 12, '200 1': 4, '120 1': 4, '-78 1': 3, '160 1': 3, '50 1': 3, '70 1': 2, '80 1': 2, '140 1': 2, '195 1': 1, '165 1': 1, '68 1': 1, '105 1': 1, '60 1': 1, '75 1': 1, '3 1': 1, '100 1': 1, '25 1': 1, '-15 1': 1, '90 1': 1}
* 催化剂：{'Pd/C': 12, 'palladium on carbon': 9, 'palladium on charcoal': 3, 'Pd—C': 3, 'palladium-on-carbon': 2, 'Palladium on carbon': 2, 'palladium-carbon': 2, 'palladium/carbon': 2, 'Pd on activated carbon': 2, 'Pd on charcoal': 1, 'Pd': 1, 'Ni': 1, 'Palladium on charcoal': 1, 'Pd(OH)2': 1, 'palladium on activated charcoal': 1, 'palladium carbon': 1, 'palladium hydroxide': 1, 'palladium acetate': 1, 'Pd(OH)2 on Carbon': 1, 'hexadecyltrimethylammonium bromide': 1}
* 溶剂：{'dichloromethane': 35, 'ethanol': 20, 'methanol': 19, 'methylene chloride': 14, 'CH2Cl2': 14, 'DCM': 14, 'water': 14, 'acetic acid': 13, 'ethyl acetate': 9, 'THF': 6, 'EtOH': 6, 'MeOH': 6, 'chloroform': 4, 'N,N-dimethylformamide': 4, 'EtOAc': 4, 'dioxane': 3, 'benzene': 3, 'tetrahydrofuran': 3, 'TFA': 3, 'HBr': 3}
* 示例：[{'rid': 'ord-e71cb2ebf2654d4ba5d844ad5a953bf8', 'temp': '195 1', 'catalysts': [], 'solvents': [], 'reagents': []}]

### support 6158 · `Br-[CH2;D2;+0:1]-[C:2].[OH;D1;+0:3]-[c:4]>>[C:2]-[CH2;D2;+0:1]-[O;H0;D2;+0:3]-[c:4]`

* fired 162 / match 115；温度 41 / 催化剂 9 / 溶剂 103 / 试剂 0
* 温度：{'80 1': 8, '60 1': 5, '70 1': 4, '90 1': 3, '50 1': 3, '100 1': 3, '3 1': 2, '0 1': 2, '65 1': 2, '165 1': 2, '25 1': 1, '45 1': 1, '54.5 1': 1, '55 1': 1, '40 1': 1, '4 1': 1, '110 1': 1}
* 催化剂：{'potassium iodide': 2, 'tetrabutyl ammonium chloride': 1, 'Aliquat 336': 1, 'Potassium iodide': 1, 'tetra-n-butylammonium bromide': 1, 'tetrabutylammonium iodide': 1, 'tetrabuylammonium iodide': 1, 'copper': 1}
* 溶剂：{'DMF': 22, 'acetone': 20, 'dimethylformamide': 13, 'N,N-dimethylformamide': 11, 'water': 10, 'ethyl acetate': 8, 'acetonitrile': 7, 'diethyl ether': 4, 'ether': 4, 'methyl ethyl ketone': 2, 'ethanol': 2, 'EtOAc': 2, '2-butanone': 2, 'methylene chloride': 2, 'dichloromethane': 1, 'methanol': 1, 'methylcellosolve': 1, 'chloroform': 1, 'toluene DMF': 1, 'toluene': 1}
* 示例：[{'rid': 'ord-000cebf4787344f1bf7d418a9168b1b4', 'temp': '', 'catalysts': ['tetrabutyl ammonium chloride'], 'solvents': ['diethyl ether', 'ether'], 'reagents': []}]

### support 5381 · `C-C(-C)(-C)-O-C(=O)-[NH;D2;+0:1]-[C:2]>>[C:2]-[NH2;D1;+0:1]`

* fired 584 / match 105；温度 11 / 催化剂 1 / 溶剂 86 / 试剂 0
* 温度：{'25 1': 4, '0 1': 3, '5 1': 2, '50 1': 1, '2.5 1': 1}
* 催化剂：{'H2 Pd': 1}
* 溶剂：{'dichloromethane': 17, 'dioxane': 16, 'DCM': 10, 'CH2Cl2': 7, 'ethyl acetate': 6, 'HCl': 4, 'ethanol': 4, 'EtOAc': 3, 'methanol': 3, 'trifluoroacetic acid': 3, 'methylene chloride': 3, 'ether': 3, 'MeOH': 3, 'acetic acid': 2, 'CH3OH': 2, 'TFA': 2, '1,4-dioxane': 2, 'chloroform': 1, '2-methyltetrahydrofuran': 1, 'water': 1}
* 示例：[{'rid': 'ord-157b347806e5402d819b7c9214a3f0d4', 'temp': '', 'catalysts': [], 'solvents': [], 'reagents': []}]

### support 4994 · `Cl-[c;H0;D3;+0:1](:[#7;a:2]):[#7;a:3].[NH2;D1;+0:4]-[c:5]>>[#7;a:2]:[c;H0;D3;+0:1](-[NH;D2;+0:4]-[c:5]):[#7;a:3]`

* fired 113 / match 59；温度 21 / 催化剂 10 / 溶剂 26 / 试剂 0
* 温度：{'120 1': 3, '80 1': 3, '100 1': 3, '150 1': 2, '60 1': 1, '200 1': 1, '170 1': 1, '130 1': 1, '175 1': 1, '75 1': 1, '110 1': 1, '140 1': 1, '116 1': 1, '160 1': 1}
* 催化剂：{'palladium acetate': 3, 'palladium(II) acetate': 2, 'Pd(OAc)2': 2, 'Pd2(dba)3': 1, 'palladium(II)acetate': 1, 'Zinc(II) chloride': 1}
* 溶剂：{'dioxane': 6, '1,4-dioxane': 4, 'iPrOH': 2, 'MeOH': 2, 'DMF': 1, 'ethylene glycol': 1, 'dimethylformamide': 1, 'DCM': 1, 'i-PrOH': 1, 'trifluoroethanol': 1, 'THF': 1, 'acetic acid': 1, 'DME': 1, 'n-hexanes EtOAc': 1, 'H2O': 1, 'ethyl acetate': 1, 'toluene': 1, 'dichloromethane': 1, 'butyl alcohol': 1, 'DCE': 1}
* 示例：[{'rid': 'ord-6319f4d90ee340cbb34c2715c3d9de01', 'temp': '60 1', 'catalysts': [], 'solvents': ['DMF'], 'reagents': []}]

### support 4335 · `Cl-[S;H0;D4;+0:1](-[C;D1;H3:2])(=[O;D1;H0:3])=[O;D1;H0:4].[C:5]-[OH;D1;+0:6]>>[C:5]-[O;H0;D2;+0:6]-[S;H0;D4;+0:1](-[C;D1;H3:2])(=[O;D1;H0:3])=[O;D1;H0:4]`

* fired 115 / match 69；温度 19 / 催化剂 1 / 溶剂 61 / 试剂 0
* 温度：{'0 1': 14, '-10 1': 1, '35 1': 1, '130 1': 1, '-20 1': 1, '-78 1': 1}
* 催化剂：{'N,N-dimethylpyridin-4-amine': 1}
* 溶剂：{'dichloromethane': 24, 'methylene chloride': 10, 'CH2Cl2': 10, 'ethyl acetate': 6, 'water': 6, 'THF': 4, 'DCM': 3, 'EtOAc': 3, 'tetrahydrofuran': 2, 'triethylamine': 2, 'brine': 1, 'DMF': 1, 'N,N-dimethylformamide': 1, 'acetonitrile THF': 1, 'toluene': 1, 'chloroform': 1, 'pyridine': 1, 'TEA': 1}
* 示例：[{'rid': 'ord-13653be87d9a426aafa7e7ae72c1fdf7', 'temp': '', 'catalysts': [], 'solvents': ['methylene chloride'], 'reagents': []}]

### support 4268 · `C-[O;H0;D2;+0:1]-[C;H0;D3;+0:2](-[C:3])=[O;H0;D1;+0:4]>>[C:3]-[C;H0;D3;+0:2](=[O;H0;D1;+0:1])-[OH;D1;+0:4]`

* fired 3739 / match 443；温度 87 / 催化剂 25 / 溶剂 389 / 试剂 0
* 温度：{'50 1': 16, '60 1': 15, '25 1': 11, '0 1': 10, '70 1': 5, '55 1': 5, '90 1': 3, '40 1': 3, '80 1': 3, '30 1': 2, '20 1': 2, '95 1': 2, '100 1': 2, '65 1': 1, '47.5 1': 1, '68 1': 1, '18 1': 1, '130 1': 1, '12.5 1': 1, '140 1': 1}
* 催化剂：{'palladium on carbon': 4, 'Pd/C': 4, 'zinc': 3, 'Pd(PPh3)4': 3, 'palladium carbon': 2, 'palladium on charcoal': 2, 'acetic acid': 1, 'palladium': 1, 'palladium-on-carbon': 1, 'Pd(Ph3P)4': 1, 'Pd on carbon': 1, 'palladium-on-charcoal': 1, 'Pd on activated charcoal': 1}
* 溶剂：{'water': 67, 'ethanol': 60, 'methanol': 56, 'THF': 46, 'tetrahydrofuran': 37, 'MeOH': 32, 'dioxane': 23, 'dichloromethane': 17, 'H2O': 13, 'CH2Cl2': 12, 'ethyl acetate': 10, 'NaOH': 10, 'EtOH': 9, 'trifluoroacetic acid': 8, 'HCl': 7, '1,4-dioxane': 5, 'methylene chloride': 5, 'EtOAc': 4, 'diethyl ether': 4, 'DCM': 4}
* 示例：[{'rid': 'ord-2900eeef6bee4f96854b610d5c6665dc', 'temp': '', 'catalysts': [], 'solvents': ['H2O'], 'reagents': []}]

### support 4028 · `C-C-[O;H0;D2;+0:1]-[C;H0;D3;+0:2](-[C:3])=[O;H0;D1;+0:4]>>[C:3]-[C;H0;D3;+0:2](=[O;H0;D1;+0:1])-[OH;D1;+0:4]`

* fired 2579 / match 262；温度 52 / 催化剂 10 / 溶剂 230 / 试剂 0
* 温度：{'50 1': 9, '60 1': 8, '0 1': 7, '55 1': 5, '25 1': 4, '30 1': 2, '20 1': 2, '95 1': 2, '80 1': 2, '70 1': 2, '100 1': 2, '40 1': 2, '65 1': 1, '130 1': 1, '140 1': 1, '160 1': 1, '90 1': 1}
* 催化剂：{'zinc': 3, 'Pd(PPh3)4': 3, 'acetic acid': 1, 'PdCl2': 1, 'Pd(Ph3P)4': 1, 'palladium on charcoal': 1}
* 溶剂：{'ethanol': 43, 'water': 34, 'THF': 25, 'methanol': 24, 'dichloromethane': 17, 'tetrahydrofuran': 14, 'dioxane': 13, 'MeOH': 12, 'CH2Cl2': 10, 'trifluoroacetic acid': 7, 'EtOH': 6, 'HCl': 5, 'H2O': 5, 'DCM': 4, 'NaOH': 4, 'ethyl acetate': 4, 'acetonitrile': 3, 'TFA': 3, 'methylene chloride': 3, 'isopropanol': 2}
* 示例：[{'rid': 'ord-ee01e8fa35e148bf874c25c944de280c', 'temp': '', 'catalysts': [], 'solvents': [], 'reagents': []}]

### support 4010 · `O=[C;H0;D3;+0:1](-[OH;D1;+0:2])-[c:3].[C:4]-[NH2;D1;+0:5]>>[C:4]-[NH;D2;+0:5]-[C;H0;D3;+0:1](=[O;H0;D1;+0:2])-[c:3]`

* fired 331 / match 236；温度 23 / 催化剂 13 / 溶剂 134 / 试剂 0
* 温度：{'0 1': 6, '25 1': 4, '40 1': 2, '50 1': 2, '-10 1': 1, '70 1': 1, '60 1': 1, '-5 1': 1, '23 1': 1, '2.5 1': 1, '80 1': 1, '-30 1': 1, '17 1': 1}
* 催化剂：{'DMAP': 6, '4-dimethylaminopyridine': 3, 'DMF': 2, '4-Dimethylaminopyridine': 1, 'N,N-dimethylformaldehyde': 1}
* 溶剂：{'DMF': 42, 'water': 22, 'dichloromethane': 17, 'N,N-dimethylformamide': 12, 'ethyl acetate': 11, 'dimethylformamide': 10, 'DCM': 10, 'THF': 9, 'tetrahydrofuran': 8, 'triethylamine': 8, 'methylene chloride': 6, 'CH2Cl2': 5, 'chloroform': 4, 'EtOAc': 3, 'DMA': 3, 'Water': 3, 'DMSO': 3, 'acetonitrile': 3, 'tert-butanol': 2, 'CHCl3': 2}
* 示例：[{'rid': 'ord-43dc13e19e6d4983baebc448eadd34c1', 'temp': '', 'catalysts': [], 'solvents': [], 'reagents': []}]

### support 3646 · `[c:1]-[O;H0;D2;+0:2]-C-c1:c:c:c:c:c:1>>[OH;D1;+0:2]-[c:1]`

* fired 535 / match 62；温度 7 / 催化剂 45 / 溶剂 59 / 试剂 0
* 温度：{'50 1': 2, '68 1': 1, '65 1': 1, '-78 1': 1, '0 1': 1, '85 1': 1}
* 催化剂：{'Pd/C': 12, 'palladium on carbon': 9, 'palladium on charcoal': 3, 'Pd—C': 3, 'palladium-on-carbon': 2, 'Palladium on carbon': 2, 'palladium-carbon': 2, 'palladium/carbon': 2, 'Pd on activated carbon': 2, 'Pd on charcoal': 1, 'Palladium on charcoal': 1, 'Pd(OH)2': 1, 'palladium on activated charcoal': 1, 'palladium carbon': 1, 'palladium hydroxide': 1, 'Pd(OH)2 on Carbon': 1, 'palladium-on-charcoal': 1}
* 溶剂：{'ethanol': 15, 'methanol': 8, 'ethyl acetate': 6, 'MeOH': 6, 'EtOH': 5, 'THF': 3, 'TFA': 3, 'EtOAc': 3, 'trifluoroacetic acid': 2, 'acetonitrile': 2, 'methanol ethyl acetate': 2, 'DCM': 2, 'dioxane': 1, 'ethyl acetate methanol': 1, 'THF ethyl acetate': 1, 'acetic acid': 1, 'methylene chloride': 1, 'methylenedichloride': 1, 'tetrahydrofuran': 1, 'hexanes': 1}
* 示例：[{'rid': 'ord-f369b6f770fb42b39d21ef9339c14116', 'temp': '', 'catalysts': ['Pd/C'], 'solvents': ['THF'], 'reagents': []}]

### support 3481 · `Br-[CH2;D2;+0:1]-[C:2].[C:3]-[NH;D2;+0:4]-[C:5]>>[C:3]-[N;H0;D3;+0:4](-[CH2;D2;+0:1]-[C:2])-[C:5]`

* fired 212 / match 142；温度 29 / 催化剂 6 / 溶剂 109 / 试剂 0
* 温度：{'60 1': 6, '50 1': 4, '80 1': 3, '100 1': 3, '5 1': 2, '90 1': 2, '25 1': 2, '110 1': 1, '120 1': 1, '95 1': 1, '170 1': 1, '75 1': 1, '70 1': 1, '77 1': 1}
* 催化剂：{'tetrabutylammonium sulfate': 2, 'tetrabutylammonium bromide': 1, 'potassium iodide': 1, 'tetra-n-butylammonium hydrogensulfate': 1, 'tetra-butylammonium hydrogen sulfate': 1}
* 溶剂：{'acetonitrile': 31, 'DMF': 18, 'dimethylformamide': 9, 'THF': 9, 'ethanol': 9, 'water': 8, 'acetone': 6, 'EtOAc': 5, 'N,N-dimethylformamide': 5, 'CH3CN': 4, 'tetrahydrofuran': 3, 'ethyl acetate': 3, 'benzene': 3, 'methanol': 3, 'toluene': 3, 'H2O': 3, 'methylene chloride': 3, 'ether': 3, 'methyl isobutyl ketone': 3, 'dimethylsulfoxide': 2}
* 示例：[{'rid': 'ord-e8381d73f4f9423dbff70d4f1bb4f249', 'temp': '', 'catalysts': [], 'solvents': ['tetrahydrofuran'], 'reagents': []}]

### support 3462 · `C-C(-C)(-C)-[O;H0;D2;+0:1]-[C:2]=[O;D1;H0:3]>>[O;D1;H0:3]=[C:2]-[OH;D1;+0:1]`

* fired 2117 / match 78；温度 8 / 催化剂 0 / 溶剂 60 / 试剂 0
* 温度：{'0 1': 3, '25 1': 2, '45 1': 1, '70 1': 1, '100 1': 1}
* 催化剂：—
* 溶剂：{'dichloromethane': 17, 'CH2Cl2': 10, 'trifluoroacetic acid': 7, 'DCM': 5, 'methylene chloride': 4, 'TFA': 3, 'dioxane': 3, 'water': 3, 'Petroleum ether': 2, 'diethyl ether': 2, 'acetonitrile': 1, 'dichloroethane': 1, 'di-chloromethane': 1, 'HCl': 1, 'formic acid': 1, 'hydrogen chloride': 1, 'H2O': 1, 'dioxanes': 1, 'hydrochloric acid': 1, 'Ethyl acetate': 1}
* 示例：[{'rid': 'ord-ee01e8fa35e148bf874c25c944de280c', 'temp': '', 'catalysts': [], 'solvents': [], 'reagents': []}]

### support 3192 · `O-[C;H0;D3;+0:1](=[O;D1;H0:2])-[c:3].[C:4]-[NH2;D1;+0:5]>>[C:4]-[NH;D2;+0:5]-[C;H0;D3;+0:1](=[O;D1;H0:2])-[c:3]`

* fired 464 / match 272；温度 28 / 催化剂 14 / 溶剂 149 / 试剂 0
* 温度：{'0 1': 6, '25 1': 4, '40 1': 2, '50 1': 2, '80 1': 2, '100 1': 2, '-10 1': 1, '70 1': 1, '60 1': 1, '-5 1': 1, '23 1': 1, '2.5 1': 1, '10 1': 1, '-30 1': 1, '170 1': 1, '17 1': 1}
* 催化剂：{'DMAP': 6, '4-dimethylaminopyridine': 4, 'DMF': 2, '4-Dimethylaminopyridine': 1, 'N,N-dimethylformaldehyde': 1}
* 溶剂：{'DMF': 43, 'water': 24, 'dichloromethane': 17, 'ethyl acetate': 13, 'N,N-dimethylformamide': 12, 'dimethylformamide': 10, 'DCM': 10, 'THF': 9, 'triethylamine': 9, 'tetrahydrofuran': 8, 'methylene chloride': 6, 'CH2Cl2': 5, 'chloroform': 5, 'EtOAc': 4, 'DMA': 3, 'Water': 3, 'methanol': 3, 'DMSO': 3, 'acetonitrile': 3, 'tert-butanol': 2}
* 示例：[{'rid': 'ord-43dc13e19e6d4983baebc448eadd34c1', 'temp': '', 'catalysts': [], 'solvents': [], 'reagents': []}]

### support 3178 · `Cl-[C;H0;D3;+0:1](=[O;D1;H0:2])-[c:3].[NH2;D1;+0:4]-[c:5]>>[O;D1;H0:2]=[C;H0;D3;+0:1](-[c:3])-[NH;D2;+0:4]-[c:5]`

* fired 114 / match 87；温度 6 / 催化剂 9 / 溶剂 58 / 试剂 0
* 温度：{'60 1': 2, '100 1': 1, '0 1': 1, '50 1': 1, '-5 1': 1}
* 催化剂：{'4-dimethylaminopyridine': 3, 'DMAP': 2, '4-dimethylamino-pyridine': 1, '4-(dimethylamino)pyridine': 1, 'ether': 1, 'platinum': 1}
* 溶剂：{'dichloromethane': 14, 'pyridine': 10, 'methylene chloride': 7, 'THF': 6, 'DCM': 5, 'CH2Cl2': 5, 'water': 4, 'tetrahydrofuran': 3, 'acetonitrile': 3, 'methanol': 3, 'Ethyl acetate hexane': 1, 'triethylamine': 1, 'DMF': 1, '1,2-dichloroethane': 1, 'acetic acid': 1, 'toluene': 1, 'dioxane': 1, 'MeCN': 1, 'acetic acid, acetic anhydride': 1, 'potassium acetate': 1}
* 示例：[{'rid': 'ord-26852837714a48d0acc9eda7e9ce55f7', 'temp': '', 'catalysts': [], 'solvents': ['methylene chloride'], 'reagents': []}]

### support 3070 · `O=[N+;H0;D3:1](-[O-])-[c:2]:[c:3]:[#7;a:4]>>[#7;a:4]:[c:3]:[c:2]-[NH2;D1;+0:1]`

* fired 217 / match 61；温度 15 / 催化剂 43 / 溶剂 57 / 试剂 0
* 温度：{'80 1': 4, '75 1': 2, '50 1': 2, '65 1': 1, '105 1': 1, '90 1': 1, '22.5 1': 1, '30 1': 1, '52.5 1': 1, '70 1': 1}
* 催化剂：{'Pd/C': 8, 'iron': 6, 'palladium on carbon': 5, 'platinum on carbon': 4, 'zinc': 3, 'palladium-carbon': 2, 'palladium-on-charcoal': 2, 'Platinum on carbon': 2, 'palladium hydroxide on carbon': 1, 'Pd—C': 1, 'Pd on carbon': 1, 'HCl': 1, 'Iron': 1, 'water': 1, 'palladium on activated carbon': 1, 'palladium carbon': 1, 'Pt/C': 1, 'palladium on charcoal': 1, 'Ni': 1, 'Pd': 1}
* 溶剂：{'ethanol': 14, 'methanol': 9, 'MeOH': 7, 'ethyl acetate': 5, 'acetonitrile': 4, 'tetrahydrofuran': 4, 'EtOH': 3, 'acetic acid': 3, 'water': 2, 'THF MeOH': 2, 'EtOAc': 2, 'isopropanol': 1, '2-methyl-2-propanol': 1, 'EtOH HOAc H2O': 1, 'IMS': 1, 'Water': 1, 'DMF': 1, 'THF': 1, 'dichloromethane': 1, 'HCl': 1}
* 示例：[{'rid': 'ord-aae0dad34e834b03a63c256ec63dadca', 'temp': '', 'catalysts': ['platinum on carbon'], 'solvents': ['acetonitrile', 'isopropanol'], 'reagents': []}]

### support 3039 · `Cl-[CH2;D2;+0:1]-[C:2].[C:3]-[NH;D2;+0:4]-[C:5]>>[C:3]-[N;H0;D3;+0:4](-[CH2;D2;+0:1]-[C:2])-[C:5]`

* fired 161 / match 81；温度 20 / 催化剂 3 / 溶剂 59 / 试剂 0
* 温度：{'80 1': 10, '70 1': 3, '60 1': 2, '100 1': 2, '55 1': 1, '82 1': 1, '30 1': 1}
* 催化剂：{'Br2': 1, 'tetrabutylammonium hydrogen sulfate': 1, 'tetrabutylammonium iodide': 1}
* 溶剂：{'acetonitrile': 13, 'N,N-dimethylformamide': 9, 'DMF': 9, 'water': 9, 'ether': 4, 'dimethylformamide': 3, 'toluene': 3, 'ethanol': 2, 'H2O': 2, 'MeCN': 2, 'dichloromethane': 2, 'THF': 2, 'THF EtOH': 1, 'diethyl ether': 1, 'EtOH': 1, 'n-hexane': 1, 'tetrahydrofuran': 1, '4-methyl-2-pentanone': 1, 'DCM': 1, 'n-butanol': 1}
* 示例：[{'rid': 'ord-e1dcf3764cea4e59a631d89d7f2b7e7d', 'temp': '', 'catalysts': [], 'solvents': [], 'reagents': []}]

### support 2653 · `C-C(-C)(-C)-[Si](-C)(-C)-[O;H0;D2;+0:1]-[C:2]>>[C:2]-[OH;D1;+0:1]`

* fired 152 / match 34；温度 7 / 催化剂 1 / 溶剂 34 / 试剂 0
* 温度：{'0 1': 4, '25 1': 1, '20 1': 1, '90 1': 1}
* 催化剂：{'acetyl chloride': 1, 'ammonium chloride': 1}
* 溶剂：{'THF': 23, 'methanol': 4, 'tetrahydrofuran': 3, 'ethyl acetate': 2, 'water': 2, 'acetic acid': 2, 'EA': 1, 'acetonitrile': 1, 'dimethylformamide': 1, 'ether': 1, 'ammonia': 1, 'EtOAc': 1, 'brine': 1, 'NaHCO3': 1, 'Diethyl ether': 1, 'ethanol': 1}
* 示例：[{'rid': 'ord-a9e5e1fe7109474dbd63453d82efc8ef', 'temp': '25 1', 'catalysts': [], 'solvents': ['tetrahydrofuran'], 'reagents': []}]

### support 2633 · `Br-[c;H0;D3;+0:1](:[c:2]):[c:3].O-B(-O)-[c;H0;D3;+0:4](:[c:5]):[c:6]>>[c:2]:[c;H0;D3;+0:1](-[c;H0;D3;+0:4](:[c:5]):[c:6]):[c:3]`

* fired 265 / match 210；温度 97 / 催化剂 130 / 溶剂 154 / 试剂 0
* 温度：{'100 1': 21, '90 1': 13, '80 1': 12, '110 1': 9, '85 1': 7, '75 1': 6, '70 1': 6, '120 1': 4, '95 1': 4, '140 1': 3, '150 1': 2, '160 1': 2, '105 1': 2, '130 1': 2, '22.5 1': 1, '82.5 1': 1, '135 1': 1, '62 1': 1}
* 催化剂：{'tetrakis(triphenylphosphine)palladium(0)': 21, 'Pd(PPh3)4': 17, 'Pd(dppf)Cl2': 17, 'tetrakis(triphenylphosphine)palladium': 9, 'PdCl2(dppf)': 5, 'PdCl2(PPh3)2': 4, 'Pd(OAc)2': 4, 'Palladium tetrakis(triphenylphosphine)': 3, 'Tetrakis(triphenylphosphine)palladium(0)': 3, 'palladium acetate': 3, '[1,1′-bis(diphenylphosphino)-ferrocene]dichloro palladium(II)': 2, 'tetrakis(triphenylphosphine) palladium(0)': 2, '[1,1′-bis(diphenylphosphino)ferrocene]dichloropalladium(II)': 2, 'Pd(PPh3)2Cl2': 2, 'Pd2(dba)3': 2, 'tris(dibenzylideneacetone)dipalladium(0)': 2, 'tetrakis(triphenylphosphine) palladium': 2, 'PdCl2(dppf) CH2Cl2': 2, 'palladium(II) acetate': 2, 'dichlorobis(triphenylphosphine)palladium': 1}
* 溶剂：{'water': 48, 'toluene': 31, 'dioxane': 28, 'ethanol': 18, 'DME': 9, 'ethyl acetate': 9, 'EtOAc': 8, 'H2O': 8, 'DMF': 8, '1,4-dioxane': 8, 'EtOH': 7, 'acetonitrile': 5, 'Water': 4, 'dimethoxyethane': 4, 'THF': 3, 'dioxane water': 3, '1,2-dimethoxyethane': 3, 'Toluene': 2, 'DME H2O': 2, 'NaHCO3': 2}
* 示例：[{'rid': 'ord-2e87ef03d13944988967e1bb4dcac910', 'temp': '', 'catalysts': [], 'solvents': [], 'reagents': []}]

### support 2627 · `Cl-[C;H0;D3;+0:1](-[C:2])=[O;D1;H0:3].[NH2;D1;+0:4]-[c:5]>>[C:2]-[C;H0;D3;+0:1](=[O;D1;H0:3])-[NH;D2;+0:4]-[c:5]`

* fired 172 / match 92；温度 13 / 催化剂 2 / 溶剂 71 / 试剂 0
* 温度：{'0 1': 6, '25 1': 3, '80 1': 1, '19 1': 1, '40 1': 1, '95 1': 1}
* 催化剂：{'4-dimethylaminopyridine': 1, 'DMAP': 1}
* 溶剂：{'tetrahydrofuran': 12, 'CH2Cl2': 8, 'methylene chloride': 7, 'THF': 6, 'dichloromethane': 6, 'pyridine': 5, 'DCM': 5, 'ethyl acetate': 4, 'DMF': 4, 'water': 3, 'EtOAc': 3, 'diethyl ether': 2, 'NMP': 2, 'acetonitrile': 2, 'ethanol': 1, 'dimethylformamide': 1, 'CH2Cl2 THF': 1, 'toluene': 1, 'chloroform': 1, 'ethyl acetate hexane': 1}
* 示例：[{'rid': 'ord-2e03a241be2b4b53bf88ccfacb21967f', 'temp': '', 'catalysts': [], 'solvents': ['ethanol', 'tetrahydrofuran'], 'reagents': []}]

### support 2543 · `[C:1]-[CH2;D2;+0:2]-[OH;D1;+0:3]>>[C:1]-[CH;D2;+0:2]=[O;H0;D1;+0:3]`

* fired 1431 / match 47；温度 15 / 催化剂 2 / 溶剂 45 / 试剂 0
* 温度：{'0 1': 6, '-78 1': 4, '23 1': 2, '-10 1': 2, '5 1': 1}
* 催化剂：{'manganese dioxide': 2}
* 溶剂：{'CH2Cl2': 12, 'methylene chloride': 8, 'water': 6, 'dichloromethane': 5, 'DMSO': 4, 'DCM': 3, 'ether': 3, 'benzene': 2, 'dimethylsulfoxide': 2, 'EtOAc': 1, 'diethyl ether': 1, 'solution': 1, 'methanol': 1, 'NaHCO3': 1, 'pyridine': 1, 'Methylene chloride': 1, 'triethylamine': 1, 'dimethyl sulfoxide': 1, 'H2O': 1, 'tetrahydrofuran': 1}
* 示例：[{'rid': 'ord-e5daab64725749169af83e097ae14fc0', 'temp': '23 1', 'catalysts': [], 'solvents': ['EtOAc'], 'reagents': []}]

### support 2513 · `O-[CH3;D1;+0:1].[O;D1;H0:2]=[C:3]-[OH;D1;+0:4]>>[CH3;D1;+0:1]-[O;H0;D2;+0:4]-[C:3]=[O;D1;H0:2]`

* fired 813 / match 70；温度 15 / 催化剂 2 / 溶剂 21 / 试剂 0
* 温度：{'60 1': 3, '70 1': 3, '0 1': 2, '-5 1': 1, '120 1': 1, '25 1': 1, '100 1': 1, '22 1': 1, '80 1': 1, '20 1': 1}
* 催化剂：{'sulfuric acid': 2}
* 溶剂：{'THF': 5, 'water': 4, 'methanol': 3, 'diethyl ether': 2, 'H2SO4': 1, 'ethyl acetate': 1, 'ethyl acetate petroleum ether': 1, 'EtOAc': 1, 'dioxane': 1, 'acetone': 1, 'methylene chloride': 1, 'sulfuric acid': 1, 'hydrogen chloride': 1, 'tetrahydrofuran': 1}
* 示例：[{'rid': 'ord-13f0bb09496b4e76add90df9bebc924b', 'temp': '', 'catalysts': [], 'solvents': ['methanol'], 'reagents': []}]

### support 2484 · `O=[CH;D2;+0:1]-[c:2].[C:3]-[NH2;D1;+0:4]>>[C:3]-[NH;D2;+0:4]-[CH2;D2;+0:1]-[c:2]`

* fired 163 / match 77；温度 6 / 催化剂 7 / 溶剂 56 / 试剂 0
* 温度：{'15 1': 1, '20 1': 1, '0 1': 1, '45 1': 1, '85 1': 1, '130 1': 1}
* 催化剂：{'acetic acid': 3, 'Raney nickel': 1, 'AcOH': 1, 'palladium-on-carbon': 1, 'H2O': 1}
* 溶剂：{'methanol': 22, 'MeOH': 7, 'dichloromethane': 6, '1,2-dichloroethane': 4, 'acetic acid': 3, 'acetonitrile': 3, 'ethyl acetate': 3, 'toluene': 3, 'DCM': 3, 'DCE': 2, 'ethanol': 2, 'Water': 2, 'triethylamine': 2, 'HOAc': 1, 'benzene': 1, 'chloroform': 1, 'N-methyl-2-pyrrolidinone': 1, 'trimethylorthoformate': 1, 'CH2Cl2': 1, 'NaHCO3': 1}
* 示例：[{'rid': 'ord-3838062fb5794b499372a71d6efce843', 'temp': '', 'catalysts': [], 'solvents': ['acetic acid', 'methanol'], 'reagents': []}]

### support 2428 · `Br-[c;H0;D3;+0:1](:[c:2]):[c:3].[C:4]#[CH;D1;+0:5]>>[C:4]#[C;H0;D2;+0:5]-[c;H0;D3;+0:1](:[c:2]):[c:3]`

* fired 77 / match 57；温度 15 / 催化剂 34 / 溶剂 35 / 试剂 0
* 温度：{'50 1': 4, '70 1': 4, '80 1': 3, '65 1': 1, '55 1': 1, '85 1': 1, '40 1': 1}
* 催化剂：{'CuI': 8, 'copper(I)iodide': 7, 'dichlorobis(triphenylphosphine)palladium(II)': 7, 'copper (I) iodide': 6, 'copper(I) iodide': 4, 'tetrakis(triphenylphosphine)palladium': 3, 'bis(triphenylphosphine) palladium (II) chloride': 3, 'bis(triphenylphosphine)palladium(II) chloride': 3, '(Ph3P)2PdCl2': 3, 'Pd(PPh3)2Cl2': 3, 'Pd(PPh3)4': 2, 'Bis-(triphenylphosphine)-palladium(II)dichloride': 1, 'bis(triphenylphosphine)palladium (II) chloride': 1, 'palladium (II) chloride': 1, 'bis(triphenylphosphine)palladium(II) dichloride': 1, 'bis(benzonitrile)dichloropalladium': 1, 'copper (II) acetate': 1, 'copper iodide': 1, 'PdCl2(PPh3)2': 1, 'bis (triphenylphosphine)-palladium (II) chloride': 1}
* 溶剂：{'triethylamine': 10, 'DMF': 7, 'tetrahydrofuran': 5, 'Et3N': 5, 'ethyl acetate': 5, 'water': 3, 'hexane': 3, 'THF': 2, 'triethyl amine': 1, 'ammonium hydroxide': 1, 'NEt3': 1, 'hexanes': 1, 'diisopropyl amine': 1, 'ether': 1, 'diisopropylamine': 1, 'methylene chloride': 1, 'Dioxane': 1, 'EtOAc': 1}
* 示例：[{'rid': 'ord-c1285cc3f48e45fcba3863c6b4ce2a19', 'temp': '65 1', 'catalysts': ['Bis-(triphenylphosphine)-palladium(II)dichloride', 'copper(I)iodide'], 'solvents': ['THF'], 'reagents': []}]

### support 2386 · `[C:1]-[N;H0;D3;+0:2](-C-c1:c:c:c:c:c:1)-[C:3]>>[C:1]-[NH;D2;+0:2]-[C:3]`

* fired 1094 / match 60；温度 7 / 催化剂 35 / 溶剂 55 / 试剂 0
* 温度：{'90 1': 3, '25 1': 1, '50 1': 1, '100 1': 1, '0 1': 1}
* 催化剂：{'Pd/C': 7, 'palladium on carbon': 5, 'palladium': 4, 'palladium-on-charcoal': 3, 'palladium on charcoal': 3, 'Pd(OH)2/C': 2, 'Pd(OH)2 on carbon': 2, 'catalyst': 1, 'palladium-charcoal': 1, 'palladium on activated carbon': 1, 'palladium hydroxide': 1, 'Palladium': 1, 'Pd-C': 1, 'palladium hydroxide-on-carbon': 1, 'palladium-on-carbon': 1, 'palladium carbon': 1, "Pearlman's catalyst": 1}
* 溶剂：{'methanol': 18, 'water': 7, 'ethanol': 5, 'MeOH': 4, 'acetonitrile': 3, '1,2-dichloroethane': 3, 'ACN water': 3, 'trifluoroacetic acid': 2, 'EtOH': 2, 'toluene': 2, 'CH2Cl2': 2, 'hydrogen': 2, 'ether': 1, 'hydrobromic acid': 1, 'methylene chloride': 1, 'AcOH': 1, 'acetic acid': 1, 'sulfuric acid': 1, 'water methanol': 1, 'triethylamine methanol': 1}
* 示例：[{'rid': 'ord-13fff069e6674f938ae4987e19fdf4d8', 'temp': '', 'catalysts': ['Pd/C', 'catalyst'], 'solvents': ['methanol'], 'reagents': []}]

### support 2376 · `C-[O;H0;D2;+0:1]-[C;H0;D3;+0:2](=[O;H0;D1;+0:3])-[c:4]>>[O;H0;D1;+0:1]=[C;H0;D3;+0:2](-[OH;D1;+0:3])-[c:4]`

* fired 1672 / match 298；温度 79 / 催化剂 5 / 溶剂 260 / 试剂 0
* 温度：{'50 1': 14, '80 1': 11, '60 1': 8, '40 1': 4, '120 1': 4, '100 1': 4, '45 1': 4, '90 1': 3, '70 1': 3, '65 1': 3, '0 1': 3, '75 1': 2, '35 1': 2, '55 1': 2, '23 1': 2, '25 1': 1, '43 1': 1, '20 1': 1, '150 1': 1, '68 1': 1}
* 催化剂：{'Pd(PPh3)4': 2, 'palladium carbon': 1, 'palladium': 1, 'palladium on charcoal': 1}
* 溶剂：{'water': 62, 'methanol': 54, 'THF': 42, 'ethanol': 41, 'tetrahydrofuran': 31, 'MeOH': 23, 'H2O': 9, 'EtOH': 9, 'hydrochloric acid': 7, 'acetic acid': 6, 'EtOAc': 5, 'dioxane': 5, 'dichloromethane': 5, 'THF H2O': 4, 'THF MeOH': 4, 'NaOH': 4, 'N,N-dimethylformamide': 3, 'sodium hydroxide': 3, 'HCl': 3, 'THF ethanol': 3}
* 示例：[{'rid': 'ord-4f8eca8686f04fab850d92ff0dd05c7a', 'temp': '75 1', 'catalysts': [], 'solvents': ['THF'], 'reagents': []}]

### support 2294 · `O=[C;H0;D3;+0:1](-[OH;D1;+0:2])-[c:3].[C:4]-[NH;D2;+0:5]-[C:6]>>[C:4]-[N;H0;D3;+0:5](-[C;H0;D3;+0:1](=[O;H0;D1;+0:2])-[c:3])-[C:6]`

* fired 232 / match 122；温度 5 / 催化剂 1 / 溶剂 58 / 试剂 0
* 温度：{'0 1': 2, '22 1': 1, '20 1': 1, '80 1': 1}
* 催化剂：{'DMAP': 1}
* 溶剂：{'DMF': 28, 'water': 9, 'dichloromethane': 6, 'CH2Cl2': 5, 'EtOAc': 5, 'Water': 4, 'DMSO': 3, 'DCM': 3, 'DMF dichloromethane': 2, 'methylene chloride': 2, 'dimethylformamide': 2, 'THF': 2, 'NMP': 2, 'CH3CO2Et': 1, 'ethyl acetate': 1, 'ethanol': 1, '2-methyltetrahydrofuran': 1, 'N,N-dimethylacetamide': 1, 'CH2Cl2 MeOH': 1, 'DCE': 1}
* 示例：[{'rid': 'ord-ec04af704dab4af0a800e52e05e90ec9', 'temp': '', 'catalysts': [], 'solvents': [], 'reagents': []}]

### support 2281 · `[O-]-[N+;H0;D3:1](=[O;D1;H0:2])-[OH;D1;+0:3].[c:4]:[cH;D2;+0:5]:[c:6]>>[O-;H0;D1:3]-[N+;H0;D3:1](=[O;D1;H0:2])-[c;H0;D3;+0:5](:[c:4]):[c:6]`

* fired 90 / match 72；温度 29 / 催化剂 1 / 溶剂 57 / 试剂 0
* 温度：{'0 1': 14, '5 1': 3, '90 1': 1, '100 1': 1, '-20 1': 1, '-3 1': 1, '-40 1': 1, '23 1': 1, '40 1': 1, '3 1': 1, '60 1': 1, '-15 1': 1, '50 1': 1, '-5 1': 1}
* 催化剂：{'tetrabutylammonium bromide': 1}
* 溶剂：{'acetic acid': 12, 'water': 9, 'sulfuric acid': 9, 'H2SO4': 6, 'ice water': 3, 'H2O': 3, 'acetic anhydride': 3, 'ice': 2, 'hexane': 1, 'acetonitrile': 1, 'hexanes': 1, '1,2-dichloroethane': 1, 'CH2Cl2': 1, 'DCE': 1, 'Et2O': 1, 'heptane': 1, 'ethyl acetate': 1, 'sulphuric acid': 1, 'nitromethane': 1, 'dichloroethane': 1}
* 示例：[{'rid': 'ord-617bfdd769eb46abb48d202834543d87', 'temp': '90 1', 'catalysts': [], 'solvents': ['water'], 'reagents': []}]

