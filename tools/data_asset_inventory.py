# -*- coding: utf-8 -*-
"""Inventory data assets + licence/distribution boundary (read-only). Writes JSON only."""
import hashlib, json, os, sqlite3, sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
OUT = STAGE / "reports" / "data_assets_20261019.json"

ASSETS = [
    {"id": "tcm_db", "path": r"D:\TCMAI\tcm.db", "owner": "库主(用户)", "licence": "无许可文件 / 用户自有(待书面授权)",
     "tier": "internal-only", "sha256": True, "sqlite": True},
    {"id": "coconut_db", "path": r"D:\TCMAI\coconut.db", "owner": "COCONUT 上游 (CC0)", "licence": "curated dataset CC0; 本地快照需确认版本",
     "tier": "controlled-research", "sha256": True, "sqlite": True},
    {"id": "formula_db", "path": r"D:\TCMAI\data\formula_db.json", "owner": "库主(用户爬虫库)",
     "licence": "用户自有(待书面授权)", "tier": "internal-only", "sha256": False, "sqlite": False,
     "note": "爬虫正在构建; 按工作区约定不读内容, 只记 size/mtime"},
    {"id": "chp_overlay", "path": str(STAGE / "data" / "chp_formulas.json"), "owner": "《中国药典》整理(派生)",
     "licence": "原出版方版权; 派生整理不得公开分发", "tier": "internal-only", "sha256": True, "sqlite": False},
    {"id": "demo_catalog", "path": str(STAGE / "reports" / "desktop-build" / "christos-demo" / "demo_catalog.json"),
     "owner": "Christos 派生(100味/50方 名称与映射)", "licence": "派生自 CC0 COCONUT + 用户库; 需库主授权后方可外发",
     "tier": "public-demo", "sha256": True, "sqlite": False},
    {"id": "demo_predictions", "path": str(STAGE / "reports" / "desktop-build" / "christos-demo" / "demo_predictions.json"),
     "owner": "Christos 派生(预计算产物)", "licence": "派生结果; 需库主授权", "tier": "public-demo", "sha256": True, "sqlite": False},
]

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def sqlite_info(p):
    info = {}
    try:
        c = sqlite3.connect("file:%s?mode=ro" % str(p).replace("\\", "/"), uri=True)
        tabs = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
        info["tables"] = len(tabs)
        counts = {}
        for t in tabs:
            try:
                counts[t] = c.execute('select count(*) from "%s"' % t).fetchone()[0]
            except sqlite3.Error as e:
                counts[t] = "ERR:%s" % e
        info["row_counts"] = counts
        info["journal_mode"] = c.execute("pragma journal_mode").fetchone()[0]
        c.close()
    except sqlite3.Error as e:
        info["error"] = str(e)
    return info

rows = []
for a in ASSETS:
    p = Path(a["path"])
    rec = {k: v for k, v in a.items() if k not in ("sha256", "sqlite")}
    if not p.exists():
        rec["status"] = "missing"
        rows.append(rec)
        continue
    st = p.stat()
    rec["status"] = "present"
    rec["size_bytes"] = st.st_size
    rec["mtime"] = __import__("datetime").datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    rec["sha256"] = sha256(p) if (a["sha256"] and st.st_size < 400 * 1024 * 1024) else "(skipped)"
    if a["sqlite"]:
        rec["sqlite"] = sqlite_info(p)
    rows.append(rec)

payload = {"generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "note": "只读盘点: 未修改任何数据文件; formula_db.json 未读取内容",
           "assets": rows}
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
for r in rows:
    print(r["id"], r["status"], r.get("size_bytes", "-"), (r.get("sha256") or "-")[:16],
          (r.get("sqlite", {}) or {}).get("row_counts", ""))
print("wrote", OUT)