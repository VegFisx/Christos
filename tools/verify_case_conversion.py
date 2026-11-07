# -*- coding: utf-8 -*-
r"""核对 H3 的转换**没有偷换分子**（护栏②的硬证据）。

对每个用例的每个分子字段：
  · 归档的手写版（reports\第七十五轮-用例DB化-存档\reaction_cases*.json）里的**原字符串**
  · 现版（tools\reaction_cases*.json）里的**引用**
逐条解析成 SMILES，取规范式比对：
  * 引用是 {"db": …} → 用只读连接从 tcm.db 取 SMILES
  * 引用是 {"lit": …} → 必须与归档里的原串**逐字相同**（库里没有的才允许留字面量）
任何一处不一致 → 打印并退出码 1。

复现：``python tools\verify_case_conversion.py``
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
sys.path.insert(0, str(STAGE / "libs"))
import case_db                                            # noqa: E402

ARCH = STAGE / "reports" / "第七十五轮-用例DB化-存档"
TOOLS = STAGE / "tools"
FILES = ("reaction_cases.json", "reaction_cases2.json")


def main() -> int:
    print("=" * 100)
    print("H3 转换核对：现版引用 vs 归档手写原值（规范 SMILES 必须相等）")
    print("=" * 100)
    bad = []
    n_db = n_lit = n_skip = 0
    for fn in FILES:
        old = {c["id"]: c for c in json.loads((ARCH / fn).read_text(encoding="utf-8"))}
        new = json.loads((TOOLS / fn).read_text(encoding="utf-8"))
        for c in new:
            o = old.get(c["id"])
            if not o:
                bad.append((fn, c["id"], "归档里找不到这条用例"))
                continue
            for field in ("smiles", "expect_any", "forbid"):
                ov, nv = o.get(field), c.get(field)
                if nv is None:
                    continue
                olist = ov if isinstance(ov, list) else ([ov] if ov else [])
                nlist = nv if isinstance(nv, list) else ([nv] if nv else [])
                if len(olist) != len(nlist):
                    bad.append((fn, c["id"], "%s 个数变了 %d → %d"
                                % (field, len(olist), len(nlist))))
                    continue
                for i, (a, b) in enumerate(zip(olist, nlist)):
                    if isinstance(a, dict) and a.get("db"):
                        n_skip += 1
                        continue                # 归档本来就是引用（重复转换）
                    if isinstance(b, dict) and b.get("db"):
                        smi = case_db.by_key(b["db"])[1]
                        n_db += 1
                    elif isinstance(b, dict) and b.get("lit"):
                        smi = b["lit"]
                        n_lit += 1
                        if smi != a:
                            bad.append((fn, "%s.%s[%d]" % (c["id"], field, i),
                                        "字面量与归档原值不同：%r ≠ %r" % (smi, a)))
                            continue
                    else:
                        bad.append((fn, "%s.%s[%d]" % (c["id"], field, i),
                                    "现版既不是 db 也不是 lit：%r" % (b,)))
                        continue
                    ca, cb = case_db.canon(a), case_db.canon(smi)
                    if not ca or not cb:
                        bad.append((fn, "%s.%s[%d]" % (c["id"], field, i),
                                    "解析失败：%r / %r" % (a, smi)))
                    elif ca != cb:
                        bad.append((fn, "%s.%s[%d]" % (c["id"], field, i),
                                    "分子变了：%s → %s" % (ca, cb)))
    print("  核对分子字段：数据库引用 %d 处 ｜ 库外字面量 %d 处（逐字相同）｜ 跳过 %d 处"
          % (n_db, n_lit, n_skip))
    if bad:
        print("  ★ 不一致 %d 处：" % len(bad))
        for x in bad[:20]:
            print("      %s ｜ %s ｜ %s" % x)
        return 1
    print("  ✓ 全部一致：引用取出来的分子与原来手写的**是同一张结构**（无一处偷换）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
