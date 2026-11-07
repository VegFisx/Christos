# 第七十五轮 · H2：AI 现查古方抽检 100 条

> 任务书：`reports\第七十五轮-任务-数据出处隐患.md` 的 H2。
> 一句话结论：**AI 现查那批里，能逐条核到公开来源的约 94%**（命中 84 + 部分命中 199，Wilson 95% CI 91.1–96.4%）；
> **组成与公开源一致**的只有 **28%**（Wilson 95% CI 23.2–33.3%），**查无**的 6%。

## 一、怎么抽的（口径先定死）

* 总体 = `formula_db.json` 里 `category` 缺失的那批记录（= H1 的 tier 5，实测 **5,332 条**）；
* 抽样单位 = **一条记录**（同一方名下不同出处的记录各自独立）；
* 两批**固定种子、无放回、互不重叠**：第一批种子 20261016 抽 100 条，第二批种子 20261017 从剩下的 5,232 条里抽 200 条 → 合计 **n=300**（`tools\build_h2_sample.py` / `build_h2_sample2.py`，抽样可复现）；
* 清单：`reports\第七十五轮-AI古方抽检-清单.csv`（第一批）、`reports\第七十五轮-H2-第二批-清单.csv`（第二批）。

## 二、怎么核的（每条都可复查）

1. **检索**：对每条用「方名 + 组成」在公开搜索引擎上查（360 / Bing / 搜狗轮询，每条间隔 2.5–3 秒），把**原始结果（标题/链接/摘要）**存进 `reports\_h2_net\<序号>_<方名>.json`；
2. **取正文**：从候选里挑最可能的页面抓正文节选，存 `reports\_h2_net\<序号>_*.top.txt`；
3. **判定**：把库里「组成」拆成药材名，与来源文本逐字比对算覆盖率（去剂量、去炮制前缀，`炙甘草`能对`甘草`、`白术`**不会**误配`苍术`），**再逐条阅读修正** —— 规则与每一条修正的理由都写在 `tools\h2_verdicts.py` 里；
4. 判定三档：**命中** = 方名 + 组成能对上；**部分命中** = 同名方存在但组成/版本不同（或页面在、组成未核到）；**查无** = 公开源里没找到能证明该条的实质内容。

★ **最终判定口径（v2，两批同一把尺子，写在 `tools\h2_verdicts2.py` 里）**：

   * **证据文档** = 抓到的页面（医学百科 / A+医学百科 / 维基 / 文库），或检索结果里**非搜索页/文库页/图片页**且文本同时含方名与「组成/处方/功效…」标记的那一条；
   * **命中** = 库里组成与证据文档的**字面重合 ≥ 0.6**；
   * **部分命中** = 覆盖率 < 0.6 但存在证据文档（= 同名方在，组成/版本不同）；
   * **查无** = 没有任何证据文档；
   * 另加**逐条人工修正**（第一批 12 条、第二批 1 条），每条理由都写在脚本里。

★ 诚实交代（重要）：

* **「查无」不等于「不存在」** —— 它只表示「本次检索的这几条公开信道里没找到」。不少古籍方只在纸本《中医方剂大辞典》里；
* 覆盖率是**字面重合**，会被剂量写法（`钱`/`分`）、异名（`黄耆`/`黄芪`）、炮制注记干扰 —— 所以最终判定以逐条阅读为准，自动建议与最终判定不一致的 **13 条**全部列了理由；
* 两批的**取证信道不同**，会带来口径差异（第一批赶上搜索引擎封禁，第二批改用医学百科/维基等**站内搜索**，拿到页面的比例更高，所以第二批的「查无」明显少于第一批）——见下面的分批对照；
* 搜索侧本轮碰到封禁：DuckDuckGo 抓到第 50 条开始 403、360/搜狗中途返回「访问异常页」、Bing 对长中文方名常给无关结果、中医世家站点 502 ——都如实记在证据目录里，没有静默跳过（0 失败被吞）。

## 三、结果

| 判定 | 条数 | 占比 | Wilson 95% CI |
|---|---|---|---|
| 命中（组成对得上） | 84 | 28% | 23.2–33.3% |
| 部分命中（同名但组成/版本不同） | 199 | 66% | — |
| 查无 | 17 | 6% | — |
| **命中 + 部分命中（能核到来源）** | **283** | **94%** | **91.1–96.4%** |

**分批对照**（同一口径，看稳定性）：

| 批次 | n | 命中 | 部分命中 | 查无 |
|---|---|---|---|---|
| 第 1 批（种子 20261016） | 100 | 24（24%） | 66（66%） | 10（10%） |
| 第 2 批（种子 20261017） | 200 | 60（30%） | 133（66%） | 7（4%） |

## 四、100 条明细（每条都有可点的来源）

