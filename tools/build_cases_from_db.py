# -*- coding: utf-8 -*-
r"""把验收用例里的**分子数据**换成「从 tcm.db 取」（第七十五轮 H3）。

做什么
------
读**旧的手写版**用例（`tools\reaction_cases.json` / `reaction_cases2.json`），
把每个分子字面量换成数据库引用：

    {"db": "<InChIKey>", "name": "<库里名字>"}     ← 库里查得到（用 case_db 校验"同一张结构"）
    {"lit": "<SMILES>", "why": "库外（教科书级小分子）"}  ← 库里没有，如实标注、留在原处

然后**就地写出**新格式（同一个文件名），并把旧文件**原样归档**到
`reports\第七十五轮-用例DB化-存档\`（不删产物）。已经不用的历史补丁脚本
`patch_cases*.py` 一并移进存档（它们改的正是被替换掉的那版 cases.py）。

为什么不是"手写改成另一个手写"
------------------------------
引用是 **InChIKey**（分子的标准标识符，来自库里的 `compounds.inchi_key`），
运行时由 `tools\case_db.py` 用**只读**连接取 SMILES。任何一条引用在库里查不到
都会**报错**，不会静默退回字面量。转换时逐条核对"库里那一行"与"原来手写的那个分子"
的规范 SMILES 是否相等 —— 不相等就不换（并在输出里报出来）。

复现：``python tools\build_cases_from_db.py``
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
TOOLS = STAGE / "tools"
ARCHIVE = STAGE / "reports" / "第七十五轮-用例DB化-存档"
DATA = STAGE / "data"

sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(STAGE / "libs"))

import case_db                                            # noqa: E402

CASE_FILES = ("reaction_cases.json", "reaction_cases2.json")
GEN_FILES = ("cases.py", "cases2.py")
PATCH_FILES = ("patch_cases.py", "patch_cases2.py", "patch_cases3.py")


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_originals() -> list:
    """旧文件原样归档（复制）；历史补丁脚本**移动**过去（它们已失效）。"""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    moved, copied = [], []
    for fn in CASE_FILES + GEN_FILES:
        src = TOOLS / fn
        dst = ARCHIVE / fn
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            copied.append(fn)
    for fn in PATCH_FILES:
        src = TOOLS / fn
        dst = ARCHIVE / fn
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
            moved.append(fn)
    return copied, moved


def convert_value(v, log: list, cid: str, field: str):
    """字符串 → 引用 dict（库里查得到）或字面量 dict（库外）。"""
    if isinstance(v, dict):
        return v
    if not isinstance(v, str) or not v.strip():
        return v
    ref = case_db.ref_of_smiles(v)
    if ref:
        log.append(("db", cid, field, v, ref["name"], ref["db"]))
        return {"db": ref["db"], "name": ref["name"]}
    log.append(("lit", cid, field, v, "", ""))
    return {"lit": v, "why": "库外（教科书级小分子 / 引擎产物；tcm.db 里没有）"}


def main() -> int:
    copied, moved = archive_originals()
    print("=" * 100)
    print("H3 · 验收用例的分子改为「从 tcm.db 取」")
    print("=" * 100)
    print("  归档到 reports\\第七十五轮-用例DB化-存档\\：复制 %s ｜ 移动 %s"
          % (copied or "（已存在）", moved or "（已存在）"))

    out_manifest = {"schema": 1, "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "archive_dir": str(ARCHIVE), "files": {}, "counts": {},
                    "literals": [], "by_case": {}}
    for fn in CASE_FILES:
        src = (ARCHIVE / fn) if (ARCHIVE / fn).exists() else (TOOLS / fn)
        cases = json.loads(src.read_text(encoding="utf-8"))
        log: list = []
        new = []
        for c in cases:
            c2 = dict(c)
            if "smiles" in c2:
                c2["smiles"] = convert_value(c2["smiles"], log, c.get("id"), "smiles")
            for f in ("expect_any", "forbid"):
                if f in c2 and isinstance(c2[f], list):
                    c2[f] = [convert_value(v, log, c.get("id"), f) for v in c2[f]]
            new.append(c2)
        (TOOLS / fn).write_text(json.dumps(new, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        n_db = sum(1 for x in log if x[0] == "db")
        n_lit = sum(1 for x in log if x[0] == "lit")
        out_manifest["files"][fn] = {
            "old_sha256": sha256_of(src), "old_path": str(src),
            "cases": len(cases), "molecules_from_db": n_db, "molecules_literal": n_lit}
        out_manifest["counts"][fn] = {"db": n_db, "lit": n_lit}
        out_manifest["literals"] += [{"file": fn, "case": cid, "field": f, "smiles": v}
                                     for kind, cid, f, v, _n, _k in log if kind == "lit"]
        out_manifest["by_case"][fn] = {c["id"]: {
            "substrate": ("db" if isinstance(c.get("smiles"), dict) and c["smiles"].get("db")
                          else "lit" if c.get("smiles") else "-"),
            "n_expect_db": sum(1 for v in (c.get("expect_any") or [])
                               if isinstance(v, dict) and v.get("db")),
            "n_expect_lit": sum(1 for v in (c.get("expect_any") or [])
                                if isinstance(v, dict) and v.get("lit"))}
            for c in new}
        print("  %s：%d 条用例 ｜ 分子 %d 处 → 数据库引用 %d 处 ｜ 库外留字面量 %d 处"
              % (fn, len(cases), n_db + n_lit, n_db, n_lit))

    out_manifest["tcm_db"] = {"note": "运行时由 tools/case_db.py 只读解析 InChIKey"}
    (DATA / "case_sources.json").write_text(
        json.dumps(out_manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("  库外留字面量的（如实列出，不隐藏）：%d 处" % len(out_manifest["literals"]))
    for x in out_manifest["literals"][:12]:
        print("      %-22s %-24s %-10s %s"
              % (x["file"].replace("reaction_cases", "rc"), x["case"], x["field"], x["smiles"]))
    if len(out_manifest["literals"]) > 12:
        print("      … 其余见 data\\case_sources.json")
    print()
    print("  台账 -> data\\case_sources.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
