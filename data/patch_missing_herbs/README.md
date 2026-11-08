# 补库补丁（药典缺 %d 味）

> **仅库主维护者使用。** 软件不会读取或应用本补丁；终端用户没有数据库写入入口。
> 只有库主在明确确认并备份后，才由维护者执行下面的 SQL。

> 由 `tools\build_missing_herbs_patch.py` 生成；**没有改动你的库**，只是一个文件包。

## 里面有什么

* `missing_herbs.json` —— 逐条明细：药典条目名、类别（炮制品/其它）、拉丁学名、
  对应物种（COCONUT）、药用部位、功能主治、出处（药典 2025 一部）、以及缺哪些字段；
* `patch_tcmdb.sql` —— INSERT 语句；`herb_id` 用 `PATCH` 前缀，**不会和爬虫的编号冲突**；
* `rollback_tcmdb.sql` —— 对应的 DELETE，后悔药。

## 库主维护流程（不是终端用户流程）

```powershell
# 1) 先备份（关掉爬虫/VS Code 里的写入进程再做）
Copy-Item D:\TCMAI\tcm.db D:\TCMAI\tcm.db.bak-20261016
# 2) 应用补丁
sqlite3 D:\TCMAI\tcm.db ".read data\patch_missing_herbs\patch_tcmdb.sql"
# 3) 核对（期望 %d）
sqlite3 D:\TCMAI\tcm.db "SELECT COUNT(*) FROM herbs WHERE herb_id LIKE 'PATCH%%';"
```

## 这个补丁**不做什么**

* 不造成分数据：这些药材的成分仍由软件用「药典正文拉丁学名 → COCONUT 物种」兜底；
* 不改任何既有行：只插入 52 行新行；
* 不替你做决定：要不要导入、导入哪几条（比如动物药 `哈蟆油` 你可以只导其中一部分）由你定。

## 明细

| # | 药典条目 | 类别 | 基原 | 拉丁学名 | 物种(COCONUT) | 缺 |
|---|---|---|---|---|---|---|
| 1 | 亚乎奴(锡生藤) | 其它 | — | — | — | latin、species、use_part、function |
| 2 | 体外培育牛黄 | 其它 | — | — | — | latin、species、use_part |
| 3 | 冰片(合成龙脑) | 其它 | — | — | — | latin、species、use_part、function |
| 4 | 制何首乌 | 炮制品 | 何首乌 | — | — | latin、species、use_part |
| 5 | 制天南星 | 炮制品 | 天南星 | — | — | latin、species、use_part |
| 6 | 南板蓝根 | 其它 | — | Baphicacanthus cusia | baphicacanthus cusia | — |
| 7 | 哈蟆油 | 其它 | — | Rana dybowskii | — | species、use_part |
| 8 | 土鳖虫(䗪虫) | 其它 | — | — | — | latin、species、use_part、function |
| 9 | 大皂角 | 其它 | — | Gleditsia sinensis | gleditsia sinensis | — |
| 10 | 大蓟炭 | 炮制品 | 大蓟 | — | — | latin、species、use_part |
| 11 | 天然冰片(右旋龙脑) | 其它 | — | — | — | latin、species、use_part、function |
| 12 | 姜半夏 | 炮制品 | 半夏 | — | — | latin、species、use_part |
| 13 | 小驳骨 | 其它 | — | Gendarussa vulgaris | — | species |
| 14 | 山银花 | 其它 | — | Lonicera macranthoides | lonicera macranthoides、lonicera hypoglauca、lonicera confusa、lonicera fulvotomentosa | — |
| 15 | 山香圆叶 | 其它 | — | Turpinia arguta | turpinia arguta | — |
| 16 | 广东紫珠 | 其它 | — | Callicarpa kwangtungensis | callicarpa kwangtungensis | — |
| 17 | 广金钱草 | 其它 | — | Desmodium styracifolium | desmodium styracifolium | — |
| 18 | 延胡索(元胡) | 其它 | — | — | — | latin、species、use_part、function |
| 19 | 暴马子皮 | 其它 | — | Syringa reticulata | syringa reticulata | — |
| 20 | 木芙蓉叶 | 其它 | — | Hibiscus mutabilis | hibiscus mutabilis | — |
| 21 | 杠板归 | 其它 | — | Polygonum perfoliatum | polygonum perfoliatum | — |
| 22 | 榼藤子 | 其它 | — | Entada phaseoloides | entada phaseoloides | — |
| 23 | 油松节 | 其它 | — | Pinus tabuliformis | pinus tabuliformis、pinus massoniana | use_part |
| 24 | 清半夏 | 炮制品 | 半夏 | — | — | latin、species、use_part |
| 25 | 滇鸡血藤 | 其它 | — | Kadsura interior | kadsura interior | — |
| 26 | 灯盏细辛(灯盏花) | 其它 | — | — | — | latin、species、use_part、function |
| 27 | 炒瓜蒌子 | 炮制品 | 瓜蒌子 | — | — | latin、species、use_part |
| 28 | 猪胆粉 | 其它 | — | — | — | latin、species、use_part |
| 29 | 瓜子金 | 其它 | — | Polygala japonica | polygala japonica | — |
| 30 | 皂矾(绿矾) | 其它 | — | — | — | latin、species、use_part、function |
| 31 | 紫珠叶 | 其它 | — | Callicarpa formosana | callicarpa formosana | — |
| 32 | 紫萁贯众 | 其它 | — | Osmunda japonica | osmunda japonica | — |
| 33 | 绵马贯众炭 | 炮制品 | 绵马贯众 | — | — | latin、species、use_part |
| 34 | 翼首草 | 其它 | — | Pterocephalus hookeri | pterocephalus hookeri | — |
| 35 | 臭灵丹草 | 其它 | — | Laggera pterodonta | laggera pterodonta | — |
| 36 | 艾片(左旋龙脑) | 其它 | — | — | — | latin、species、use_part、function |
| 37 | 荆芥炭 | 炮制品 | 荆芥 | — | — | latin、species、use_part |
| 38 | 荆芥穗炭 | 炮制品 | 荆芥穗 | — | — | latin、species、use_part |
| 39 | 蓍草 | 其它 | — | Achillea alpina | achillea alpina | — |
| 40 | 蓝布正 | 其它 | — | Geum aleppicum | geum aleppicum、geum japonicum | — |
| 41 | 藏菖蒲 | 其它 | — | Acorus calamus | acorus calamus | — |
| 42 | 裸花紫珠 | 其它 | — | Callicarpa nudiflora | callicarpa nudiflora | — |
| 43 | 西瓜霜 | 其它 | — | Citrullus lanatus | citrullus lanatus | use_part |
| 44 | 西青果 | 其它 | — | Terminalia chebula | terminalia chebula | use_part |
| 45 | 野马追 | 其它 | — | Eupatorium lindleyanum | eupatorium lindleyanum | — |
| 46 | 金果榄 | 其它 | — | Tinospora sagittata | tinospora sagittata、tinospora capillipes | — |
| 47 | 金龙胆草 | 其它 | — | Conyza blinii | conyza blinii | — |
| 48 | 飞扬草 | 其它 | — | Euphorbia hirta | euphorbia hirta | — |
| 49 | 黄藤 | 其它 | — | Fibraurea recisa | fibraurea recisa | — |
| 50 | 黑种草子 | 其它 | — | Nigella glandulifera | nigella glandulifera | — |
| 51 | 龟甲胶 | 其它 | — | — | — | latin、species、use_part |
| 52 | 􀅰 | 其它 | — | — | — | latin、species、use_part、function |