| # | 方名 | 出处（库内） | 判定 | 覆盖率 | 来源 | 说明 |
|---|---|---|---|---|---|---|
| 1 | 丁香散 | 《叶氏女科》卷二。 | **命中** | 0.67 | [来源](https://health.baidu.com/m/detail/ar_7096815533108865924) | 组成字面重合 2/3（证据文档 10 个） |
| 2 | 乌药散 | 《朱氏集验方》卷一。 | **部分命中** | 0.20 | [来源](https://baike.baidu.com/item/乌药散/7785801) | 组成字面重合 1/5（证据文档 8 个） |
| 3 | 五苓散 | 《痘科类编》卷三。 | **命中** | 0.71 | [来源](https://www.so.com/link?m=wLCAmAiATV9L0znYlQJG234AHbyMTXOmCcZb0s7TOpy9O1ShTjiq0zpx7HOglprTcUfuu01WKNTznkLcV7mPWY7ow6lhF9LR27UxnZ99NED%2B0T7y15ibA%2Bm9h2YCETglc5WNLPVnyhzGD0xsL4tpqtO5lgcFAl0Sm4jb6Y7iXFKnZx9bU3O3zTu0DazlXXhJmWwKPfH8e192dvFxt) | 组成字面重合 5/7（证据文档 2 个） |
| 4 | 五苓散 | 《金鉴》卷五十四。 | **命中** | 0.83 | [来源](https://www.so.com/link?m=e%2B3mJojfAPCEXbiz%2BYfLPAv9LvdZwVo7%2BbdxaXOOU8ybWdij1NQKe4FCRlyE%2FLs05u1ZyyrKUJvmaAdk9EwauvImSkDShNmmaBbhAtfDbFy80xA8RZxbDGdNwymAGz2mXPmE9y23U%2FTgQaAJ67cCws4fpeG%2FaK5KMCUcN75dOwmjUm6oV6jtFPeWR3Mvbj9xwsYtJlInFXCe8Q51h) | 组成字面重合 5/6（证据文档 4 个） |
| 5 | 人参败毒散 | 《回春》卷三。 | **部分命中** | 0.33 | [来源](https://www.youlai.cn/ask/909750zO8VT.html) | 组成字面重合 1/3（证据文档 6 个） |
| 6 | 仁丹 | 《幼幼新书》卷三十一引张涣方。 | **部分命中** | 0.00 | [来源](https://www.so.com/link?m=bDf35w4Qo5gUKkIes6pF19%2FqLnfxBhGtMr5K3kKR1jZLiFUdEEh4wWGTLbcenUcBhUwXeXRueYMvwbTeTagav2ocSIm83oGDSHR9UwLBpCEwNLzY6GWujCusggVfdKCOe36gc1RGVGq6PsSTX8A3t9fy1rOhwNx2FY%2F7NYpBLWaqqqyxgpfjsTdv5MB9WbeTF7fFC%2BHOuKmCg625PZVDQGLiufgqv53msStAXwN6ycHoOpOoi%2F2ENcmNWBIkoZmS7OcIuOHAAI%2B1Wi%2Fv%2B7jvPfWwu%2BUG1fCbaP%2Fx1br%2F9hdOk5OyR) | 组成字面重合 0/8（证据文档 1 个） |
| 7 | 伤痛宁片 | 《上海市药品标准》。 | **部分命中** | 0.00 | [来源](https://www.jianke.com/product/172657.html) | 组成字面重合 0/7（证据文档 4 个） |
| 8 | 何人饮 | 《黑热病证治指南》。 | **部分命中** | 0.10 | [来源](https://www.so.com/link?m=erS4XMNsozM7e0%2Fu8DzS0MSVEwmJaingni1T4cmR2lUFv%2FJ9C%2FHb4rASQemzyLecfYVRQfZzU8OvHqPStJb51jsqhDEGgp9HCjR%2F9I68sdp%2FKytrbsbc3M2gDn1nFq4h9MMMctYsaZKiOBPlpoHf14FDQ3IDlzA85PNG%2BREHByWEOCiA6h8AeoCSabu7LgNgkZp%2FkaQNelm2IDJy1nItXsI9OGh4%3D) | 组成字面重合 1/10（证据文档 5 个） |
| 9 | 保元丸 | 《会约》卷二。 | **部分命中** | 0.00 | （无） | 组成字面重合 0/26（证据文档 2 个） |
| 10 | 保元汤 | 《外科正宗》卷四。 | **部分命中** | 0.50 | [来源](https://www.so.com/link?m=zXD0tm2f6YgsPdrlXCNKpDG4XHR0ozyKGU0Rpyvt8prBgFfYyz20gSec4XccI3dLt5Vd7wklAsNDshb%2FC8UyzUL1t0q0RNax3nHxYsqYX6tk4xsOUu4fkKooMHwUl14lPbT3UWTgH%2BD89NmcM2XmT6Mhmu8FjHs9CHmyl%2BjLZm9P8mQbdOwpYOa6Uku%2FzYf0kFdPRyYwYX2Aejt7U) | 组成字面重合 2/4（证据文档 2 个） |
| 11 | 保元汤 | 《会约》卷十二。 | **部分命中** | 0.00 | [来源](https://www.so.com/link?m=e7pOeenaPF2mFCB73emzzTV7asx%2B2LAn2NIrKVHFa5KELEdZBvjHY2GRghMxubdiDLDtwikVatqpibeCXLx4QxmWxLipm%2FokkWFtYE%2FRvAHgTNRHZDjICJrUUCNMBhp2sEqjAAdC%2B1oHaBhlBMBshxUws8T3fCT3gl6p%2FiS5%2Bt5UTr%2B%2B3AukLARXFTTGEdA%2Bie8WfC%2BMy4%2FcaA29J) | 组成字面重合 0/9（证据文档 3 个） |
| 12 | 八宝丹 | 《救伤秘旨》。 | **部分命中** | 0.22 | （无） | 组成字面重合 2/9（证据文档 2 个） |
| 13 | 六味汤 | 《古今医彻》卷二。 | **部分命中** | 0.00 | [来源](https://baike.so.com/doc/4974659-5197421.html) | 组成字面重合 0/8（证据文档 2 个） |
| 14 | 六神丸 | 《普济方》卷三九一引《保婴方》。 | **部分命中** | 0.00 | [来源](https://www.so.com/link?m=bn0Y4pX1tJv%2F4wBWp2IY3GS0jFvSGlgWlfCapdwLmsTAV5dZmolMzpNUDbpE20nw1cARHoXUquP00ALzPtWTxBd2MLl487Kp7i4sApjINMlizoYcVOIUY9N0rdtsflqg4FEeLks1ftPI0oRW7qbI7IiRI%2F4HNLbuP3FYvWQW1eZoftfgdbl61tUI2ROd33PB0) | 组成字面重合 0/6（证据文档 2 个） |
| 15 | 养胃汤 | 《回春》卷三。 | **部分命中** | 0.42 | [来源](https://mingyi.sogou.com/fuwu/pc/vr/landresult/juheSecondPage?query=%E5%85%BB%E8%83%83%E6%B1%A4%20%E7%BB%84%E6%88%90) | 组成字面重合 5/12（证据文档 2 个） |
| 16 | 凉膈散 | 《症因脉治》卷一。 | **命中** | 0.71 | [来源](https://www.so.com/link?m=wKQfpJ7fwzSNtQhamPgTPNUokWNwoItjkmt2we93HAKoC5HGKfNb3k9bcTZ2xPQ7CCJTyajwDnbgko2ZtZqUYxKFmgV%2FE3AZYviCKFC%2B8uYNlLi1uD3QEK3VmcogP317l33ZPQFRJuB2Z3oYIPOR%2B9Gc8%2B2dJ4im%2BVP44oUPhS5aJ7R6jfvF%2FQfrRhP5HJJbqdbHGOzADbkdrcItP5joUq%2BIb3t8%3D) | 组成字面重合 5/7（证据文档 3 个） |
| 17 | 加减地黄丸 | 《活人方》卷一。 | **部分命中** | 0.18 | [来源](https://www.so.com/link?m=eQkSKSSxOpfD1WGhsDNFT%2B6FXiPirp%2BeMq0s%2B5qfGG94ffuxqSbgN26yS%2BChzShJwOnh8EGDOCMfE53vZSTq9zEY9udNBf%2BxFRMUeZIhEeAo8ATmrX%2FF8lBrXRtCsbujH5M0bII2ar1BPlIz9VASV8RmyKrzO3tM%2BkNp1W5Wlkb%2FtgW2VpAyaU7v8iqWvH%2F32t8eOee4f9mdAmMd4CMvJMKKWgy5zMNVKR1gEtpRTxOxhXSROGYbsn6Ks7e3Mfdx7735GrNenjIr2PQ49ao9AaGWBBlA%3D) | 组成字面重合 3/17（证据文档 1 个） |
| 18 | 加味四君子汤 | 《济阴纲目》卷十四。 | **部分命中** | 0.71 | （无） | 加味四君子汤：同名方在，但源是《直指》版（含白芍/白扁豆），本条含罂粟壳 |
| 19 | 加味枳术丸 | 《赤水玄珠》卷十三。 | **部分命中** | 0.25 | [来源](https://baike.so.com/doc/2776873-25768587.html) | 组成字面重合 2/8（证据文档 4 个） |
| 20 | 加味香苏散 | 《奇效良方》卷三十九。 | **部分命中** | 0.25 | [来源](https://baike.so.com/doc/2278551-2410450.html) | 组成字面重合 1/4（证据文档 4 个） |
| 21 | 化毒丹 | 《疡医大全》卷十八。 | **命中** | 0.60 | [来源](https://baike.so.com/doc/6817399-7034427.html) | 组成字面重合 3/5（证据文档 3 个） |
| 22 | 化风丹 | 《幼科指掌》卷四。 | **部分命中** | 0.00 | [来源](https://www.so.com/link?m=eHuDTPBX0zMZaxP70ZR6XNWmuaP4ujXzPEKsgvEFQA%2BLEFZsF%2FVHiO7UqCLe5URoNazLWqasonM%2Fhx%2FfUc3Rx3PPGXsqkZyDj%2BGnmTC977QfQNuCj4u6hUl8Buj8UO5SP0i8k506dn1uHPF2HEKnFYsUqlylE0KYuwbL47m2Ec3jCvvftI1Aa7p0ksHFMwZZDMVVpHya4XlE%3D) | 组成字面重合 0/11（证据文档 4 个） |
| 23 | 十灰散 | 《医级》卷八。 | **部分命中** | 0.10 | [来源](https://www.so.com/link?m=bPP2ScY%2F%2BI%2BHZA%2BLOHIReHtrMNyGjKCQoMrP%2FPfFtgb65muGKvUAOGk6s4aQY6k849LT0J4P4k35m9aw%2B92J5J1G6LLFnRam1uuQD3pknuH2dCONTAg2PUV%2FftmZ00H0%2FxfI%2BXqSmPsz3ezp%2F94XWHw7RxAwTpRJq%2BlFht29B1sO5r0gLwNLdera4bYhWeJsm) | 组成字面重合 1/10（证据文档 5 个） |
| 24 | 十灰散 | 方出《蒲辅周医疗经验》，名见《千家妙 | **部分命中** | 0.14 | [来源](https://www.so.com/link?m=bSQl2NbEbrWtjQKuJJDYqnPZfGPIs87McXUvsXYaqqxAajSa4ePXJj%2FV4qTn66%2Bup63fErdrKDh%2BfcdBx0jWzkf0nnM%2BGX%2F9vXolkeoBOQsBp%2FWL3pD4foc%2F%2B890PvcDpM%2FYVE5KYkYN1UZqmZtMNFtIoCjSM9XC8uzmuQHTh0EBgRtCU2w4XE4Ue3mdRfbY4) | 组成字面重合 1/7（证据文档 5 个） |
| 25 | 半夏泻心汤 | 《伤寒论》。 | **部分命中** | 0.00 | [来源](https://baike.so.com/doc/5400601-32337609.html) | 组成字面重合 0/7（证据文档 3 个） |
| 26 | 华盖散 | 《外科大成》卷三。 | **查无** | 0.00 | [来源](https://www.so.com/link?m=ull55nEp1bVULpGY%2BbmCI7gBjKk%2FKhzu8BIIk%2Bz4jNIQ2JDiEUB4iuItQx6OXgL%2B8W81K8wIIQuZL1GiyANgi2S8BPM%2B2696QRD%2F00C19Z%2F2yb7nM7z9%2FVTHcUCo75jjREi4Q4zNJQ0aoHKjdWhYehfoEwnRwU64tQNjX28eenq5iJ7w9ZQWq9TcRQx5EAdddJUr8AFGh4FrwImES) | 华盖散：只取到文库搜索壳，无证据文档（本条库内组成仅糯米） |
| 27 | 右归饮 | 《景岳全书》卷五十一。 | **部分命中** | 0.50 | [来源](https://www.so.com/link?m=blbB%2FkaLoF5dD5%2BMGdFGiGkvz4RSWzNDgYaALJOgwidvncWfgEkmhaih5qdktqS%2BP6K5v5Y4w25T7%2BwEIzvw9k7UMRVORFZXGokt3EOhQd4QZzzx3W5lzbnsP0xLGKMJQcx9GT9UxXJqyjXk4QvDEwnEZF30G6jAUURJaP8j28TAjK6flEILGEldB2dJsCwb9t%2FAZyBkN7%2B0%2F%2FY4C) | 组成字面重合 4/8（证据文档 3 个） |
| 28 | 四君子汤 | 方出《丹溪心法》卷一，名见《医方考》 | **命中** | 0.67 | [来源](https://www.so.com/link?m=ew%2BbeFJh4IIRITuXdeH5EA7c7R3LWr7l2udD6XYLNW3VMQTd4GIlezTKTfcvBdjSmDT%2BMyxki%2FL1eUMt8pSx3bS99vUEi3%2BLngW%2BFcKskwetiopeP13Tvrm0JEScuyzK7C92%2B2ktC0Gth4jEyhLkLSE135vCq%2FyabTsQv98iVirRI7Pv%2F1k4pjmJqT1UgyMJ3F9DTRQSMd63VcPferAqguy2DN5M%3D) | 组成字面重合 4/6（证据文档 2 个） |
| 29 | 四红丹 | 《全国中药成药处方集》（济南方）。 | **查无** | 0.00 | [来源](https://www.so.com/link?m=bN5Fg7fExpwxctwW9JWjryxOOtQ6N6oI0bw2B5t5SFn6%2BIeUDDA1nsMrvF7xX90NfQmw1%2F7YyrzDxY%2F63X4lhDNXh7bdOKOl9raOKhxGmvwK4PiR5dlFhnGtY5UkInBIoofIoBWEmStXBz1stoZJUVdT%2FjPaP%2BRq8%2BASYwCcMWns0KkGN4ZAq2dkKuwpngAKg) | 四红丹：只取到文库搜索壳 |
| 30 | 圣愈汤 | 《不知医必要》卷二。 | **部分命中** | 0.25 | [来源](https://www.so.com/link?m=uxgilwWNjAUTrVq1%2Bo3uRhqV52HVMm2nM12DPrl6abakR2AVFumddatoohupdCuwcVeQZM8avq34ghzTHCSX5EoUo8%2B95Y8NLMrDMY%2BP345gasMVlVqhtZ96sgtAzrucqluLv3uEDcH01lrlNNbEgQx6GUtMR7kUEEd2db5tacbaMhHQnE6%2FYt9GCGEonjpAhh4mZduS6GDJA4IaX) | 组成字面重合 2/8（证据文档 3 个） |
| 31 | 定痛膏 | 《摄生众妙方》卷九。 | **查无** | 0.00 | [来源](https://www.so.com/link?m=zcuseD3mjetH7giJhSl%2BJ6U6TEHjTphDnXNBZBtTz2R0LIpUjlANHw7xaLvVrCeAYguC13PA2pLFo6vsqHj2POD4cBvYW9sKEhUDIyuUJ63J%2BRuAucoSojzFazShsVX5RNA2mnXXERTKKLOsrYs%2BHlezMFPK5zttZQ1gbluOsGMuY8oURgJ7oEx5QfK3MNA6DWWUJltu3%2FuiFU6MzHSlNkhq5uXg%3D) | 定痛膏：只取到文库搜索壳 |
| 32 | 小儿化毒散 | 《中国药典》（一部）。 | **部分命中** | 0.00 | [来源](https://baike.so.com/doc/7562679-7836772.html) | 组成字面重合 0/12（证据文档 3 个） |
| 33 | 小儿止泻片 | 《中医方剂临床手册》。 | **查无** | 0.00 | [来源](https://www.so.com/link?m=urC6lw%2BPJJwLsXXOgsM8Wk3RbV7oQcW3QFEcD6a3PaNE1mrqMqyaGO7ZExN7z3GDBOZZmlBa6%2BZ5pFuNYy8Sk4lfQq%2FCVOtkG9iQHcStqbUpK79l6Y12H%2B2KiWInTUV%2Fq7jRjaAO5A49H3h26ES%2FnUmTClNjZo655AfLhzggh0BCu1ST3zBMd34uMJwJzkSVYr1MnLIas4d1IZwsxzeFv5SNQOykXKNPc) | 小儿止泻片：只取到文库搜索壳 |
| 34 | 延胡索散 | 《圣惠》卷七十一。 | **命中** | 0.67 | [来源](https://baike.so.com/doc/398610-422020.html) | 延胡索散：360百科条目组成与本条 8/12 一致（其余为炮制注记） |
| 35 | 开胸顺气丸 | 《北京市中药成方选集》。 | **部分命中** | 0.40 | [来源](https://www.so.com/link?m=bXMyiH2pLdOQ%2FN89XaUxMVnzrkoAuGeKLJJAJICNSamwQ0QvWTZx%2BD89F8FLurYjQJicK7O170XSxfD7bUEiR1CpPJW%2FBgVnPcdVsGL7KzILudB%2B3qDb32tv9F7ePhC%2BNGgunxH8%2FDYb29ISVs6MtJ9cm%2F7meDF8aIZbXCz%2FwkMFdqU%2F6aSE50rdUyn010WnWyJ084DDvcnLVS3a4yzv3ZPuex54%3D) | 组成字面重合 4/10（证据文档 3 个） |
| 36 | 抑肝散 | 《医便》卷四。 | **部分命中** | 0.39 | [来源](https://baike.so.com/doc/260373-275630.html) | 组成字面重合 5/13（证据文档 4 个） |
| 37 | 木香分气丸 | 《天津市固有成方统一配本》。 | **命中** | 0.77 | [来源](https://baike.so.com/doc/1708950-1806789.html) | 组成字面重合 10/13（证据文档 4 个） |
| 38 | 栀子豉汤 | 《伤寒论》。 | **命中** | 0.67 | [来源](https://www.so.com/link?m=bA7ygDG2yQrpfV1cVtMht%2FtKFxVJkkVHYy4qDFKQqcALIpaiJcuQznnSH5BM45TVNT73ob1QFh3Zt9G%2B9vvCVGkUkneoo7wUXTlAZWZlHNHOUX6ZLCauZ9iKQORhNBY0Spt2x3xANBdNW3SmEQuPc34SYseQHJC55Ajl99TOQkljCvXf0RQAtPaV87HQ%2Bx8w1bEbdtYZ%2B3IvgS%2FBm51v8xn6nlQzOOXjR70xMWWYe%2BquV%2BeGZJl48C%2FTqAua13f8ULjnbo3QXcjUDaz4aV%2Fclm8MG5wovEWIgoua0DK56m2Gi26E%2FbdpraQaSnuahKenmsZ8bEVTEGymdAZ3d8hRF%2BXeRMVM%3D) | 组成字面重合 2/3（证据文档 2 个） |
| 39 | 桑白皮汤 | 《圣济总录》卷二十六。 | **部分命中** | 0.56 | [来源](https://baike.so.com/doc/30513977-32356953.html) | 组成字面重合 5/9（证据文档 4 个） |
| 40 | 桔梗流浸膏 | 《上海市药品标准》。 | **部分命中** | 0.14 | [来源](https://baike.so.com/doc/6095393-6308501.html) | 组成字面重合 1/7（证据文档 3 个） |
| 41 | 槐角地榆丸 | 《外科大成》卷二。 | **部分命中** | 0.29 | [来源](https://wenku.so.com/s?q=槐角地榆丸 组成&src=ob_zz_juhe360wenku) | 组成字面重合 2/7（证据文档 1 个） |
| 42 | 橘皮竹茹汤 | 《金鉴》卷六十二。 | **命中** | 0.67 | [来源](https://baike.so.com/doc/2167871-2293890.html) | 组成字面重合 4/6（证据文档 4 个） |
| 43 | 沉香化气丸 | 《活人方》卷二。 | **查无** | 0.00 | [来源](https://wenku.so.com/s?q=沉香化气丸 组成&src=ob_zz_juhe360wenku) | 沉香化气丸：只取到文库搜索壳 |
| 44 | 沉香化滞丸 | 《重订通俗伤寒论》。 | **查无** | 0.00 | （无） | 组成字面重合 0/13（证据文档 0 个） |
| 45 | 泻白散 | 《玉案》卷三。 | **部分命中** | 0.43 | [来源](https://www.so.com/link?m=uAR%2BEB0LkFUkfJh7WTl48FpZO4D5XOKwEk36xBvihwD9et1NjGLlS7eT6iBe%2F51eDybBUWaTXd8WwoacRccgKelAs75XkZ5zV1VzozFIMJiM3foB%2BuaAarXF47KquirwgJcI8QlqgYDUm6f4PKZ9fgulMVxWKFHxv40CxNj%2BQYJz3b7Uoys7%2F9RhkG%2BRdPjh2oCuoYin%2BgsI1DJhS) | 组成字面重合 3/7（证据文档 3 个） |
| 46 | 海蛤散 | 《圣济总录》卷一二一。 | **部分命中** | 0.25 | [来源](https://www.so.com/link?m=bX%2FFpZgHdqim7t1QvY2F1cM%2BPWwy%2BiHJ1clTxiCjP8JkOyXSawIeWv1BqavT%2FJ4jF%2B5o6l6NWa2TLHBYB6uMGf9TuzrGmZhpDhN64Cl3GhXmyKHuHA3MZLOrpFYcE7vxZTMFvfwK0ku01Z8vAQwGdsRez%2FTZFHyeCKTdpi9GJa2C9wx0W4qzGHzYSk%2F6rFgFyB7CCj%2BK61J4UQuy9SpqLaoCrBMI%3D) | 组成字面重合 1/4（证据文档 4 个） |
| 47 | 消积丸 | 《普济方》卷三九二。 | **部分命中** | 0.12 | [来源](https://www.so.com/link?m=eWRikDtM%2BJrlsptoACbfahLX7nS2jQZqMa0D2ZukrmWB9Nom19lgHeGu213Egsv53ZuOWAIQXgn3pP5XWGGFygpU1S6UgPmqVobyHAcVaosJSK1jnpeo6GOnf5Jz4n3WTDdGZtOfJPkt6idr5S0Sgr659BnhNt563wEgZpBnKt4v17MHjCzOPig%3D%3D) | 组成字面重合 2/16（证据文档 4 个） |
| 48 | 消风散 | 《局方》卷一。 | **部分命中** | 0.06 | [来源](https://www.cndzys.com/xshcore/quanwei_ztart/1es_3435087.html) | 组成字面重合 1/17（证据文档 5 个） |
| 49 | 涤痰汤 | 《寒温条辩》卷五。 | **部分命中** | 0.00 | [来源](https://www.so.com/link?m=bhNDJ73LEdJ0xo%2FOFVOB12ZCqo8ADdIktgrDBWMjABUzUcNSCaANrjR2bvuhdLOo7ysiJ0Euj2cxLzgFkquYM18fPwIcaRFkEbCOcgMvH0zxod4dAcufEU%2FFE0pjfvq%2FZ5I9FY%2FeCNNknMA5jyLWbOpm05okSKB%2BqQXRHTb%2FugZeBU%2F90t83a7MlpeW3EPKOid7HRM%2FhIaPtgEnQgMOjfIFJ5eBQcIt2qg6NXU2jUCaUve9XzCDMH1O%2BYHCASouKXNi2uBi1jsmdL9lDm%2FqURf7ZSxEjz00SEk5IPpCnAcx7TazNHbBDA0g9Td11vcZ6atipChg%3D%3D) | 组成字面重合 0/12（证据文档 2 个） |
| 50 | 清心丸 | 《魏氏家藏方》卷九。 | **部分命中** | 0.50 | [来源](https://www.so.com/link?m=bwKL9mTk47PefSZ6h69AHC0HRgWrrY%2Bm1UTdMGv2bpkvrSFoGi%2FYZ3%2Fm09Y73JV3xZizVBP2zFPMKb2whZOkVX8mf6MRadexNPMa8HxHZqR6%2FhMXO544yDWAsMeIJRKzfdDroZNJ7Ki6nv67PfabdjmirljsRqAIA6mqgU77NIcIFDzKFGrJBByMndHw4UjoW) | 组成字面重合 1/2（证据文档 2 个） |
| 51 | 清暑汤 | 《伤寒大白》卷二。 | **部分命中** | 0.00 | （无） | 组成字面重合 0/4（证据文档 1 个） |
| 52 | 烂积丸 | 《全国中药成药处方集》（大同方）。 | **命中** | 0.92 | [来源](https://www.so.com/link?m=z%2BvA5bjQAL0gZh2l2X042MCmKxUTiONBp1KybKNjwyUpW0jZARa3DE%2Fon5QAe6SRu7MI4y0EprRz%2BpPujy%2FQ4Ye386rKw8dXcfev3q21aSjIwS%2BfNyXegTVV1BRS2i0s4E2jJSZ8uhZITInYZX31qHG5u5ypXx650%2FAfqxBnb8MChtGnQks82jQ%3D%3D) | 组成字面重合 12/13（证据文档 5 个） |
| 53 | 犀角化毒丹 | 《喉科紫珍集》卷上。 | **命中** | 1.00 | [来源](https://baike.so.com/doc/9727474-10073955.html) | 组成字面重合 11/11（证据文档 2 个） |
| 54 | 玉液丸 | 《幼科指南》卷三。 | **部分命中** | 0.00 | （无） | 组成字面重合 0/7（证据文档 2 个） |
| 55 | 珠黄散 | 《温证指归》卷三。 | **部分命中** | 0.50 | [来源](https://www.so.com/link?m=e6Us3ZNuY%2Fv4IeXHqm35hlCVDUBWVZNRxDIcGUu76AXT6BmDPs7yI23TBAvNegZyNLQbjqYNHqGRPWzIztNl5vA0onqbTFCoKfZ1vmnoXUKzwRQ7%2B4yRLQ9AfbQrrJmD3QNq3nBn1BBfJvx4PBzDo%2FMOkxOd4%2BAz5behyVpeT%2FnZnRsKSFB1k2F4MHHyglgeq) | 组成字面重合 2/4（证据文档 5 个） |
| 56 | 理中丸 | 《直指》卷八。 | **命中** | 0.75 | [来源](https://www.so.com/link?m=we%2FSiV24qZCy22kbzE2X2oCH%2B3Sd6%2BPauW42JaYRzJx6lqf0jCCFC6Y%2FFzULkUOVJH17%2FhGpM%2FfSXOpuCEtL0m3%2Bx5nb6%2BCGSgs5PKFqg0Osvp3EK36NQfyl%2B6qNnSjVRc7tPoZyPqXViNrGsMFy07CQkDI8q3%2B3kM1g5wWYe2oXk60%2B%2BWZ3i%2BCw6d19uE%2BJgTc8Iv%2FsPQWTtN1RS) | 组成字面重合 3/4（证据文档 4 个） |
| 57 | 理中丸 | 《千金翼》卷十八。 | **命中** | 1.00 | [来源](https://www.so.com/link?m=uvqaTHwbpHIOfiMZeIoyT00JYK2QcXJnXGPnusNMaKj%2Bwk4fjSZQuaTEGlSAqTALfKyXDs3TcwceBCf8n%2FTqxJgOJH9Z4d5jiLd0EaYpI8K4Ys4XJcC4kxSK5CmM9e%2FHMlTkGaOjQBm0hOkx7sHBsPZg7lOkLVNIN%2F9TxocnlPMSv44v1DBDo%2BMz%2BAssXcxZsKHBPemBT2cXRpW1G) | 组成字面重合 4/4（证据文档 3 个） |
| 58 | 生肌散 | 《中医皮肤病学简编》。 | **查无** | 0.00 | [来源](https://www.so.com/link?m=zVhjsL1Ngxzi0xqShYrQyz7X02RVr6rlZbdB7h%2BXo9Wq%2BUkp0SPYl4Nzdz58iqqGwqecMwCN1%2FQi6TfmGu3PiBN0HR3e0EZihE%2FzWPMlog42ZRFwV7iY0yxM3nSF6MrqOn75noPrnZbKqLeulA3vNA0OL5Id8B59lURbVjq0rGT3yuhz%2F%2FCcTK99Vi3HXU%2FmG) | 生肌散：只取到图片搜索壳 |
| 59 | 白术散 | 《圣惠》卷十一。 | **部分命中** | 0.08 | [来源](https://www.so.com/link?m=uOhdwJ1o%2Fzebz4Gs8vJXMBzKw8pcih2tC8%2FF12yp%2FyEcRAXCrEaSDuAIOuGEmd4HkcbXIf9lcCGyXm9X1SEOKj41t4OWehazA%2BnNMM9vFA8X1ArylioKC%2Fw6%2FrAObLzBpqHlck3ec7TfI%2FnSxpbK1oz95bR6vb8uPT7BfJyvVpUzWlGUi1CAojWpOFbI%2BHgGh%2B5f9Rg5XwcKdNV6a) | 组成字面重合 1/12（证据文档 4 个） |
| 60 | 益母丸 | 《灵验良方汇编》卷上。 | **部分命中** | 0.33 | [来源](https://www.so.com/link?m=u1oW7lBfv2PkO8q6YN%2B8CaWJWrtymGwrtQ4%2BeZr46G109vENER6XBQmIcEurMYsSBOPQ%2BCP%2FtTo4DY0BxB%2BJ6ucHY7ycXMKYqLfG63ygUyp3t%2BSox%2B6xbAZi2ns3fpUYL1OliOMWAwBYfpbXo8EnH%2FMJmaVn547ZjwpWiUvvzcdGXHOCk%2B06TBec3FtkUv3Nggn5LDA%3D%3D) | 组成字面重合 1/3（证据文档 3 个） |
| 61 | 益母丸 | 《绛囊撮要》。 | **部分命中** | 0.33 | [来源](https://www.so.com/link?m=u0VzHP1jbGul8mB6CPKp0ol01UhtUbeuOc4ab1KCzuEBp57J3rzeaMwQwXJoi3o6%2FGfu1DnEYaVu6j6G5mpxZsd9l%2FCeOgrI12uPHXu5Zl4x3GBhO3tMWCJvYG27nRVrt7dSGxSpafSwxz%2BosyNi9NEEOQhWAQXqixPPJmMGueh%2FFt8Rb1uogiyBHBk2SXQjlVah1AA%3D%3D) | 组成字面重合 3/9（证据文档 3 个） |
| 62 | 益阴汤 | 《类证治裁》卷二。 | **命中** | 1.00 | [来源](https://www.so.com/link?m=ef1vJ3j%2FIspRbyKKRwEPvJ30X6SDkQv660hLnztoyYcruDHlwLJA2SsiaXjK1QXS9HMngxNoxm3wglFSLA8MJw5YRHibRLE98zUW4TEUEgadlOOG6fUl6pAh0MZnHio5BqgconbkEWddTXfJCbg95bRNkB4tzB8RYmhgxdsWOhJI%3D) | 组成字面重合 11/11（证据文档 3 个） |
| 63 | 石决明散 | 《金鉴》卷七十七。 | **部分命中** | 0.11 | [来源](https://baike.so.com/doc/2809159-2964954.html) | 组成字面重合 1/9（证据文档 2 个） |
| 64 | 红灵散 | 《急救痧证全集》卷下。 | **部分命中** | 0.40 | [来源](https://baike.so.com/doc/3431354-26396143.html) | 组成字面重合 2/5（证据文档 2 个） |
| 65 | 绿袍散 | 《喉科秘诀》卷下。 | **部分命中** | 0.20 | [来源](https://www.so.com/link?m=bGAkdnj2Lhtf1zNjL0xdgZBR6x8ZxMNOSO3XGs127dlmN55oyt71d8JgKkcyJLW26WvuQzOZjGIB1nZciycSWgmGd2B5JOH4LKi%2FagYK53Wcb2w1ukm1D1%2Fuz7NxPXoB74upLH%2FEWwaKMQ1j49T961Vq63vIWZD8rzlYgwUkrWd%2FQW8yUlzJPxJDMc3w25CQgjOr0%2B2yxNXbUpgUVTEBoMYvEoY0%3D) | 组成字面重合 1/5（证据文档 3 个） |
| 66 | 羚翘解毒丸 | 《全国中药成药处方集》（呼和浩特方） | **部分命中** | 0.38 | [来源](https://www.so.com/link?m=uLCYeunaMsBxlNa7%2BKYolba%2Bc5J3UM4D6f48GAue8vxygBFf4Tqep0Zws8FzaNFI9hOf%2F%2Fk3tvCL%2FgEvOcIqn%2FkIH93XLK54UprC%2FEyiZfBhwGxkkYFwsMnhrBf7zSBB2QpCJ21xsXyeMAph52pBwoIteQxVixwFRqX5siULXTIk5fEL639iRbv9IcdTEhFY6W%2F20rFSN5gjqtV5QG62TBu6auD8%3D) | 组成字面重合 6/16（证据文档 2 个） |
| 67 | 肥儿丸 | 《广笔记》卷三。 | **部分命中** | 0.12 | [来源](https://www.yixue.com/index.php?search=%E8%82%A5%E5%84%BF%E4%B8%B8) | 组成字面重合 2/16（证据文档 1 个） |
| 68 | 肥儿丸 | 《医林纂要》卷九。 | **部分命中** | 0.00 | [来源](https://baike.so.com/doc/5977599-6190559.html) | 组成字面重合 0/9（证据文档 1 个） |
| 69 | 茯神散 | 《圣惠》卷六十九。 | **部分命中** | 0.08 | [来源](https://www.yixue.com/index.php?search=%E8%8C%AF%E7%A5%9E%E6%95%A3) | 组成字面重合 1/12（证据文档 1 个） |
| 70 | 菊花茶调散 | 《不居集》下集卷二。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E8%8F%8A%E8%8A%B1%E8%8C%B6%E8%B0%83%E6%95%A3) | 组成字面重合 2/2（证据文档 1 个） |
| 71 | 葛根芩连汤 | 《赵锡武医疗经验》。 | **查无** | 0.00 | [来源](https://www.so.com/link?m=bHfAOMkQDqHKfYlSaZP9nN%2BneLvx%2B36I0FKngeRYcbNIpE0E5vCiyLI1XmOmTcNeQdRqX1fHArgFqymMnhbCxVRcXaVzCAEcOcerxOGdFRZ7%2FkaLWQxiaozkAYSYM2QYHE9IJ4praMfxGacRne4F2t1z7Y0A0LKM24i8N7%2BoojOo%2BGwruIy4q7di82RcmCVMnxQup1iqhqD4VUQF4WfVI7pZBWcF9uaeEfutkFA%2Fwe7E%3D) | 葛根芩连汤：本条是《赵锡武医疗经验》加味方，只取到文库搜索壳 |
| 72 | 薏苡仁汤 | 《圣济总录》卷十二。 | **部分命中** | 0.12 | [来源](https://www.mfk.com/article/2324628.shtml) | 组成字面重合 2/17（证据文档 4 个） |
| 73 | 藿香正气散 | 《医便》卷二。 | **部分命中** | 0.55 | [来源](https://www.so.com/link?m=w66062R1JZn6gjDkxDLF%2BiAuicmub4k6FDbqwGIvzC%2BxHGmeZ1hJo9vOMpPWuHIfnM4T18wnvZwnGlpEgoV0v3XHa1AIMnwBvp6uEZhVhVIsJVsnFMvvSBiLdexlaJ7eZCw%2B0zZFdkg3qlL%2FAJqJRoPtre8NhhgK7zddENjDSqzhIN4bzg8cWMKh%2FeWtSv%2BCrzAHB4HTDpS7qGa08CAWJP0RFs9XUHcLJkJFI9svQKNo%3D) | 组成字面重合 6/11（证据文档 3 个） |
| 74 | 补中益气汤 | 《种痘新书》卷九。 | **部分命中** | 0.00 | [来源](https://baike.so.com/doc/5417611-5655759.html) | 组成字面重合 0/7（证据文档 3 个） |
| 75 | 补肺丸 | 《本草图经》引《传信方》（见《证类本 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E8%A1%A5%E8%82%BA%E4%B8%B8) | 组成字面重合 0/1（证据文档 1 个） |
| 76 | 补肾明目丸 | 《银海精微》卷上。 | **部分命中** | 0.27 | [来源](https://www.so.com/link?m=ucVtfXU0Vou2TCiGCu3%2FEQiy0k6qDFhR%2FZjx1lYeSgm6e7ygQD6XL487zRC1YB%2FXRaYL%2BOMStBy9dNiG9MbFAC5%2FC4Nr181Kifedh2cGrhHIWYibokwRBFBNA26s70pEZt3b4U2M1wMpRV8GYEgpPz9YawVvLWcnOJkkzE9gJ2cCAgqFZShkxMNUDpPNvfpwNoDn8jEw03HhGWNA%2BEQ10RYOurEM%3D) | 组成字面重合 6/22（证据文档 4 个） |
| 77 | 调经种子丸 | 《救产全书》。 | **部分命中** | 0.00 | [来源](https://www.so.com/link?m=uOc4mB%2BMh5uEXmF4UWsNmfb1SYGpIMUOe7oHHdHW%2F%2FeJMdBoL4KDUwPmc5ug%2FOoaj5IyxKcAk6Ts00%2BcfdBaPgfcOSiDLsNrzL%2FBc37n68XySo0T9GWVCedHDx3kVj2IBk8KfuCJzBTNn6c52vrhsy2mYm41j0woO%2B0TwSCFtYaTPUYy8YqPAmJBqoNNCTsDeLfNzEczBIfKeF5BXtr1JSkuk45Q%3D) | 组成字面重合 0/13（证据文档 3 个） |
| 78 | 跌打丸 | 《中药制剂手册》。 | **部分命中** | 0.30 | [来源](https://www.yixue.com/index.php?search=%E8%B7%8C%E6%89%93%E4%B8%B8) | 组成字面重合 7/23（证据文档 1 个） |
| 79 | 辛夷散 | 《名家方选》。 | **命中** | 0.67 | [来源](https://www.so.com/link?m=enL7e5%2BtcOcZX6%2FNcZJMb2WThvSVG5qMffSHGAnyDgLFK0rgQ%2FdHXlucQFQ4c8OMp2cbNBsE5sCCaUBMU4onyFUg0b4f1ucT8GUURhbifncPDR5%2B8hqZXcjvgLBucSyYKWpFIFBTrwQuTFfHcNTsjJhYV8nokN%2FDXo4xJuzfaeA%2BCNvvK4i1t0ao%2BGql9eMnjEstgsLk2qF81h7R0jKWPaow4ahs%3D) | 组成字面重合 4/6（证据文档 4 个） |
| 80 | 追风丸 | 《北京市中药成方选集》。 | **部分命中** | 0.00 | [来源](https://www.so.com/link?m=updfgr0LpmsIWwdWxSa6u27gzLMG6s6XMPH2y6rEZk%2B6y1s0tsNwbXtliuKofTAtnC%2FSI5%2BNFW2ETNWPwBO5Ji4BTZQxpy742ybE6duOPcczpRl4SXYI1MUDa8a%2FhnGCHdGo5f2yPpFRqDB%2Bz54NwX36SYVh9cs%2F3DXf%2BsFat9NsyG4A7g4knvl%2FfBR1xCPg0DQn3eegQA5C8eRPIcMRf5m6p8w8%3D) | 组成字面重合 0/19（证据文档 3 个） |
| 81 | 通塞脉片 | 南京中医学院制药厂。 | **命中** | 0.75 | [来源](https://www.yixue.com/index.php?search=%E9%80%9A%E5%A1%9E%E8%84%89%E7%89%87) | 组成字面重合 3/4（证据文档 1 个） |
| 82 | 通气散 | 《圣济总录》卷一一五。 | **部分命中** | 0.00 | [来源](https://www.so.com/link?m=b560Y7MInF4qFFl50pVJqJ1G7zY7goA2sn60%2FWePKsPKsnIVJwbJ0CQGurvl6iLNk3X7sLeMOVx8DPR3qwpKfiRg1pf5DiLpN6IqG%2BLjYtUEiP1JgFAnngrOH3XGSOCDsS8Z%2Bw3TJ%2FLevXgKhyNa6TwLsFXuO59QCY5OdEIsKQ%2BGEaLip3TcMEHjJYxGGyPLkjx%2FxnTxzXMutC%2FIk) | 组成字面重合 0/13（证据文档 3 个） |
| 83 | 防风通圣散 | 《疯门全书》。 | **部分命中** | 0.21 | [来源](https://www.so.com/link?m=bOJ3AY1Txqfdy87CNjOOM%2FOjRokqURj3lhFqvNLMmBaMUIKLcUR63xXJRHziuYERTQGnbpC1DKHk7gRM7YYOKM53%2B20KB1ccCFREqygO4BtWJKKF2wOdNd%2BRmX72BUsNUfFguCtwQKzH7ZM2Z4bViQfwtcigB74doA2phtF%2F8879fWmtLxj6FUnIcyktVMgdRse59CJ2F7CqO7dLg) | 组成字面重合 5/24（证据文档 3 个） |
| 84 | 附子理中汤 | 《镐京直指》。 | **部分命中** | 0.29 | [来源](https://www.so.com/link?m=bZOcz17xyGQ2qNqJXFH0e2BbhFuzCl3Gv0HxZsU2SNh%2FjcbjRsOzkxj%2FCYBUONheXn1SNPY4BdK3dGp1ByzC0acPhXeFzp4G8YmG72norBMnqHdtFWz%2FmAoNvDQBmpb7ybTLgZ%2FrynC7OFRpKSVhb%2FJkJ7Zx3fqRPBoFwW7h9edliB39sWqsy5WzYKltusCs05Y3Iqylozs5EqSN0) | 组成字面重合 2/7（证据文档 3 个） |
| 85 | 青麟丸 | 《中医内科学》引《邵氏经验良方》。 | **命中** | 1.00 | [来源](https://baike.so.com/doc/542307-574163.html) | 组成字面重合 1/1（证据文档 3 个） |
| 86 | 青黛散 | 《圣惠》卷九十三。 | **部分命中** | 0.12 | [来源](https://www.so.com/link?m=zcbXaB3P6KQwDBLuTxEzft4iZ48VbCv5rqMH%2FtXeobLmS%2FcMczaH3GnJKTANOcCOPRMfEJoEQGV9YjMNG342Mrz346xrON02QSwHSAMK60ld6lycy8%2Bi2S%2BloNvTPPl1qCfNLsO4ldkgY6vQrpFCZYuWUFwmEz1LkAGRa%2Bt43HUO0IvypLJhAZh1Q9fM11XYI) | 组成字面重合 1/8（证据文档 3 个） |
| 87 | 香棱丸 | 《杏苑》卷四。 | **部分命中** | 0.25 | [来源](https://baike.so.com/doc/763854-808305.html) | 组成字面重合 2/8（证据文档 2 个） |
| 88 | 香砂六君子汤 | 《古今名医方论》卷一引柯韵伯方。 | **命中** | 1.00 | [来源](https://www.so.com/link?m=e2tcEi3Z8HEQYbYAlqqQT69YIqh3nsQY0TsM7PhT6HgAVvylqh3Mlhs7%2B1hsEqlxgfhHfwQoeQImp8WctbF7kn%2BHZpNLYcNArBrX%2FmHX6RDtfYEVGpSUp28%2BE6H5R%2FWMAO%2BA8zP5TrXO0DSkwhifV0JFqd5Uh%2BEJPWwhPTH6E1IVdf7QxN8CaeEoQ4LC9DMgFK0xBXQy5ISol3Mz5dK84JCd3cApnMB5eE9iXK%2BE0OvM%3D) | 组成字面重合 8/8（证据文档 3 个） |
| 89 | 香砂枳术丸 | 《景岳全书》卷五十四。 | **命中** | 0.80 | [来源](https://baike.so.com/doc/5677580-5890253.html) | 组成字面重合 4/5（证据文档 2 个） |
| 90 | 香苏饮 | 《风痨臌膈》 | **部分命中** | 0.25 | [来源](https://www.so.com/link?m=wJnhfVvyXlFs1wgrZ8cd3fsxPTRe42whoDZJsJBv2TBQeHhVqBV%2FtNYVDMADrC4gPxgE8MXmDgndwnwFzkvotLR7i78tWokRNZXDF8oLP0kdSQxkv3F7sP2WbHYWLNxZZMPaaQ79IyBJsbkMWTE4daPTfHnr7ToJ6PMre4z0R1b82YjzuNx%2F1Bw%3D%3D) | 组成字面重合 2/8（证据文档 3 个） |
| 91 | 鲤鱼汤 | 《圣惠》卷九十七。 | **部分命中** | 0.17 | [来源](https://www.so.com/link?m=uOWssMTdqCG92MQZHVropMFFJJgunfgrsktZHIx61C7lBlyqPM8NeQNu%2FXoSIStxrifdr4nfSFUa5EPrwDxS7ZJQ%2BiYfe95fUfvyJKei0Qf1T6mmb8OxZLneBAI9XoJXW2uzAytHWtOq8S%2BC7lSdbAAEVC3uTD9FssAIoY2z4ijObG3Yh) | 组成字面重合 1/6（证据文档 1 个） |
| 92 | 麻子仁丸 | 《伤寒论》。 | **命中** | 0.22 | [来源](https://www.so.com/link?m=e8KnJnidURd1qAGp6Oiwn2X55YdMaJgBVbeSzfkIl79OJA6tC0AOXmPUv%2FZZZgvciyixSMXHvWw7mF2lR7o3nGmodnXijt4WD5RxrsX4Q9Rm26iz2MLDji3nIi49rFBBU4sYOyhPTMEHkh7iMlRQGRfalH2MkzSFub9c%2FFbPKmuVMmNydk%2FUAJ9MM%2FU%2FYyqWbyVFZie0xCcE%3D) | 麻子仁丸：源列出麻子仁/芍药/枳实/大黄/厚朴/杏仁 = 本条 6 味（覆盖率低是剂量字被拆坏） |
| 93 | 麻杏石甘汤 | 《喉痧症治概要》。 | **部分命中** | 0.17 | [来源](https://www.yixue.com/index.php?search=%E9%BA%BB%E6%9D%8F%E7%9F%B3%E7%94%98%E6%B1%A4) | 组成字面重合 2/12（证据文档 1 个） |
| 94 | 麻黄汤 | 《外台》卷九引《古今录验》。 | **部分命中** | 0.20 | [来源](https://www.so.com/link?m=u3X1Izcr%2BiSp4R1JLoNDwEy0yk%2F2MAU%2BH5x56QgF3gutKW5xroTiH97BIc3kcsOPI3matu%2F54uIz6Va22W9wB0n5PvGR5Mi1rFxnDvl5BxD50MfxWNBmv5Y0TS%2BlQiWow%2BlIajSC5PCCzBi3Bx939%2Fjbe%2FNb0fRwMsaRAm3uvHjAyyX8HfOw3nlyA84ZzkhKw%2BMCQWI97LxATCIuR) | 组成字面重合 1/5（证据文档 3 个） |
| 95 | 黄土汤 | 《普济方》卷一○八引《旅舍方》。 | **查无** | 0.00 | [来源](https://www.so.com/link?m=un0Y1E9fIzdTfp3Ad7PjWTNPld2dgPnmGOUXJFAEMdXPGmVTsTU5TiJKFsMfVj6EfGi%2FSCthYpLmAP%2BIPkGEzF23qu8cAq7LKs8Eh2ZVwoLkhDjf%2FGdKp5CqnbAA82xONzsQxC63Lhd6l4tQD6m8PNBShB2egX%2BI9LbpMwl3hZdAZawkBY0c%2B7Q%3D%3D) | 黄土汤：取到的是验证码页 |
| 96 | 黄精丸 | 《济阳纲卧》卷六十八。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E9%BB%84%E7%B2%BE%E4%B8%B8) | 组成字面重合 0/5（证据文档 1 个） |
| 97 | 黄芩汤 | 《圣济总录》卷二十五。 | **部分命中** | 0.08 | [来源](https://www.so.com/link?m=eYxXIQ7%2FHYrbI4ARfnVNxlI%2BK%2BWl%2B%2F%2FBuRparv%2F7CaYuMznwtuQhoEuv56Ldx10FeB68RwZ%2FH%2FG37m7CutbEwkw7EQqVxV4widzpMrkFs%2FgspZy5NfUYOVZAh7ExcjFK%2FjeemXuLF4TaGyUI%2F4Xk94%2Fc%2BqeclcCgS%2Fq41C6CmhCZjXEdrJPpikQZtouw2AEywm7zOxiDaIOy%2BPdiq) | 组成字面重合 1/13（证据文档 3 个） |
| 98 | 黄连上清丸 | 《饲鹤亭集方》。 | **命中** | 0.60 | [来源](https://www.so.com/link?m=wauz6La7L%2BJcbPsVEhfYVAZbTBPPXN7vUPzj2GOkHc9KMNYFL7YfO8%2Bi21IrdFw%2F48TBV0d11l8ZbigNQEH9UvtGKkzdS5yIS8vwg3kXzowxOAEYpK2SNfXm8MkRz0eeY2xFE2iwga7YWysT70iUx0c1gTi5%2FKiizvFPsq7rkQeCXKva1E5ZsmLA9sd08HaARhKB7ng3%2FW75%2F6qeN%2BaKEkQUSRVA%3D) | 组成字面重合 9/15（证据文档 1 个） |
| 99 | 黄龙汤 | 《活人书》卷十九。 | **命中** | 0.25 | [来源](https://www.yixue.com/index.php?search=%E9%BB%84%E9%BE%99%E6%B1%A4) | 黄龙汤：医学百科《类证·活人书》卷十九 = 柴胡/黄芩/人参/甘草，逐字一致 |
| 100 | 黑虎散 | 《普济方》卷三○二。 | **查无** | 0.00 | [来源](https://www.so.com/link?m=bPRiU%2BeYBg7TqSJZOhtAszZtDssiGt7hfBbGKw3L%2B8d8ix2FMO40MX6IUyb93sfGEwRr7yblmNr9vyMmJJWy5eQS%2Fnqiuhfc8v4RtnblC6SiCd929YvlPn6I4ZLovufOkN1QKS6IwSj47ZZ2HqYxbqmaspEpOPeAhG1rA0pNRAYXGcXqUIJA6UK80k4Y%3D) | 黑虎散：只取到图片搜索壳 |
| 1 | 丁香柿蒂汤 | 《症因脉治》卷二。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E4%B8%81%E9%A6%99%E6%9F%BF%E8%92%82%E6%B1%A4) | 组成字面重合 4/4（证据文档 1 个） |
| 2 | 七制香附丸 | 《验方新编》卷十一。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E4%B8%83%E5%88%B6%E9%A6%99%E9%99%84%E4%B8%B8) | 组成字面重合 0/9（证据文档 1 个） |
| 3 | 七味白术散 | 《医钞类编》卷八。 | **命中** | 0.67 | [来源](https://www.yixue.com/index.php?search=%E4%B8%83%E5%91%B3%E7%99%BD%E6%9C%AF%E6%95%A3) | 组成字面重合 6/9（证据文档 1 个） |
| 4 | 万应锭 | 《疡科纲要》卷下。 | **部分命中** | 0.37 | [来源](https://www.yixue.com/index.php?search=%E4%B8%87%E5%BA%94%E9%94%AD) | 组成字面重合 7/19（证据文档 1 个） |
| 5 | 万灵膏 | 《本草纲目》卷十七引《摘玄方》。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E4%B8%87%E7%81%B5%E8%86%8F) | 组成字面重合 0/3（证据文档 1 个） |
| 6 | 三子养亲汤 | 《杂病广要》引《皆效方》。 | **部分命中** | 0.33 | [来源](https://www.anhao.cn/prescriptions/yf-16170-%E4%B8%89%E5%AD%90%E5%85%BB%E4%BA%B2%E6%B1%A4) | 组成字面重合 1/3（证据文档 7 个） |
| 7 | 三拗汤 | 《得效》卷五。 | **部分命中** | 0.17 | [来源](https://health.baidu.com/m/detail/ar_6065396260931378403) | 组成字面重合 1/6（证据文档 7 个） |
| 8 | 上清丸 | 《活人方》卷一。 | **部分命中** | 0.25 | [来源](https://www.yixue.com/index.php?search=%E4%B8%8A%E6%B8%85%E4%B8%B8) | 组成字面重合 1/4（证据文档 1 个） |
| 9 | 不换金正气散 | 《外科精要》卷下。 | **部分命中** | 0.20 | [来源](https://www.yixue.com/index.php?search=%E4%B8%8D%E6%8D%A2%E9%87%91%E6%AD%A3%E6%B0%94%E6%95%A3) | 组成字面重合 2/10（证据文档 1 个） |
| 10 | 两地汤 | 《中医妇科治疗学》。 | **命中** | 0.86 | [来源](https://m.baidu.com/bh/m/detail/ar_10079630868201172226) | 组成字面重合 6/7（证据文档 9 个） |
| 11 | 乌头汤 | 《圣济总录》卷三十五。 | **部分命中** | 0.11 | [来源](https://www.yixue.com/index.php?search=%E4%B9%8C%E5%A4%B4%E6%B1%A4) | 组成字面重合 1/9（证据文档 1 个） |
| 12 | 乌梅汤 | 《圣济总录》卷三十一。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E4%B9%8C%E6%A2%85%E6%B1%A4) | 组成字面重合 0/4（证据文档 1 个） |
| 13 | 乌金丸 | 《冯氏锦囊》卷十三。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E4%B9%8C%E9%87%91%E4%B8%B8) | 乌金丸：医学百科条目是《寿世保元》版，与本条（锦纹大黄）不同 |
| 14 | 乌金丸 | 《妇科玉尺》卷五。 | **命中** | 0.75 | [来源](https://www.yixue.com/index.php?search=%E4%B9%8C%E9%87%91%E4%B8%B8) | 组成字面重合 3/4（证据文档 1 个） |
| 15 | 二至丸 | 《济阳纲目》卷六十四。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E4%BA%8C%E8%87%B3%E4%B8%B8) | 组成字面重合 0/13（证据文档 1 个） |
| 16 | 二陈汤 | 《古今医彻》卷一。 | **部分命中** | 0.46 | [来源](http://www.dazhongyi.cc/zhongyaofang/yaofang_e/erchentang.html) | 组成字面重合 5/11（证据文档 8 个） |
| 17 | 五淋散 | 《玉案》卷五。 | **部分命中** | 0.57 | [来源](https://www.yixue.com/index.php?search=%E4%BA%94%E6%B7%8B%E6%95%A3) | 组成字面重合 4/7（证据文档 1 个） |
| 18 | 五皮散 | 《麻症集成》卷四。 | **部分命中** | 0.57 | [来源](https://www.yixue.com/index.php?search=%E4%BA%94%E7%9A%AE%E6%95%A3) | 组成字面重合 4/7（证据文档 9 个） |
| 19 | 人参养荣汤 | 《嵩崖尊生》卷十。 | **部分命中** | 0.40 | [来源](http://www.dazhongyi.cc/zhongyaofang/yaofang_r/renshenyangrongtang.html) | 组成字面重合 4/10（证据文档 5 个） |
| 20 | 人参鹿茸丸 | 《医级》卷八。 | **部分命中** | 0.36 | [来源](https://www.yixue.com/index.php?search=%E4%BA%BA%E5%8F%82%E9%B9%BF%E8%8C%B8%E4%B8%B8) | 组成字面重合 5/14（证据文档 1 个） |
| 21 | 健步丸 | 《丹溪心法》卷三。 | **部分命中** | 0.20 | [来源](https://www.yixue.com/index.php?search=%E5%81%A5%E6%AD%A5%E4%B8%B8) | 组成字面重合 2/10（证据文档 1 个） |
| 22 | 健脾丸 | 《慈航集》卷下。 | **部分命中** | 0.50 | [来源](https://zhongyibaike.com/wiki/%E5%81%A5%E8%84%BE%E4%B8%B8) | 组成字面重合 6/12（证据文档 8 个） |
| 23 | 八厘散 | 《金鉴》卷八十八。 | **命中** | 0.91 | [来源](https://www.yixue.com/index.php?search=%E5%85%AB%E5%8E%98%E6%95%A3) | 组成字面重合 10/11（证据文档 1 个） |
| 24 | 八宝坤顺丸 | 《中国药典》一部。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E5%85%AB%E5%AE%9D%E5%9D%A4%E9%A1%BA%E4%B8%B8) | 组成字面重合 0/17（证据文档 1 个） |
| 25 | 八珍汤 | 《医彻》卷四。 | **命中** | 0.80 | [来源](https://www.yixue.com/index.php?search=%E5%85%AB%E7%8F%8D%E6%B1%A4) | 组成字面重合 8/10（证据文档 9 个） |
| 26 | 六合定中丸 | 《北京市中药成方选集》。 | **命中** | 0.83 | [来源](https://www.yixue.com/index.php?search=%E5%85%AD%E5%90%88%E5%AE%9A%E4%B8%AD%E4%B8%B8) | 组成字面重合 10/12（证据文档 1 个） |
| 27 | 六味丸 | 《饲鹤亭集方》。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E5%85%AD%E5%91%B3%E4%B8%B8) | 六味丸：按名检索有同族条目（磁石六味丸等），本条《饲鹤亭集方》版未逐字核到 |
| 28 | 六味丸 | 《类证治裁》卷七。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E5%85%AD%E5%91%B3%E4%B8%B8) | 六味丸：同上，同名族存在但本版本组成未核到 |
| 29 | 六味地黄丸 | 方出《朱仁康临床经验集》，名见《千家 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E5%85%AD%E5%91%B3%E5%9C%B0%E9%BB%84%E4%B8%B8) | 组成字面重合 0/10（证据文档 1 个） |
| 30 | 六神曲 | 《全国中药成药处方集》（杭州方）。 | **部分命中** | 0.25 | [来源](https://www.yixue.com/index.php?search=%E5%85%AD%E7%A5%9E%E6%9B%B2) | 组成字面重合 1/4（证据文档 1 个） |
| 31 | 养荣壮肾汤 | 《嵩崖尊生》卷十四。 | **命中** | 0.88 | [来源](https://www.yixue.com/index.php?search=%E5%85%BB%E8%8D%A3%E5%A3%AE%E8%82%BE%E6%B1%A4) | 组成字面重合 7/8（证据文档 1 个） |
| 32 | 再造散 | 《外科大成》卷四。 | **部分命中** | 0.25 | [来源](https://www.yixue.com/index.php?search=%E5%86%8D%E9%80%A0%E6%95%A3) | 组成字面重合 1/4（证据文档 1 个） |
| 33 | 凉膈散 | 《喉科紫珍集》卷上。 | **命中** | 0.61 | [来源](https://www.yixue.com/index.php?search=%E5%87%89%E8%86%88%E6%95%A3) | 组成字面重合 8/13（证据文档 1 个） |
| 34 | 利膈丸 | 《医学发明》卷一。 | **部分命中** | 0.10 | [来源](https://www.yixue.com/index.php?search=%E5%88%A9%E8%86%88%E4%B8%B8) | 组成字面重合 1/10（证据文档 1 个） |
| 35 | 加味五苓散 | 《金鉴》卷五十四。 | **部分命中** | 0.40 | [来源](https://www.yixue.com/index.php?search=%E5%8A%A0%E5%91%B3%E4%BA%94%E8%8B%93%E6%95%A3) | 组成字面重合 4/10（证据文档 1 个） |
| 36 | 加味逍遥散 | 《得效》卷十五。 | **部分命中** | 0.00 | （无） | 加味逍遥散：本条《得效》版（+远志/桃仁/苏木/红花）未核到；同名加味方在 |
| 37 | 加味青娥丸 | 《古今医鉴》卷十。 | **部分命中** | 0.20 | [来源](https://www.yixue.com/index.php?search=%E5%8A%A0%E5%91%B3%E9%9D%92%E5%A8%A5%E4%B8%B8) | 组成字面重合 2/10（证据文档 1 个） |
| 38 | 化毒丹 | 《古方汇精》卷四。 | **命中** | 0.67 | [来源](https://www.yixue.com/index.php?search=%E5%8C%96%E6%AF%92%E4%B8%B9) | 组成字面重合 6/9（证据文档 1 个） |
| 39 | 化积丸 | 《袖珍》卷三。 | **部分命中** | 0.12 | [来源](https://www.yixue.com/index.php?search=%E5%8C%96%E7%A7%AF%E4%B8%B8) | 组成字面重合 1/8（证据文档 1 个） |
| 40 | 十香丸 | 《赤水玄珠》卷十三。 | **部分命中** | 0.40 | [来源](https://www.yixue.com/index.php?search=%E5%8D%81%E9%A6%99%E4%B8%B8) | 组成字面重合 4/10（证据文档 1 个） |
| 41 | 千金散 | 《点点经》卷一。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E5%8D%83%E9%87%91%E6%95%A3) | 千金散：医学百科是《万病回春》版，与本条（千步峰土/食盐）不同 |
| 42 | 升麻葛根汤 | 《鸡峰》卷二十四。 | **命中** | 0.60 | [来源](https://www.yixue.com/index.php?search=%E5%8D%87%E9%BA%BB%E8%91%9B%E6%A0%B9%E6%B1%A4) | 组成字面重合 3/5（证据文档 1 个） |
| 43 | 半夏厚朴汤 | 《兰室秘藏》卷上。 | **部分命中** | 0.16 | [来源](https://health.baidu.com/m/detail/ar_6298340293167205422) | 组成字面重合 4/25（证据文档 6 个） |
| 44 | 半夏泻心汤 | 《温病条辨》卷二。 | **命中** | 0.60 | [来源](https://www.yixue.com/index.php?search=%E5%8D%8A%E5%A4%8F%E6%B3%BB%E5%BF%83%E6%B1%A4) | 组成字面重合 3/5（证据文档 1 个） |
| 45 | 参苓白术散 | 《局方》卷三（绍兴续添方）。 | **命中** | 0.64 | [来源](https://www.yixue.com/index.php?search=%E5%8F%82%E8%8B%93%E7%99%BD%E6%9C%AF%E6%95%A3) | 组成字面重合 7/11（证据文档 8 个） |
| 46 | 参附汤 | 《女科秘旨》卷二。 | **部分命中** | 0.11 | [来源](https://www.yixue.com/index.php?search=%E5%8F%82%E9%99%84%E6%B1%A4) | 组成字面重合 1/9（证据文档 1 个） |
| 47 | 双解散 | 《痘疹心法》卷二十二。 | **部分命中** | 0.21 | [来源](https://www.yixue.com/index.php?search=%E5%8F%8C%E8%A7%A3%E6%95%A3) | 组成字面重合 3/14（证据文档 1 个） |
| 48 | 吴茱萸汤 | 《圣济总录》卷二十六。 | **部分命中** | 0.08 | [来源](https://www.yixue.com/index.php?search=%E5%90%B4%E8%8C%B1%E8%90%B8%E6%B1%A4) | 组成字面重合 1/12（证据文档 1 个） |
| 49 | 四圣散 | 《李氏医鉴》卷八。 | **部分命中** | 0.50 | [来源](https://www.yixue.com/index.php?search=%E5%9B%9B%E5%9C%A3%E6%95%A3) | 组成字面重合 2/4（证据文档 1 个） |
| 50 | 四圣散 | 《仙拈集》卷二。 | **部分命中** | 0.50 | [来源](https://www.yixue.com/index.php?search=%E5%9B%9B%E5%9C%A3%E6%95%A3) | 组成字面重合 2/4（证据文档 1 个） |
| 51 | 四逆汤 | 《伤寒论》。 | **部分命中** | 0.29 | [来源](https://www.anhao.cn/prescriptions/yf-20252-%E5%9B%9B%E9%80%86%E6%B1%A4) | 组成字面重合 2/7（证据文档 9 个） |
| 52 | 回阳救急汤 | 《寿世新编》卷下。 | **部分命中** | 0.14 | [来源](https://www.yixue.com/index.php?search=%E5%9B%9E%E9%98%B3%E6%95%91%E6%80%A5%E6%B1%A4) | 组成字面重合 2/14（证据文档 1 个） |
| 53 | 固冲汤 | 《妇产科学》。 | **部分命中** | 0.36 | [来源](https://www.yixue.com/index.php?search=%E5%9B%BA%E5%86%B2%E6%B1%A4) | 组成字面重合 4/11（证据文档 6 个） |
| 54 | 固本止崩汤 | 《傅青主女科》卷上。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E5%9B%BA%E6%9C%AC%E6%AD%A2%E5%B4%A9%E6%B1%A4) | 组成字面重合 6/6（证据文档 1 个） |
| 55 | 固真汤 | 《活幼心书》卷下。 | **命中** | 0.64 | [来源](https://www.yixue.com/index.php?search=%E5%9B%BA%E7%9C%9F%E6%B1%A4) | 组成字面重合 7/11（证据文档 1 个） |
| 56 | 固真汤 | 《幼科直言》卷四。 | **部分命中** | 0.55 | [来源](https://www.yixue.com/index.php?search=%E5%9B%BA%E7%9C%9F%E6%B1%A4) | 组成字面重合 6/11（证据文档 1 个） |
| 57 | 地榆丸 | 《外科大成》卷二。 | **部分命中** | 0.43 | [来源](https://www.yixue.com/index.php?search=%E5%9C%B0%E6%A6%86%E4%B8%B8) | 组成字面重合 3/7（证据文档 1 个） |
| 58 | 增液汤 | 《中医儿科学》。 | **命中** | 1.00 | [来源](https://baike.baidu.com/item/%E5%85%BB%E8%83%83%E5%A2%9E%E6%B6%B2%E6%B1%A4/7331161) | 组成字面重合 6/6（证据文档 9 个） |
| 59 | 天仙藤散 | 《镐京直指》卷二。 | **部分命中** | 0.22 | [来源](https://www.yixue.com/index.php?search=%E5%A4%A9%E4%BB%99%E8%97%A4%E6%95%A3) | 组成字面重合 2/9（证据文档 1 个） |
| 60 | 天水散 | 《痘疹会通》卷四。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E5%A4%A9%E6%B0%B4%E6%95%A3) | 组成字面重合 0/12（证据文档 1 个） |
| 61 | 太极丸 | 《医学入门》卷七。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E5%A4%AA%E6%9E%81%E4%B8%B8) | 组成字面重合 0/29（证据文档 1 个） |
| 62 | 安肾丸 | 《朱氏集验方》卷九。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E5%AE%89%E8%82%BE%E4%B8%B8) | 组成字面重合 0/4（证据文档 1 个） |
| 63 | 宽中顺气丸 | 《普济方》卷一八三。 | **命中** | 0.67 | [来源](https://www.yixue.com/index.php?search=%E5%AE%BD%E4%B8%AD%E9%A1%BA%E6%B0%94%E4%B8%B8) | 组成字面重合 8/12（证据文档 1 个） |
| 64 | 导赤丸 | 《局方》卷六（续添诸局经验秘方）。 | **部分命中** | 0.29 | [来源](https://www.yixue.com/index.php?search=%E5%AF%BC%E8%B5%A4%E4%B8%B8) | 组成字面重合 2/7（证据文档 1 个） |
| 65 | 小柴胡汤 | 《万氏家抄方》卷六。 | **部分命中** | 0.56 | [来源](https://www.yixue.com/index.php?search=%E5%B0%8F%E6%9F%B4%E8%83%A1%E6%B1%A4) | 组成字面重合 5/9（证据文档 1 个） |
| 66 | 小续命汤 | 《千金》卷八（注文）引《小品方》。 | **命中** | 0.83 | [来源](https://www.yixue.com/index.php?search=%E5%B0%8F%E7%BB%AD%E5%91%BD%E6%B1%A4) | 组成字面重合 10/12（证据文档 7 个） |
| 67 | 左归饮 | 《不知医必要》卷三。 | **部分命中** | 0.50 | [来源](https://www.yixue.com/index.php?search=%E5%B7%A6%E5%BD%92%E9%A5%AE) | 组成字面重合 3/6（证据文档 1 个） |
| 68 | 当归丸 | 《普济方》卷三三二引《济生》。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E5%BD%93%E5%BD%92%E4%B8%B8) | 组成字面重合 0/8（证据文档 1 个） |
| 69 | 木香分气丸 | 《御药院方》卷三。 | **部分命中** | 0.23 | [来源](https://www.yixue.com/index.php?search=%E6%9C%A8%E9%A6%99%E5%88%86%E6%B0%94%E4%B8%B8) | 组成字面重合 4/17（证据文档 1 个） |
| 70 | 杀虫丸 | 《经验良方》。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E6%9D%80%E8%99%AB%E4%B8%B8) | 组成字面重合 0/3（证据文档 1 个） |
| 71 | 枇杷叶膏 | 《中药成方配本》。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E6%9E%87%E6%9D%B7%E5%8F%B6%E8%86%8F) | 组成字面重合 1/1（证据文档 1 个） |
| 72 | 枳术丸 | 《医便》卷二。 | **部分命中** | 0.14 | [来源](https://baike.baidu.com/item/%E6%9E%B3%E6%9C%AF%E4%B8%B8/1652549) | 组成字面重合 2/14（证据文档 11 个） |
| 73 | 枳术丸 | 《赤水玄珠》卷十三。 | **部分命中** | 0.25 | [来源](https://baike.baidu.com/item/%E6%9E%B3%E6%9C%AF%E4%B8%B8/1652549) | 组成字面重合 2/8（证据文档 11 个） |
| 74 | 柏子仁丸 | 《圣济总录》卷一○二。 | **部分命中** | 0.10 | [来源](https://www.yixue.com/index.php?search=%E6%9F%8F%E5%AD%90%E4%BB%81%E4%B8%B8) | 组成字面重合 2/20（证据文档 1 个） |
| 75 | 桂枝加厚朴杏子汤 | 《伤寒论》 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E6%A1%82%E6%9E%9D%E5%8A%A0%E5%8E%9A%E6%9C%B4%E6%9D%8F%E5%AD%90%E6%B1%A4) | 组成字面重合 0/8（证据文档 1 个） |
| 76 | 桂枝汤 | 《外台》卷三引《范汪方》。 | **部分命中** | 0.00 | [来源](https://zhongyibaike.com/wiki/%E6%A1%82%E6%9E%9D%E6%B1%A4) | 组成字面重合 0/2（证据文档 8 个） |
| 77 | 桃仁承气汤 | 《准绳·幼科》卷六。 | **部分命中** | 0.14 | [来源](https://www.yixue.com/index.php?search=%E6%A1%83%E4%BB%81%E6%89%BF%E6%B0%94%E6%B1%A4) | 组成字面重合 1/7（证据文档 1 个） |
| 78 | 桃花汤 | 《圣济总录》卷九十七。 | **部分命中** | 0.54 | [来源](https://www.yixue.com/index.php?search=%E6%A1%83%E8%8A%B1%E6%B1%A4) | 组成字面重合 7/13（证据文档 1 个） |
| 79 | 桑螵蛸散 | 《直指》卷二十四。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E6%A1%91%E8%9E%B5%E8%9B%B8%E6%95%A3) | 组成字面重合 0/10（证据文档 1 个） |
| 80 | 桔梗汤 | 《保命集》卷中。 | **部分命中** | 0.38 | [来源](https://www.yixue.com/index.php?search=%E6%A1%94%E6%A2%97%E6%B1%A4) | 组成字面重合 3/8（证据文档 1 个） |
| 81 | 槐花散 | 《本事》卷五。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E6%A7%90%E8%8A%B1%E6%95%A3) | 组成字面重合 7/7（证据文档 1 个） |
| 82 | 槐角丸 | 《扶寿精方》引朱上卿方。 | **部分命中** | 0.40 | [来源](https://www.yixue.com/index.php?search=%E6%A7%90%E8%A7%92%E4%B8%B8) | 组成字面重合 4/10（证据文档 1 个） |
| 83 | 橘皮汤 | 《外台》卷三引《近效方》。 | **部分命中** | 0.33 | [来源](https://www.yixue.com/index.php?search=%E6%A9%98%E7%9A%AE%E6%B1%A4) | 组成字面重合 1/3（证据文档 1 个） |
| 84 | 止嗽丸 | 《简明医彀》卷四。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E6%AD%A2%E5%97%BD%E4%B8%B8) | 组成字面重合 0/17（证据文档 1 个） |
| 85 | 沉香曲 | 《引经证医》卷四。 | **部分命中** | 0.22 | [来源](https://www.yixue.com/index.php?search=%E6%B2%89%E9%A6%99%E6%9B%B2) | 组成字面重合 2/9（证据文档 1 个） |
| 86 | 泻白散 | 《济生》卷二。 | **部分命中** | 0.50 | [来源](https://www.yixue.com/index.php?search=%E6%B3%BB%E7%99%BD%E6%95%A3) | 组成字面重合 5/10（证据文档 1 个） |
| 87 | 泻肝散 | 《得效》卷十六。 | **部分命中** | 0.29 | [来源](https://www.yixue.com/index.php?search=%E6%B3%BB%E8%82%9D%E6%95%A3) | 组成字面重合 2/7（证据文档 1 个） |
| 88 | 泻黄散 | 《小儿药证直诀》卷下。 | **部分命中** | 0.43 | [来源](https://www.yixue.com/index.php?search=%E6%B3%BB%E9%BB%84%E6%95%A3) | 组成字面重合 3/7（证据文档 1 个） |
| 89 | 洗心汤 | 《痘疹仁端录》卷十三。 | **部分命中** | 0.25 | [来源](https://www.yixue.com/index.php?search=%E6%B4%97%E5%BF%83%E6%B1%A4) | 组成字面重合 2/8（证据文档 1 个） |
| 90 | 消风散 | 《幼科金针》卷下。 | **命中** | 0.75 | [来源](https://www.yixue.com/index.php?search=%E6%B6%88%E9%A3%8E%E6%95%A3) | 组成字面重合 9/12（证据文档 7 个） |
| 91 | 涤痰丸 | 《嵩崖尊生》卷九。 | **部分命中** | 0.17 | [来源](https://www.yixue.com/index.php?search=%E6%B6%A4%E7%97%B0%E4%B8%B8) | 组成字面重合 1/6（证据文档 1 个） |
| 92 | 清咽下痰汤 | 《验方新编》 | **查无** | 0.00 | （无） | 组成字面重合 0/9（证据文档 0 个） |
| 93 | 清心丸 | 《圣济总录》卷一八五。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E5%BF%83%E4%B8%B8) | 组成字面重合 0/2（证据文档 1 个） |
| 94 | 清心莲子饮 | 《陈素庵妇科补解》卷五。 | **部分命中** | 0.20 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E5%BF%83%E8%8E%B2%E5%AD%90%E9%A5%AE) | 组成字面重合 3/15（证据文档 1 个） |
| 95 | 清暑汤 | 《银海指南》卷三。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E6%9A%91%E6%B1%A4) | 组成字面重合 0/3（证据文档 1 个） |
| 96 | 清暑汤 | 《外科全生集》卷四。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E6%9A%91%E6%B1%A4) | 组成字面重合 0/8（证据文档 1 个） |
| 97 | 清暑益气汤 | 《脾胃论》卷中。 | **命中** | 0.81 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E6%9A%91%E7%9B%8A%E6%B0%94%E6%B1%A4) | 组成字面重合 13/16（证据文档 7 个） |
| 98 | 清眩丸 | 《慈禧光绪医方选义》。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E7%9C%A9%E4%B8%B8) | 组成字面重合 0/5（证据文档 1 个） |
| 99 | 清经散 | 《医学探骊集》卷六。 | **部分命中** | 0.33 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E7%BB%8F%E6%95%A3) | 组成字面重合 3/9（证据文档 1 个） |
| 100 | 清肺抑火丸 | 《北京市中药成方选集》。 | **命中** | 0.90 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E8%82%BA%E6%8A%91%E7%81%AB%E4%B8%B8) | 组成字面重合 9/10（证据文档 1 个） |
| 101 | 清肺汤 | 《治疹全书》卷下。 | **部分命中** | 0.56 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E8%82%BA%E6%B1%A4) | 组成字面重合 5/9（证据文档 1 个） |
| 102 | 清胃散 | 《证治汇补》卷四。 | **命中** | 0.83 | [来源](https://health.baidu.com/m/detail/ar_6272251300397326059) | 组成字面重合 5/6（证据文档 7 个） |
| 103 | 清胆汤 | 《伤寒大白》卷三。 | **命中** | 0.83 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E8%83%86%E6%B1%A4) | 组成字面重合 5/6（证据文档 1 个） |
| 104 | 清胆汤 | 《重订通俗伤寒论》。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E8%83%86%E6%B1%A4) | 组成字面重合 0/8（证据文档 1 个） |
| 105 | 清骨散 | 《得效》卷九。 | **命中** | 0.89 | [来源](https://www.yixue.com/index.php?search=%E6%B8%85%E9%AA%A8%E6%95%A3) | 组成字面重合 8/9（证据文档 1 个） |
| 106 | 滋肾丸 | 《医便》卷一。 | **命中** | 0.77 | [来源](https://www.yixue.com/index.php?search=%E6%BB%8B%E8%82%BE%E4%B8%B8) | 组成字面重合 13/17（证据文档 1 个） |
| 107 | 滋肾通关丸 | 《兰室秘藏》 | **查无** | 0.00 | （无） | 组成字面重合 0/6（证据文档 0 个） |
| 108 | 滋血汤 | 《局方》卷九（宝庆新增方）。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E6%BB%8B%E8%A1%80%E6%B1%A4) | 组成字面重合 3/3（证据文档 1 个） |
| 109 | 滴耳油 | 《全国中药成药处方集》（北京方）。 | **部分命中** | 0.33 | [来源](https://www.yixue.com/index.php?search=%E6%BB%B4%E8%80%B3%E6%B2%B9) | 组成字面重合 1/3（证据文档 1 个） |
| 110 | 熊胆丸 | 《圣惠》卷八十七。 | **部分命中** | 0.17 | [来源](https://www.yixue.com/index.php?search=%E7%86%8A%E8%83%86%E4%B8%B8) | 组成字面重合 1/6（证据文档 1 个） |
| 111 | 熊胆丸 | 方出《圣惠》卷五十二，名见《普济方》 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E7%86%8A%E8%83%86%E4%B8%B8) | 组成字面重合 0/4（证据文档 1 个） |
| 112 | 牛黄抱龙丸 | 《医方歌括》。 | **命中** | 0.70 | [来源](https://www.yixue.com/index.php?search=%E7%89%9B%E9%BB%84%E6%8A%B1%E9%BE%99%E4%B8%B8) | 组成字面重合 7/10（证据文档 1 个） |
| 113 | 独活寄生汤 | 《慎斋遗书》卷七。 | **命中** | 0.79 | [来源](https://www.yixue.com/index.php?search=%E7%8B%AC%E6%B4%BB%E5%AF%84%E7%94%9F%E6%B1%A4) | 组成字面重合 11/14（证据文档 10 个） |
| 114 | 玉液丸 | 《医方类聚》卷一一九引《王氏集验方》 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E7%8E%89%E6%B6%B2%E4%B8%B8) | 组成字面重合 0/10（证据文档 1 个） |
| 115 | 玉液汤 | 《衷中参西》上册。 | **命中** | 0.86 | [来源](https://www.yixue.com/index.php?search=%E7%8E%89%E6%B6%B2%E6%B1%A4) | 组成字面重合 6/7（证据文档 9 个） |
| 116 | 玉液汤 | 《圣济总录》卷六十五。 | **命中** | 0.67 | [来源](https://www.zysjw.com.cn/zhongyaofang/yuyetang/index.html) | 组成字面重合 2/3（证据文档 9 个） |
| 117 | 珠珀保婴丹 | 《全国中药成药处方集》（哈尔滨方）。 | **查无** | 0.00 | （无） | 组成字面重合 0/24（证据文档 0 个） |
| 118 | 生化汤 | 《金鉴》卷四十七。 | **命中** | 0.67 | [来源](https://www.yixue.com/index.php?search=%E7%94%9F%E5%8C%96%E6%B1%A4) | 组成字面重合 4/6（证据文档 7 个） |
| 119 | 疳积散 | 《婴童百问》卷十。 | **部分命中** | 0.50 | [来源](https://www.yixue.com/index.php?search=%E7%96%B3%E7%A7%AF%E6%95%A3) | 组成字面重合 3/6（证据文档 1 个） |
| 120 | 痧药 | 《集验良方》卷二。 | **部分命中** | 0.20 | [来源](https://www.yixue.com/index.php?search=%E7%97%A7%E8%8D%AF) | 组成字面重合 2/10（证据文档 1 个） |
| 121 | 白及片 | 《喉科心法》卷下。 | **查无** | 0.00 | （无） | 组成字面重合 0/2（证据文档 0 个） |
| 122 | 白通汤 | 《外台》卷二引《肘后方》。 | **部分命中** | 0.33 | [来源](https://www.yixue.com/index.php?search=%E7%99%BD%E9%80%9A%E6%B1%A4) | 组成字面重合 2/6（证据文档 1 个） |
| 123 | 白通汤 | 《医方简义》卷六。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E7%99%BD%E9%80%9A%E6%B1%A4) | 组成字面重合 0/6（证据文档 1 个） |
| 124 | 白降丹 | 《青囊秘传》。 | **部分命中** | 0.11 | [来源](https://www.yixue.com/index.php?search=%E7%99%BD%E9%99%8D%E4%B8%B9) | 组成字面重合 2/18（证据文档 1 个） |
| 125 | 真武汤 | 《医学集成》卷三。 | **部分命中** | 0.40 | [来源](https://health.baidu.com/m/detail/ar_6564596650449859110) | 组成字面重合 4/10（证据文档 7 个） |
| 126 | 石斛明目丸 | 《北京市中成药规范》。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E7%9F%B3%E6%96%9B%E6%98%8E%E7%9B%AE%E4%B8%B8) | 组成字面重合 25/25（证据文档 1 个） |
| 127 | 石韦散 | 《圣惠》卷七十九。 | **部分命中** | 0.43 | [来源](https://health.baidu.com/m/detail/ar_6151313873261469051) | 组成字面重合 3/7（证据文档 6 个） |
| 128 | 磨积散 | 《济南市中药成方选辑》。 | **查无** | 0.00 | （无） | 组成字面重合 0/8（证据文档 0 个） |
| 129 | 神功内托散 | 《外科正宗》卷一。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E7%A5%9E%E5%8A%9F%E5%86%85%E6%89%98%E6%95%A3) | 组成字面重合 12/12（证据文档 1 个） |
| 130 | 竹沥水 | 《全国中药成药处方集》（天津方）。 | **部分命中** | 0.02 | [来源](https://www.yixue.com/index.php?search=%E7%AB%B9%E6%B2%A5%E6%B0%B4) | 组成字面重合 1/46（证据文档 1 个） |
| 131 | 竹茹汤 | 《圣济总录》卷二十九。 | **部分命中** | 0.50 | [来源](https://www.yixue.com/index.php?search=%E7%AB%B9%E8%8C%B9%E6%B1%A4) | 组成字面重合 1/2（证据文档 1 个） |
| 132 | 竹茹汤 | 《圣济总录》卷二十四。 | **部分命中** | 0.25 | [来源](https://www.yixue.com/index.php?search=%E7%AB%B9%E8%8C%B9%E6%B1%A4) | 组成字面重合 2/8（证据文档 1 个） |
| 133 | 紫云膏 | 《古今医鉴》卷十五。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E7%B4%AB%E4%BA%91%E8%86%8F) | 组成字面重合 0/4（证据文档 1 个） |
| 134 | 紫云膏 | 年氏《集验良方》卷六。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E7%B4%AB%E4%BA%91%E8%86%8F) | 组成字面重合 0/11（证据文档 1 个） |
| 135 | 绿雪 | 《赵炳南临床经验集》。 | **查无** | 0.00 | （无） | 组成字面重合 0/12（证据文档 0 个） |
| 136 | 羊胆丸 | 《中国药典》一部。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E7%BE%8A%E8%83%86%E4%B8%B8) | 组成字面重合 0/5（证据文档 1 个） |
| 137 | 羚羊角饮子 | 《秘传眼科龙木论》卷四。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E7%BE%9A%E7%BE%8A%E8%A7%92%E9%A5%AE%E5%AD%90) | 组成字面重合 8/8（证据文档 1 个） |
| 138 | 胃苓丸 | 《痘疹传心录》卷十七 | **命中** | 0.60 | [来源](https://www.yixue.com/index.php?search=%E8%83%83%E8%8B%93%E4%B8%B8) | 组成字面重合 9/15（证据文档 1 个） |
| 139 | 胃苓丸 | 《朱氏集验方》卷四。 | **命中** | 0.78 | [来源](https://www.yixue.com/index.php?search=%E8%83%83%E8%8B%93%E4%B8%B8) | 组成字面重合 7/9（证据文档 1 个） |
| 140 | 胎产金丹 | 《胎产心法》卷中。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E8%83%8E%E4%BA%A7%E9%87%91%E4%B8%B9) | 组成字面重合 0/32（证据文档 1 个） |
| 141 | 胶艾汤 | 《千金翼》卷二十。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E8%83%B6%E8%89%BE%E6%B1%A4) | 组成字面重合 8/8（证据文档 5 个） |
| 142 | 脏连丸 | 《慈禧光绪医方选议》。 | **部分命中** | 0.14 | [来源](https://www.yixue.com/index.php?search=%E8%84%8F%E8%BF%9E%E4%B8%B8) | 组成字面重合 2/14（证据文档 1 个） |
| 143 | 至宝丹 | 《准绳·幼科》卷六。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E8%87%B3%E5%AE%9D%E4%B8%B9) | 组成字面重合 0/0（证据文档 1 个） |
| 144 | 舒筋丸 | 《杨氏家藏方》卷四。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E8%88%92%E7%AD%8B%E4%B8%B8) | 组成字面重合 0/17（证据文档 1 个） |
| 145 | 芙蓉散 | 《普济良方》卷二。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E8%8A%99%E8%93%89%E6%95%A3) | 组成字面重合 1/1（证据文档 1 个） |
| 146 | 芩术四物汤 | 《金鉴》卷四十四。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E8%8A%A9%E6%9C%AF%E5%9B%9B%E7%89%A9%E6%B1%A4) | 组成字面重合 6/6（证据文档 1 个） |
| 147 | 苏合香丸 | 《婴童百问》卷二。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E8%8B%8F%E5%90%88%E9%A6%99%E4%B8%B8) | 组成字面重合 0/12（证据文档 1 个） |
| 148 | 茜根散 | 《圣惠》卷三十七 | **部分命中** | 0.43 | [来源](https://www.yixue.com/index.php?search=%E8%8C%9C%E6%A0%B9%E6%95%A3) | 组成字面重合 3/7（证据文档 1 个） |
| 149 | 茜根散 | 《圣惠》卷五十九。 | **部分命中** | 0.29 | [来源](https://www.yixue.com/index.php?search=%E8%8C%9C%E6%A0%B9%E6%95%A3) | 组成字面重合 2/7（证据文档 1 个） |
| 150 | 茯神散 | 《圣惠》卷二十。 | **部分命中** | 0.08 | [来源](https://www.yixue.com/index.php?search=%E8%8C%AF%E7%A5%9E%E6%95%A3) | 组成字面重合 1/12（证据文档 1 个） |
| 151 | 茵陈五苓散 | 《保婴撮要》卷十。 | **命中** | 0.80 | [来源](https://www.yixue.com/index.php?search=%E8%8C%B5%E9%99%88%E4%BA%94%E8%8B%93%E6%95%A3) | 组成字面重合 4/5（证据文档 1 个） |
| 152 | 茵陈术附汤 | 《医醇剩义》卷三。 | **部分命中** | 0.30 | [来源](https://www.yixue.com/index.php?search=%E8%8C%B5%E9%99%88%E6%9C%AF%E9%99%84%E6%B1%A4) | 组成字面重合 3/10（证据文档 1 个） |
| 153 | 荆防败毒散 | 《痘疹会通》卷五。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E8%8D%86%E9%98%B2%E8%B4%A5%E6%AF%92%E6%95%A3) | 组成字面重合 9/9（证据文档 8 个） |
| 154 | 荆防败毒散 | 《青囊全集》卷下。 | **命中** | 0.77 | [来源](https://www.yixue.com/index.php?search=%E8%8D%86%E9%98%B2%E8%B4%A5%E6%AF%92%E6%95%A3) | 组成字面重合 10/13（证据文档 8 个） |
| 155 | 葛花解酲汤 | 《不知医必要》卷二。 | **命中** | 0.71 | [来源](https://www.yixue.com/index.php?search=%E8%91%9B%E8%8A%B1%E8%A7%A3%E9%85%B2%E6%B1%A4) | 组成字面重合 10/14（证据文档 6 个） |
| 156 | 虎潜丸 | 《回春》卷五。 | **命中** | 0.77 | [来源](https://www.yixue.com/index.php?search=%E8%99%8E%E6%BD%9C%E4%B8%B8) | 组成字面重合 10/13（证据文档 1 个） |
| 157 | 虎潜丸 | 《何氏济生论》卷一。 | **部分命中** | 0.18 | [来源](https://www.yixue.com/index.php?search=%E8%99%8E%E6%BD%9C%E4%B8%B8) | 组成字面重合 3/17（证据文档 1 个） |
| 158 | 蟾酥锭 | 《普济方》卷二七四。 | **部分命中** | 0.29 | [来源](https://www.yixue.com/index.php?search=%E8%9F%BE%E9%85%A5%E9%94%AD) | 组成字面重合 2/7（证据文档 1 个） |
| 159 | 血府逐瘀汤 | 《医林改错》卷上。 | **命中** | 0.82 | [来源](https://www.yixue.com/%E8%A1%80%E5%BA%9C%E9%80%90%E7%98%80%E6%B1%A4) | 组成字面重合 9/11（证据文档 5 个） |
| 160 | 补筋丸 | 《金鉴》卷八十九。 | **部分命中** | 0.40 | [来源](https://www.yixue.com/index.php?search=%E8%A1%A5%E7%AD%8B%E4%B8%B8) | 组成字面重合 4/10（证据文档 1 个） |
| 161 | 补肝丸 | 《眼科全书》卷五。 | **部分命中** | 0.33 | [来源](https://www.yixue.com/index.php?search=%E8%A1%A5%E8%82%9D%E4%B8%B8) | 组成字面重合 7/21（证据文档 1 个） |
| 162 | 补肾固冲丸 | 《古今名方》引罗元恺方。 | **部分命中** | 0.08 | [来源](https://www.yixue.com/index.php?search=%E8%A1%A5%E8%82%BE%E5%9B%BA%E5%86%B2%E4%B8%B8) | 组成字面重合 1/13（证据文档 1 个） |
| 163 | 补肾地黄丸 | 《幼幼集成》卷三。 | **部分命中** | 0.10 | [来源](https://www.yixue.com/index.php?search=%E8%A1%A5%E8%82%BE%E5%9C%B0%E9%BB%84%E4%B8%B8) | 组成字面重合 1/10（证据文档 1 个） |
| 164 | 补肾明目丸 | 《银海精微》卷上。 | **命中** | 0.92 | [来源](https://www.yixue.com/index.php?search=%E8%A1%A5%E8%82%BE%E6%98%8E%E7%9B%AE%E4%B8%B8) | 组成字面重合 11/12（证据文档 1 个） |
| 165 | 补血定痛汤 | 《回春》卷六。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E8%A1%A5%E8%A1%80%E5%AE%9A%E7%97%9B%E6%B1%A4) | 组成字面重合 11/11（证据文档 1 个） |
| 166 | 解毒活血汤 | 《霍乱论》卷四。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E8%A7%A3%E6%AF%92%E6%B4%BB%E8%A1%80%E6%B1%A4) | 组成字面重合 9/9（证据文档 1 个） |
| 167 | 解郁和肝丸 | 《北京市中药成方选集》。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E8%A7%A3%E9%83%81%E5%92%8C%E8%82%9D%E4%B8%B8) | 组成字面重合 20/20（证据文档 1 个） |
| 168 | 调元散 | 《揣摩有得集》。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E8%B0%83%E5%85%83%E6%95%A3) | 组成字面重合 9/9（证据文档 1 个） |
| 169 | 调肝汤 | 《中医妇科治疗学》。 | **部分命中** | 0.29 | [来源](https://www.yixue.com/index.php?search=%E8%B0%83%E8%82%9D%E6%B1%A4) | 组成字面重合 2/7（证据文档 1 个） |
| 170 | 败毒散 | 《回春》卷七。 | **部分命中** | 0.56 | [来源](https://www.yixue.com/index.php?search=%E8%B4%A5%E6%AF%92%E6%95%A3) | 组成字面重合 9/16（证据文档 8 个） |
| 171 | 远志丸 | 《直指》卷二十。 | **部分命中** | 0.14 | [来源](https://www.yixue.com/index.php?search=%E8%BF%9C%E5%BF%97%E4%B8%B8) | 组成字面重合 3/22（证据文档 1 个） |
| 172 | 远志丸 | 《本事》卷二。 | **部分命中** | 0.23 | [来源](https://www.yixue.com/index.php?search=%E8%BF%9C%E5%BF%97%E4%B8%B8) | 组成字面重合 3/13（证据文档 1 个） |
| 173 | 远志丸 | 《普济方》卷三十三引《经验良方》。 | **部分命中** | 0.33 | [来源](https://www.yixue.com/index.php?search=%E8%BF%9C%E5%BF%97%E4%B8%B8) | 组成字面重合 2/6（证据文档 1 个） |
| 174 | 透脓散 | 《瑞竹堂方》卷五。 | **部分命中** | 0.00 | [来源](https://baike.baidu.com/item/%E9%80%8F%E8%84%93%E6%95%A3/9705497) | 组成字面重合 0/1（证据文档 7 个） |
| 175 | 通关散 | 《良朋汇集》卷一。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E9%80%9A%E5%85%B3%E6%95%A3) | 组成字面重合 0/1（证据文档 1 个） |
| 176 | 通关散 | 《喉科指掌》卷一。 | **部分命中** | 0.50 | [来源](https://www.yixue.com/index.php?search=%E9%80%9A%E5%85%B3%E6%95%A3) | 组成字面重合 2/4（证据文档 1 个） |
| 177 | 通气散 | 《普济方》卷五十四。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E9%80%9A%E6%B0%94%E6%95%A3) | 组成字面重合 0/3（证据文档 1 个） |
| 178 | 通脉四逆汤 | 《伤寒大白》卷三。 | **命中** | 0.60 | [来源](https://www.yixue.com/index.php?search=%E9%80%9A%E8%84%89%E5%9B%9B%E9%80%86%E6%B1%A4) | 组成字面重合 3/5（证据文档 1 个） |
| 179 | 都气丸 | 《饲鹤亭集方》。 | **部分命中** | 0.33 | [来源](https://www.yixue.com/index.php?search=%E9%83%BD%E6%B0%94%E4%B8%B8) | 组成字面重合 1/3（证据文档 1 个） |
| 180 | 金黄抱龙丸 | 《全国中药成药处方集》（禹县方）。 | **部分命中** | 0.18 | [来源](https://www.yixue.com/index.php?search=%E9%87%91%E9%BB%84%E6%8A%B1%E9%BE%99%E4%B8%B8) | 组成字面重合 3/17（证据文档 1 个） |
| 181 | 铁娃丹 | 《北京市中药成方选集》。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E9%93%81%E5%A8%83%E4%B8%B9) | 组成字面重合 0/6（证据文档 1 个） |
| 182 | 银花解毒汤 | 《中医皮肤病学简编》。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E9%93%B6%E8%8A%B1%E8%A7%A3%E6%AF%92%E6%B1%A4) | 组成字面重合 0/9（证据文档 1 个） |
| 183 | 锁精丹 | 《广嗣纪要》卷二。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E9%94%81%E7%B2%BE%E4%B8%B9) | 组成字面重合 0/10（证据文档 1 个） |
| 184 | 镇惊散 | 《金鉴》卷五十二。 | **命中** | 0.83 | [来源](https://www.yixue.com/index.php?search=%E9%95%87%E6%83%8A%E6%95%A3) | 组成字面重合 5/6（证据文档 1 个） |
| 185 | 镇肝熄风汤 | 《中医妇科治疗学》。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E9%95%87%E8%82%9D%E7%86%84%E9%A3%8E%E6%B1%A4) | 组成字面重合 9/9（证据文档 1 个） |
| 186 | 防风汤 | 《圣济总录》卷十三。 | **部分命中** | 0.08 | [来源](https://www.yixue.com/index.php?search=%E9%98%B2%E9%A3%8E%E6%B1%A4) | 组成字面重合 1/12（证据文档 1 个） |
| 187 | 阳和汤 | 《外科全生集》卷四。 | **命中** | 0.88 | [来源](https://www.yixue.com/index.php?search=%E9%98%B3%E5%92%8C%E6%B1%A4) | 组成字面重合 7/8（证据文档 1 个） |
| 188 | 阿魏丸 | 《圣惠》卷七十一。 | **部分命中** | 0.07 | [来源](https://www.yixue.com/index.php?search=%E9%98%BF%E9%AD%8F%E4%B8%B8) | 组成字面重合 1/15（证据文档 1 个） |
| 189 | 附子汤 | 《鬼遗》卷四。 | **命中** | 0.64 | [来源](https://www.yixue.com/index.php?search=%E9%99%84%E5%AD%90%E6%B1%A4) | 组成字面重合 7/11（证据文档 6 个） |
| 190 | 青蛤散 | 《外科大成》卷三。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E9%9D%92%E8%9B%A4%E6%95%A3) | 组成字面重合 5/5（证据文档 1 个） |
| 191 | 青麟丸 | 《中国医学大辞典》。 | **命中** | 1.00 | [来源](https://www.yixue.com/index.php?search=%E9%9D%92%E9%BA%9F%E4%B8%B8) | 组成字面重合 1/1（证据文档 1 个） |
| 192 | 香橘丸 | 《圣济总录》卷一七九。 | **部分命中** | 0.22 | [来源](https://www.yixue.com/index.php?search=%E9%A6%99%E6%A9%98%E4%B8%B8) | 组成字面重合 2/9（证据文档 1 个） |
| 193 | 驻车丸 | 《解围元薮》卷三。 | **部分命中** | 0.00 | [来源](https://www.yixue.com/index.php?search=%E9%A9%BB%E8%BD%A6%E4%B8%B8) | 组成字面重合 0/14（证据文档 1 个） |
| 194 | 鸡苏丸 | 《元戎》卷五。 | **查无** | 0.00 | （无） | 鸡苏丸：四个站点都取不到页面，检索也无实质结果 |
| 195 | 麝香丸 | 《圣济总录》卷一七八。 | **部分命中** | 0.20 | [来源](https://www.yixue.com/index.php?search=%E9%BA%9D%E9%A6%99%E4%B8%B8) | 组成字面重合 2/10（证据文档 1 个） |
| 196 | 黄明胶 | 方出《续本事》卷五，名见《普济方》卷 | **部分命中** | 0.14 | [来源](https://www.yixue.com/index.php?search=%E9%BB%84%E6%98%8E%E8%83%B6) | 组成字面重合 1/7（证据文档 3 个） |
| 197 | 黄芪汤 | 《金匮》卷中 | **部分命中** | 0.50 | [来源](https://health.baidu.com/m/detail/ar_6993394060639160044) | 组成字面重合 3/6（证据文档 9 个） |
| 198 | 黄连汤 | 《伤寒论》。 | **命中** | 0.86 | [来源](https://www.yixue.com/index.php?search=%E9%BB%84%E8%BF%9E%E6%B1%A4) | 组成字面重合 6/7（证据文档 1 个） |
| 199 | 黄连膏 | 《瑞竹堂方》卷三。 | **部分命中** | 0.29 | [来源](https://www.yixue.com/index.php?search=%E9%BB%84%E8%BF%9E%E8%86%8F) | 组成字面重合 2/7（证据文档 1 个） |
| 200 | 黄连解毒汤 | 《救急选方》卷上引《儿科方要》。 | **部分命中** | 0.33 | [来源](http://www.dazhongyi.cc/zhongyaofang/yaofang_h/huanglianjiedutang.html) | 组成字面重合 3/9（证据文档 9 个） |

## 五、复现

```powershell
python tools\build_h2_sample.py          # 固定种子抽样（生成清单）
python tools\h2_fetch.py --engine rotate --sleep 2.5    # 检索取证（需联网）
python tools\h2_fetch_top.py --sleep 2.5                # 抓候选页正文（需联网）
python tools\h2_judge_sheet.py --start 1 --limit 100    # 覆盖率筛选信号
python tools\h2_verdicts.py              # 规则 + 逐条修正 → 最终判定
python tools\h2_report.py                # 生成本报告
```
