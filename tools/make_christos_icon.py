# -*- coding: utf-8 -*-
r"""把豆包生成的 Christos 丹炉图做成可用的软件图标原型。

步骤：
  * 裁掉底部“豆包AI生成”水印；
  * 去白底（flood fill + 轻量 alpha matte）；
  * 生成透明主标、圆形徽章、多尺寸 .ico；
  * 生成浅色/深色背景的大小预览。

只读源图；输出到 `reports/brand/christos_logo/`。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
SRC = Path(os.environ.get("CHRISTOS_ICON_SRC")
           or r"C:/Users/Vegfish/AppData/Local/Temp/codex-clipboard-d3e4627a-3f41-4b1f-a478-01a554927bdb.png")
OUT = STAGE / "reports" / "brand" / "christos_logo"


def content_bbox(im: Image.Image):
    """排除右下角水印后的内容边界。"""
    px = im.load()
    w, h = im.size
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            if x > 1600 and y > 1800:
                continue
            r, g, b = px[x, y]
            if min(r, g, b) < 235 or max(r, g, b) - min(r, g, b) > 18:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def transparent_mark(im: Image.Image, box) -> Image.Image:
    rgb = im.crop(box).convert("RGB")
    w, h = rgb.size
    filled = rgb.copy()
    # 从四角把连通的近白背景填成洋红
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        ImageDraw.floodfill(filled, seed, (255, 0, 255), thresh=28)
    out = rgb.convert("RGBA")
    alpha = Image.new("L", (w, h), 255)
    p_src, p_fill, p_a = rgb.load(), filled.load(), alpha.load()
    for y in range(h):
        for x in range(w):
            r, g, b = p_src[x, y]
            if p_fill[x, y] == (255, 0, 255):
                p_a[x, y] = 0
                continue
            mn, mx = min(r, g, b), max(r, g, b)
            if mn > 242 and mx - mn < 18:
                p_a[x, y] = 0
            elif mn > 225 and mx - mn < 18:
                p_a[x, y] = int((242 - mn) / 17.0 * 120)
            else:
                p_a[x, y] = 255
    out.putalpha(alpha)
    # 贴紧后再留一点透明边
    bbox = out.getbbox()
    if bbox:
        out = out.crop(bbox)
    return out


def fit_on_square(mark: Image.Image, size: int = 1024, fill: float = 0.82) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mw, mh = mark.size
    scale = min(size * fill / mw, size * fill / mh)
    nw, nh = max(1, int(mw * scale)), max(1, int(mh * scale))
    m = mark.resize((nw, nh), Image.LANCZOS)
    canvas.alpha_composite(m, ((size - nw) // 2, (size - nh) // 2))
    return canvas


def make_badge(mark: Image.Image, size: int = 1024) -> Image.Image:
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(badge)
    m = 28
    d.ellipse((m, m, size - m, size - m), fill=(11, 18, 32, 255),
              outline=(201, 162, 39, 255), width=20)
    d.ellipse((m + 28, m + 28, size - m - 28, size - m - 28),
              outline=(45, 60, 80, 255), width=6)
    # 主标放进圆内，留出金色边
    mw, mh = mark.size
    fill = 0.74
    scale = min(size * fill / mw, size * fill / mh)
    nw, nh = max(1, int(mw * scale)), max(1, int(mh * scale))
    mm = mark.resize((nw, nh), Image.LANCZOS)
    badge.alpha_composite(mm, ((size - nw) // 2, (size - nh) // 2 + 8))
    return badge


def simple_icon(size: int = 2048) -> Image.Image:
    """小尺寸友好：粗金线丹炉 + 一个分子环 + 短数据流。"""
    S = size / 1024.0
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    def L(xy, fill, w):
        d.line([(int(x * S), int(y * S)) for x, y in xy],
               fill=fill, width=max(2, int(w * S)), joint="curve")
    def E(box, outline, w, fill=None):
        d.ellipse(tuple(int(v * S) for v in box), outline=outline,
                  width=max(2, int(w * S)), fill=fill)
    NAVY = (11, 18, 32, 255)
    GOLD = (201, 162, 39, 255)
    CYAN = (57, 208, 216, 255)
    RED = (226, 59, 59, 255)
    INK = (20, 30, 48, 255)
    # 圆底 + 金边
    E((28, 28, 996, 996), GOLD, 22, NAVY)
    E((62, 62, 962, 962), (45, 60, 80, 255), 6)
    # 炉盖 / 炉身 / 三足
    L([(244, 424), (780, 424)], GOLD, 26)
    L([(300, 392), (724, 392)], GOLD, 18)
    L([(330, 452), (694, 452)], GOLD, 12)
    d.polygon([(330 * S, 470 * S), (694 * S, 470 * S),
               (650 * S, 700 * S), (374 * S, 700 * S)], fill=INK)
    L([(330, 470), (374, 700), (650, 700), (694, 470)], GOLD, 24)
    # 双耳
    L([(330, 500), (272, 548), (300, 610)], GOLD, 18)
    L([(694, 500), (752, 548), (724, 610)], GOLD, 18)
    # 三足 + 底座
    L([(410, 700), (380, 802)], GOLD, 22)
    L([(512, 700), (512, 802)], GOLD, 22)
    L([(614, 700), (644, 802)], GOLD, 22)
    L([(350, 814), (674, 814)], GOLD, 24)
    # 炉腹分子环
    cx, cy, r = 512, 585, 82
    nodes = []
    import math
    for k in range(6):
        a = math.radians(-90 + k * 60)
        nodes.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    for i in range(6):
        L([nodes[i], nodes[(i + 1) % 6]], CYAN, 8)
        col = RED if i in (2, 5) else (GOLD if i == 0 else CYAN)
        E((nodes[i][0] - 12, nodes[i][1] - 12,
           nodes[i][0] + 12, nodes[i][1] + 12), col, 2, col)
    E((cx - 18, cy - 18, cx + 18, cy + 18), GOLD, 3, GOLD)
    # 短数据流
    L([(512, 452), (512, 300)], CYAN, 12)
    L([(512, 360), (430, 320)], CYAN, 7)
    L([(512, 360), (594, 320)], CYAN, 7)
    E((424, 314, 436, 326), CYAN, 1, CYAN)
    E((588, 314, 600, 326), CYAN, 1, CYAN)
    return im


def preview(icon: Image.Image, out: Path) -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    W, H = 1200, 760
    im = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(im)
    d.rectangle((0, H // 2, W, H), fill=(17, 24, 39))
    x = 20
    for s in sizes:
        ic = icon.resize((s, s), Image.LANCZOS)
        y1 = H // 4 - s // 2
        y2 = H * 3 // 4 - s // 2
        im.paste(ic, (x, y1), ic)
        im.paste(ic, (x, y2), ic)
        d.text((x, 10), str(s), fill=(30, 30, 30))
        d.text((x, H // 2 + 10), str(s), fill=(220, 220, 220))
        x += max(80, s + 40)
    im.save(out)


def main() -> int:
    if not SRC.exists():
        print("源图不存在：%s" % SRC)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    im = Image.open(SRC).convert("RGB")
    im.save(OUT / "source_doubao.png")
    box = content_bbox(im)
    pad = 50
    box = (max(0, box[0] - pad), max(0, box[1] - pad),
           min(im.width, box[2] + pad), min(im.height, box[3] + pad))
    mark = transparent_mark(im, box)
    mark_full = fit_on_square(mark, 1024, 0.88)
    mark_full.save(OUT / "christos_mark_transparent.png")
    badge = make_badge(mark, 1024)
    badge.save(OUT / "christos_icon_badge.png")
    simple = simple_icon(2048)
    simple.resize((1024, 1024), Image.LANCZOS).save(OUT / "christos_icon_simple.png")
    # ICO：小尺寸简化版优先，另留徽章版
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48),
                 (64, 64), (128, 128), (256, 256)]
    simple.save(OUT / "christos.ico", format="ICO", sizes=ico_sizes)
    badge.save(OUT / "christos_badge.ico", format="ICO", sizes=ico_sizes)
    mark_full.save(OUT / "christos_mark.ico", format="ICO", sizes=ico_sizes)
    preview(simple, OUT / "icon_preview_simple.png")
    preview(badge, OUT / "icon_preview.png")
    (OUT / "README-图标说明.md").write_text(
        "# Christos（炼膏师）图标原型\n\n"
        "* `christos.ico`：**简化版**多尺寸图标，建议用于桌面快捷方式/exe（16–32px 更清楚）。\n"
        "* `christos_badge.ico`：细节徽章版多尺寸图标，适合 48px 以上/关于页。\n"
        "* `christos_icon_simple.png`：简化版 1024 预览。\n"
        "* `christos_icon_badge.png`：1024 徽章版，用于安装器/关于页。\n"
        "* `christos_mark_transparent.png`：透明主标，用于启动页/报告封面。\n"
        "* `icon_preview_simple.png` / `icon_preview.png`：简化版/徽章版的大小预览。\n\n"
        "水印已裁掉；豆包生成内容的商用/署名条款请自行确认。\n",
        encoding="utf-8")
    print("-> %s" % OUT)
    print("  源图 %s；内容框 %s；透明标 %s" % (im.size, box, mark.size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
