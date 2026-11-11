# -*- coding: utf-8 -*-
"""第 141 轮（审查 A2/A5/B3）的回归测试。

跑法：
    python tools\\test_audit_fixes_141.py

只读、秒级，不动数据库。
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                     # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "core"))
sys.path.insert(0, str(HERE.parent / "sources"))

import query_base as QB                                  # noqa: E402

_fail = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _fail
    print(("  [ok]   " if ok else "  [FAIL] ") + name + (("  " + detail) if detail else ""))
    if not ok:
        _fail += 1


def main() -> int:
    print("A5：分子式 vs 全大写 SMILES")
    for s in ("CCO", "CC", "CO", "CN", "C1CC1"):
        check(f"{s} 不算分子式", not QB._looks_like_formula(s))
    for s in ("C6H6", "C22H30O5", "C9H8O4", "NaCl", "CO2"):
        check(f"{s} 算分子式", QB._looks_like_formula(s))
    r = QB.resolve_molecule("CCO")
    check("CCO 解析成 SMILES", r.get("kind") == "SMILES", str(r.get("kind")))

    print("A2：条件依据分类（否定句不算降权）")
    check("「无降权」不是降权",
          QB.classify_activation("ORD 条件窗口内，无降权", 1.0) == QB.GATE_WINDOW_OK)
    check("「不降权」不是降权",
          QB.classify_activation("按高温加速处理，不降权", 1.0) == QB.GATE_WINDOW_OK)
    check("真降权（数值 0.6）判降权",
          QB.classify_activation("降权至 0.6", 0.6) == QB.GATE_PENALTY)
    check("判死（数值 0）判降权",
          QB.classify_activation("条件上判死", 0.0) == QB.GATE_PENALTY)
    check("无数据放行",
          QB.classify_activation("无 ORD 条件数据，放行", 1.0) == QB.GATE_PASS_NO_DATA)

    print("B3：别名多挂时确定地取最贴近的那个")
    import formula as F
    am = F.alias_map()
    check("别名表非空", len(am) > 10000, str(len(am)))
    check("龙胆草 → 龙胆", am.get("龙胆草") == "龙胆", str(am.get("龙胆草")))
    am2 = F.alias_map()
    check("两次调用结果一致（确定性）", am == am2)

    print("A3/A4：覆盖率计数器存在")
    import herb as H
    check("herb 暴露 LAST_COVERAGE", hasattr(H, "LAST_COVERAGE"))
    check("不再按长度过滤（源码里没有 LENGTH(c.smiles) > 3 的代码行）",
          "LENGTH(c.smiles) > 3" not in
          "\n".join(ln for ln in (HERE.parent / "sources" / "herb.py")
                    .read_text(encoding="utf-8").splitlines()
                    if not ln.lstrip().startswith("#")))

    print()
    print("失败 %d 项" % _fail)
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
