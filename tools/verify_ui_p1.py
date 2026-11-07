# -*- coding: utf-8 -*-
r"""待办 1/3/4 的可判定验收：应用壳布局 + 分级查找 + 方剂版本接口。

用法：
    python tools\verify_ui_p1.py

只读检查，不启动 8765、不跑批、不写 out\。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
BRIDGE = STAGE / "integration" / "tcmai_bridge"
PAGE = BRIDGE / "ui_page.html"

sys.path.insert(0, str(BRIDGE))


def check(name: str, ok: bool, detail: str = "") -> bool:
    print("  %s  %s%s" % ("PASS" if ok else "FAIL", name,
                          ("  " + detail) if detail else ""))
    return ok


def main() -> int:
    html = PAGE.read_text(encoding="utf-8")
    ok = True

    print("== 布局（待办 3 P1） ==")
    for token, label in [
        ("class='sidebar'", "左侧栏"),
        ("data-view='predict'", "单味入口"),
        ("data-view='formula'", "方剂入口"),
        ("data-view='routes'", "找路线入口"),
        ("data-view='history'", "历史入口"),
        ("data-view='settings'", "设置入口"),
        ("id='statusPill'", "状态胶囊"),
        ("id='logWrap'", "可折叠日志"),
        ("id='results'", "结果卡"),
        ("id='fxVersions'", "方剂版本卡"),
        ("id='fxTbody'", "方剂份数表"),
    ]:
        ok &= check(label, token in html)
    ok &= check("JS 有 attachAC（边打边出）", "function attachAC" in html)
    ok &= check("JS 有 setView（应用壳切换）", "function setView" in html)
    ok &= check("JS 有 loadFormula / runFormula",
                "function loadFormula" in html and "function runFormula" in html)
    ok &= check("方剂页在单味与找路线之间",
                html.index("data-view='predict'") < html.index("data-view='formula'")
                < html.index("data-view='routes'"))
    ok &= check("无外链脚本（单文件页面）", "<script src=" not in html)

    print("== 分级查找 / 方剂接口（待办 1/4） ==")
    try:
        import chemreact as CR
        CR._bootstrap()
        import ui

        latin = ui._lookup("uralensis")
        ok &= check("uralensis 判为拉丁域", latin.get("domain") == "latin",
                    str(latin.get("domain")))
        ok &= check("uralensis 粒度为种加词",
                    latin.get("granularity") == "种加词",
                    str(latin.get("granularity")))
        coco = [t for t in (latin.get("tiers") or []) if t.get("key") == "coconut"]
        ok &= check("uralensis 有 COCONUT 档且计数 3",
                    bool(coco) and coco[0].get("count") == 3,
                    str(coco[0].get("count") if coco else None))
        ok &= check("uralensis 不再出现未收录占位",
                    not any(t.get("key") == "missing" for t in (latin.get("tiers") or [])))

        cn = ui._lookup("甘草")
        keys = [t.get("key") for t in (cn.get("tiers") or [])]
        ok &= check("甘草按来源分档（药典判据/库内/COCONUT）",
                    all(k in keys for k in ("chp", "herb", "coconut")), str(keys))

        fx = ui._lookup("生脉饮")
        ok &= check("生脉饮识别为方剂", fx.get("kind") == "formula",
                    str(fx.get("kind")))

        fdat = ui._formula("生脉饮")
        vs = fdat.get("versions") or []
        ok &= check("生脉饮返回多版本", len(vs) >= 3, str(len(vs)))
        ok &= check("首选版本为药典档", bool(vs) and vs[0].get("tier") == 0,
                    str(vs[0].get("tier") if vs else None))
        ok &= check("药典版本带法定剂量",
                    bool(vs) and bool(vs[0].get("dose_multiples")),
                    str(vs[0].get("dose_multiples") if vs else None))

        hist = ui._history(5)
        ok &= check("历史接口可读 runs.jsonl",
                    isinstance(hist.get("runs"), list), str(len(hist.get("runs") or [])))
    except Exception as ex:  # noqa: BLE001
        ok &= check("接口自检未抛异常", False, "%s: %s" % (type(ex).__name__, ex))

    print("\n%s" % ("全部通过" if ok else "有失败项"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
