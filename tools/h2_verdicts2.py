# -*- coding: utf-8 -*-
r"""H2 · 最终判定（口径 v2，两批同一把尺子）。

判据（可复现）—— 先算「证据文档」，再分档：

  证据文档 = ① 抓到的页面（医学百科 / A+医学百科 / 维基 / 文库 等） 或
             ② 检索结果里**不是搜索壳**（排除 so.com/link、wenku.so.com、图片搜索、
                /link?url= 这类）且**文本里出现该方名**的那一条。
  覆盖率   = 库里「组成」拆出的药材名，在证据文档文本里的字面重合比例
             （去剂量、去炮制前缀；炙甘草能对甘草，白术不会误配苍术）。

  命中     = 覆盖率 >= 0.6
  部分命中 = 覆盖率 < 0.6，但至少 1 个证据文档提到该方名（同名方在，组成/版本不同）
  查无     = 没有任何证据文档提到该方名

另加**逐条人工修正**（每条写明理由；只改「字面重合」明显算错的那种）。

用法：
  python tools\\h2_verdicts2.py --sample data\\h2_sample.json  --net reports\\_h2_net  --out data\\h2_verdicts_b1.json --batch 1
  python tools\\h2_verdicts2.py --sample data\\h2_sample2.json --net reports\\_h2_net2 --out data\\h2_verdicts_b2.json --batch 2
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "tools"))
from h2_judge_sheet import ingredients, coverage
from h2_fetch_top import real_url

# 「像方剂条目」的标记：光提名字不算，得带组成/出处这类信息才算一条**证据文档**
MARK = ("组成", "处方", "配方", "药物组成", "方名", "来源", "功效", "主治", "用法")
# 这些是**搜索页/文库页/图片页**（不是方剂条目本身）→ 不算证据文档；
# 注意 `so.com/link?m=` 是 360 的**结果跳转**（指向真实站点），要留下
SHELL = ("wenku.so.com", "image.so.com", "/link?url=", "ai.so.com/search",
         "wenda.so.com", "zhidao.baidu.com", "baidu.com/s?", "sogou.com/web?",
         "so.com/s?", "搜索", "search")

OVERRIDES = {
    1: {
        18: ("部分命中", "加味四君子汤：同名方在，但源是《直指》版（含白芍/白扁豆），本条含罂粟壳"),
        34: ("命中", "延胡索散：360百科条目组成与本条 8/12 一致（其余为炮制注记）"),
        92: ("命中", "麻子仁丸：源列出麻子仁/芍药/枳实/大黄/厚朴/杏仁 = 本条 6 味（覆盖率低是剂量字被拆坏）"),
        99: ("命中", "黄龙汤：医学百科《类证·活人书》卷十九 = 柴胡/黄芩/人参/甘草，逐字一致"),
        26: ("查无", "华盖散：只取到文库搜索壳，无证据文档（本条库内组成仅糯米）"),
        29: ("查无", "四红丹：只取到文库搜索壳"),
        31: ("查无", "定痛膏：只取到文库搜索壳"),
        33: ("查无", "小儿止泻片：只取到文库搜索壳"),
        43: ("查无", "沉香化气丸：只取到文库搜索壳"),
        58: ("查无", "生肌散：只取到图片搜索壳"),
        71: ("查无", "葛根芩连汤：本条是《赵锡武医疗经验》加味方，只取到文库搜索壳"),
        95: ("查无", "黄土汤：取到的是验证码页"),
        100: ("查无", "黑虎散：只取到图片搜索壳"),
    },
    2: {
        13: ("部分命中", "乌金丸：医学百科条目是《寿世保元》版，与本条（锦纹大黄）不同"),
        27: ("部分命中", "六味丸：按名检索有同族条目（磁石六味丸等），本条《饲鹤亭集方》版未逐字核到"),
        28: ("部分命中", "六味丸：同上，同名族存在但本版本组成未核到"),
        36: ("部分命中", "加味逍遥散：本条《得效》版（+远志/桃仁/苏木/红花）未核到；同名加味方在"),
        41: ("部分命中", "千金散：医学百科是《万病回春》版，与本条（千步峰土/食盐）不同"),
        194: ("查无", "鸡苏丸：四个站点都取不到页面，检索也无实质结果"),
    },
}


def docs_for(x: dict, net: Path) -> list:
    r"""证据文档列表。

    * 页面（医学百科 / A+ / 维基 / 文库）→ 只要提到方名就算一条；
    * 检索结果 → 文本里**同时**出现方名与「组成/处方/功效…」这类标记才算一条
      （光出现名字、没有任何方剂信息的，不算证据文档）。
    """
    out = []
    for fp in sorted(net.glob("%03d_*.json" % x["序号"])):
        d = json.loads(fp.read_text(encoding="utf-8"))
        if "page" in fp.name:
            pg = d.get("page") or {}
            if pg.get("excerpt"):
                out.append({"url": real_url(pg.get("url") or ""), "site": pg.get("site"),
                            "text": pg["excerpt"], "kind": "page"})
            continue
        for r in (d.get("results") or []):
            u = real_url(r.get("url") or "")
            blob = (r.get("title") or "") + " " + (r.get("snippet") or "")
            if any(s in u for s in SHELL):           # 搜索页/文库页/图片页 → 不是证据
                continue
            if x["方名"] in blob and any(k in blob for k in MARK):
                out.append({"url": u, "site": d.get("engine_used"), "text": blob,
                            "kind": "search"})
    for tp in sorted(net.glob("%03d_*.top.txt" % x["序号"])):
        t = tp.read_text(encoding="utf-8")
        head, _, body = t.partition("\n\n")
        if body.strip() and x["方名"] in body:
            out.append({"url": head.replace("URL: ", "").strip(), "site": "top-page",
                        "text": body, "kind": "top"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True)
    ap.add_argument("--net", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, required=True)
    a = ap.parse_args()
    net = Path(a.net)
    items = json.loads(Path(a.sample).read_text(encoding="utf-8"))["items"]
    ov = OVERRIDES.get(a.batch, {})
    rows = []
    for x in items:
        names = ingredients(x["组成"])
        docs = docs_for(x, net)
        best, best_doc = 0, None
        for d in docs:
            c = coverage(names, d["text"])[0]
            if c > best:
                best, best_doc = c, d
        cov = round(best / max(1, len(names)), 3)
        auto = ("命中" if cov >= 0.6 else "部分命中" if docs else "查无")
        verdict, why = ov.get(x["序号"], (auto, ""))
        url = (best_doc or {}).get("url") or (docs[0]["url"] if docs else "")
        rows.append({"批次": a.batch, "序号": x["序号"], "方名": x["方名"],
                     "出处": x["出处"], "判定": verdict, "自动建议": auto,
                     "覆盖率": cov, "证据文档数": len(docs), "来源URL": url,
                     "理由": why or ("组成字面重合 %d/%d（证据文档 %d 个）"
                                     % (best, len(names), len(docs)))})
    Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    c = Counter(r["判定"] for r in rows)
    print("第 %d 批（%s）：命中 %d ｜ 部分命中 %d ｜ 查无 %d ｜ 共 %d ｜ 人工修正 %d"
          % (a.batch, Path(a.sample).name, c["命中"], c["部分命中"], c["查无"],
             len(rows), sum(1 for r in rows if r["判定"] != r["自动建议"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
