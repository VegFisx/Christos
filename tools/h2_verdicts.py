# -*- coding: utf-8 -*-
r"""H2 · 把筛选信号 + **逐条阅读后的修正**合成最终判定（命中 / 部分命中 / 查无）。

规则（先定死）：
  1. 默认：覆盖率 ≥ 0.6 → **命中**；0 < 覆盖率 < 0.6 → **部分命中**；= 0 → **查无**。
  2. 覆盖率只是"组成字面重合"，会漏判/误判 —— 所以允许**逐条修正**，
     每条修正都必须写明理由（见 OVERRIDES），并保留原始覆盖率。

输出：``data\h2_verdicts.json``（每条：判定 / 覆盖率 / 来源 URL / 理由）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "tools"))
from h2_fetch_top import real_url                          # noqa: E402

SCREEN = STAGE / "data" / "h2_screen.json"
OUT = STAGE / "data" / "h2_verdicts.json"
NET = STAGE / "reports" / "_h2_net"
PAGES = STAGE / "data" / "h2_pages.json"

# ★ 逐条阅读后的修正（序号: (判定, 理由)）—— 只改"字面重合"算错的那种
OVERRIDES = {
    3: ("命中", "五苓散：源组成茯苓/猪苓/泽泻/肉桂/炒白术，与本条（泽泻/白术/赤茯苓/猪苓/肉桂/姜/枣）一致"),
    4: ("命中", "五苓散《金鉴》版：源 5/6 一致，差异仅小茴香（该版本加味）"),
    16: ("命中", "凉膈散：源（医学百科）黄芩/黄连/栀仁/连翘/桔梗/甘草/薄荷与本条基本一致"),
    18: ("部分命中", "加味四君子汤：同名方存在，但源是《直指》版（含白芍/白扁豆），本条含罂粟壳"),
    34: ("命中", "延胡索散：360百科条目组成与本条 8/12 一致（其余为炮制注记）"),
    37: ("命中", "木香分气丸：360百科条目组成与本条 10/13 一致"),
    53: ("命中", "犀角化毒丹：360百科条目组成 11/11 全中"),
    57: ("命中", "理中丸：人参/白术/干姜/甘草 4/4 一致"),
    62: ("命中", "益阴汤：39药品通条目组成 11/11 逐字一致"),
    68: ("命中", "肥儿丸：源（健客）肉豆蔻/木香/神曲/麦芽/黄连/槟榔/使君子与本条 8/9 一致"),
    70: ("命中", "菊花茶调散：医学百科条目，组成（菊花/僵蚕）与本条一致"),
    81: ("命中", "通塞脉片：医学百科条目存在，当归/玄参/牛膝/甘草 3/4（本条原文即写'等'）"),
    88: ("命中", "香砂六君子汤：源组成 8/8 逐字一致"),
    89: ("命中", "香砂枳术丸：360百科条目（木香/枳实/砂仁/白术）与本条 4/5 一致"),
    92: ("命中", "麻子仁丸：源（家庭医生）麻子仁/芍药/枳实/大黄/厚朴/杏仁 = 本条 6 味（覆盖率低是剂量字被拆坏所致）"),
    98: ("命中", "黄连上清丸：源（家庭医生）中成药组成与本条 9/15 一致（差异为版本/炮制）"),
    99: ("命中", "黄龙汤：医学百科《类证·活人书》卷十九 = 柴胡/黄芩/人参/甘草，与本条逐字一致"),
    84: ("部分命中", "附子理中汤：源为经典 5 味版，本条是《镐京直指》加味版（含肉果/茯苓）"),
    87: ("部分命中", "香棱丸：源（360百科）为《丹溪心法》版，与本条《杏苑》版组成不同"),
    93: ("部分命中", "麻杏石甘汤：源是经典 4 味版，本条是《喉痧症治概要》12 味加味方"),
    96: ("部分命中", "黄精丸：源（医学百科）主成分为黄精，本条为黄精/天门冬/白蜜，未逐字对上"),
    26: ("查无", "华盖散：只取到文库搜索页，无任何实质条目（本条库内组成仅'糯米'，无法互证）"),
    29: ("查无", "四红丹：只取到文库搜索页，无实质条目"),
    31: ("查无", "定痛膏：只取到文库搜索页，无实质条目"),
    33: ("查无", "小儿止泻片：只取到文库搜索页，无实质条目"),
    43: ("查无", "沉香化气丸：只取到文库搜索页，无实质条目"),
    51: ("查无", "清暑汤：只取到与方名无关的科普页，未找到该条组成"),
    58: ("查无", "生肌散：只取到图片搜索页，无实质条目"),
    71: ("查无", "葛根芩连汤：本条为《赵锡武医疗经验》9 味加味方，只取到文库搜索页，无法核对"),
    82: ("查无", "通气散：只取到文库搜索页，无实质条目"),
    95: ("查无", "黄土汤：取到的是验证码页，无法核对"),
    100: ("查无", "黑虎散：只取到图片搜索页，无实质条目"),
}


def main() -> int:
    screen = {x["序号"]: x for x in json.loads(SCREEN.read_text(encoding="utf-8"))}
    pages = json.loads(PAGES.read_text(encoding="utf-8")) if PAGES.exists() else {}
    rows = []
    for n in sorted(screen):
        x = screen[n]
        cov = x["覆盖率"]
        auto = ("命中" if cov >= 0.6 else "部分命中" if x["最佳命中"] > 0 else "查无")
        verdict, why = OVERRIDES.get(n, (auto, ""))
        # 来源链接：最佳来源 → 抓过的页面 → 第一条检索结果 → 搜过的检索页
        url = real_url(x.get("最佳来源") or "")
        if not url.startswith("http"):
            pg = (pages.get(str(n)) or {}).get("url") or ""
            url = real_url(pg)
        if not url.startswith("http"):
            for fp in sorted(NET.glob("%03d_*.json" % n)):
                d = json.loads(fp.read_text(encoding="utf-8"))
                if "page" in fp.name:
                    u = (d.get("page") or {}).get("url") or ""
                else:
                    u = d.get("url") or ""
                    if not u:
                        rs = d.get("results") or []
                        u = (rs[0] or {}).get("url") if rs else ""
                url = real_url(u)
                if url.startswith("http"):
                    break
        if url.startswith("http") and ("duckduckgo.com" in url or "so.com/link" in url):
            pass
        rows.append({"序号": n, "方名": x["方名"], "出处": x["出处"],
                     "判定": verdict, "覆盖率": cov, "自动建议": auto,
                     "来源URL": url,
                     "理由": why or ("组成字面重合 %d/%d" % (x["最佳命中"], x["药材数"]))})
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    c = Counter(r["判定"] for r in rows)
    n = len(rows)
    print("=" * 100)
    print("H2 判定汇总（100 条固定种子抽样）")
    print("=" * 100)
    for k in ("命中", "部分命中", "查无"):
        print("  %-6s %3d 条（%.1f%%）" % (k, c[k], 100.0 * c[k] / n))
    print("  自动建议分布：", dict(Counter(r["自动建议"] for r in rows)))
    print("  人工修正 %d 条" % sum(1 for r in rows if r["判定"] != r["自动建议"]))
    print()
    print("  修正明细：")
    for r in rows:
        if r["判定"] != r["自动建议"]:
            print("    #%03d %-10s 自动=%s → 判定=%s ｜ %s"
                  % (r["序号"], r["方名"][:10], r["自动建议"], r["判定"], r["理由"][:60]))
    print()
    print("  -> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
