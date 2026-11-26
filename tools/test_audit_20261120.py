# -*- coding: utf-8 -*-
"""2026-11-20 代码审计修复的回归测试。

覆盖：
  A 台账 sidecar 命名（不再用字符串 replace，避免 meta 覆盖 CSV）
  B dump_inventory 原子写 + meta 独立文件
  C 压力参数校验（0/负/nan 必须报错）
  D 无效压力不做沸点截断（不崩、不静默当成 1 atm）
  E extent=0 只降权、不判零（time_min=0 时 activation 仍 > 0）
  F 静态不变量：失败计数进 stats、_mined_smarts 每步清空、
    herb 不再 zip(out, id_list)、daemon 进程池保护
  G cmd_routes 定义了 t0
"""
from __future__ import annotations

import ast
import io
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

fails = []


def check(name, ok, detail=""):
    print("  %s %s %s" % ("[ok] " if ok else "[FAIL]", name, detail))
    if not ok:
        fails.append(name)


def main() -> int:
    import query_base as qb
    import pressure as P

    print("A 台账 sidecar 命名")
    check("a.csv -> a.meta.json",
          qb._sidecar("a.csv", ".meta.json") == Path("a.meta.json"))
    check("a.tsv -> a.meta.json",
          qb._sidecar("a.tsv", ".meta.json") == Path("a.meta.json"))
    check("无后缀 -> a.meta.json",
          qb._sidecar("a", ".meta.json") == Path("a.meta.json"))
    check("sidecar 不等于台账本身",
          qb._sidecar("ledger.tsv", ".meta.json") != Path("ledger.tsv"))

    print("B dump_inventory 原子写")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        inv = qb.Inventory(spec=qb.RunSpec(seeds=[]))
        inv.built_at = "2026-11-20 00:00:00"
        qb.dump_inventory(inv, d / "a.csv", d / "a.tsv")
        check("CSV 存在", (d / "a.csv").exists())
        check("meta 独立且为 JSON", (d / "a.meta.json").exists()
              and (d / "a.meta.json").read_text(encoding="utf-8").startswith("{"))
        check("没有残留 .tmp", not list(d.glob("*.tmp")))
        back = qb.load_inventory(d / "a.csv")
        check("读回不崩且 0 行", len(back.paths) == 0)

    print("C 压力参数校验")
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        try:
            qb.RunSpec(seeds=[], pressure_atm=bad).cond()
            check("拒绝 %r" % bad, False)
        except ValueError:
            check("拒绝 %r" % bad, True)
    c = qb.RunSpec(seeds=[], pressure_atm=2.5).cond()
    check("有效压力 2.5 保留", abs(float(c.pressure_atm) - 2.5) < 1e-9,
          str(c.pressure_atm))

    print("D 无效压力不截断")
    import templates as T
    cond = replace(T.get_template("煎煮"), temperature=150.0,
                   pressure_atm=0.0, solvent="water")
    t_eff, why = P.effective_temperature(cond)
    check("压力 0 不崩且不截断", abs(t_eff - 150.0) < 1e-6, "%.1f %s" % (t_eff, why))

    print("E extent=0 只降权、不判零")
    try:
        import smartreact_engine as SE
        eng = SE.SmartReactEngine(condition_extent=True)
        table = getattr(eng, "mined_top_cond_table", {}) or getattr(eng, "cond_table", {})
        rule = next(iter(table), None)
        if rule is None:
            check("找到带条件窗口的规则", False, "表为空，跳过")
        else:
            import extent as _extent
            c2 = replace(T.get_template("煎煮"), time_min=0.0)
            prm = _extent.load_params()
            picked, e_pick = None, None
            for r in list(table.keys())[:80]:
                entry = (table.get(r) or getattr(eng, "curated_cond_table", {}).get(r)
                         or getattr(eng, "cond_table", {}).get(r))
                if not entry:
                    continue
                try:
                    e_val, _why = _extent.extent_from_table(entry, c2, prm)
                except Exception:
                    continue
                if e_val < 0.632:
                    picked, e_pick = r, e_val
                    break
            if picked is None:
                check("找到 e<0.632 的规则", False, "未找到，无法验证下限")
            else:
                act, why = eng.cond_activation(picked, c2)
                check("time_min=0 时 activation > 0", act > 0.0,
                      "rule=%s e=%.3f act=%.3f" % (picked, e_pick, act))
    except Exception as ex:                            # noqa: BLE001
        check("extent 测试可运行", False, "%s: %s" % (type(ex).__name__, ex))

    print("F 静态不变量")
    se_txt = io.open(ROOT / "core" / "smartreact_engine.py", encoding="utf-8").read()
    check("失败计数进 stats", '"enumerate_batch_failures": self._enum_fail_step' in se_txt)
    check("_mined_smarts 每步清空", "self._mined_smarts.clear()" in se_txt)
    check("立体枚举层已接线",
          "stereo_enum_cap" in se_txt and "立体未指定，枚举变体" in se_txt)
    herb_txt = io.open(ROOT / "sources" / "herb.py", encoding="utf-8").read()
    check("herb 不再 zip(out, id_list)", "for c, iid in zip(out, id_list)" not in herb_txt)
    qb_txt = io.open(ROOT / "core" / "query_base.py", encoding="utf-8").read()
    check("daemon 进程池保护", "_in_daemon" in qb_txt)

    print("G cmd_routes 定义 t0")
    src = io.open(ROOT / "integration" / "tcmai_bridge" / "chemreact.py",
                  encoding="utf-8").read()
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "cmd_routes"), None)
    has_t0 = False
    if fn is not None:
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "t0" for t in node.targets):
                has_t0 = True
    check("cmd_routes 内赋值 t0", has_t0)

    print("H 第二批审计修复（2026-11-20 第二轮）")
    import os
    sys.path.insert(0, str(ROOT / "integration" / "tcmai_bridge"))
    import ui as UI
    check("_safe_name 保留空格", UI._safe_name("甘草 煎煮.html") == "甘草 煎煮.html")
    check("_safe_name 保留加号", UI._safe_name("A+B.tsv") == "A+B.tsv")
    check("_safe_name 拦目录穿越", UI._safe_name("../x.html") == "")
    check("_safe_name 拦分隔符", UI._safe_name("a/b.html") == ""
          and UI._safe_name("a\\b.html") == "")
    check("_safe_name 空名", UI._safe_name("") == "")

    old_out = UI.OUT_DIR
    try:
        UI.OUT_DIR = Path(tempfile.gettempdir()) / "ui-out-test"
        env = UI._engine_env()
        check("_engine_env 指向 OUT_DIR",
              env.get("CHEMCREACT_RUNS_DIR") == str(UI.OUT_DIR))
    finally:
        UI.OUT_DIR = old_out

    import chemreact as CR
    check("_runs_dir 默认 HERE/out", CR._runs_dir() == CR.HERE / "out")
    os.environ["CHEMCREACT_RUNS_DIR"] = str(Path(tempfile.gettempdir()) / "runs-x")
    try:
        check("_runs_dir 认环境变量",
              CR._runs_dir() == Path(tempfile.gettempdir()) / "runs-x")
    finally:
        os.environ.pop("CHEMCREACT_RUNS_DIR", None)
    cr_txt = io.open(ROOT / "integration" / "tcmai_bridge" / "chemreact.py",
                     encoding="utf-8").read()
    check("cmd_history 走 _runs_dir", 'p = _runs_dir() / "runs.jsonl"' in cr_txt)
    check("choice_window 文件名已清洗", "qtag = re.sub(" in cr_txt)

    co_txt = io.open(ROOT / "sources" / "coconut.py", encoding="utf-8").read()
    check("COCONUT 不再按长度丢短 SMILES",
          "AND LENGTH(c.smiles) > 3" not in co_txt)

    check("categories 空列表不再 IndexError",
          '.get("categories") or [""]' in se_txt)

    inv2 = qb.Inventory(spec=qb.RunSpec(seeds=[]))
    inv2.paths.append({"product_smiles": "CCO", "product_inchikey": "",
                       "formula": "C2H6O", "mw": 46.0, "heavy_atoms": 3,
                       "score": "", "is_byproduct": "False", "reversible": "False",
                       "co_products": "", "source_smiles": "CCO",
                       "source_name": "", "source_herb": "", "rule_name": "r",
                       "round": 1, "seq": 7, "direction_cn": "",
                       "direction_reason": "", "activation_why": ""})
    ent0 = next(iter(inv2.index().values()))["sources"]["CCO"]["paths"][0]
    check("Inventory.index 带 seq", ent0.get("seq") == 7, repr(ent0.get("seq")))

    with tempfile.TemporaryDirectory() as td:
        pth = Path(td) / "ik.json"
        qb.save_ik_cache({"CCO": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"}, pth)
        ok = pth.is_file() and not list(Path(td).glob("*.tmp"))
        check("IK 缓存原子写且无残留 .tmp", ok)
        check("IK 缓存内容可读回",
              qb.load_ik_cache(pth).get("CCO") == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N")

    mem = {}
    for i in range(5):
        qb._mem_put(mem, i, i, cap=3)
    check("_mem_put 有界", len(mem) == 3 and 0 not in mem and 4 in mem, repr(sorted(mem)))

    qb._NAMES_MEM.clear()
    qb._NAMES_SCAN = {"IK": [{"db": "x", "name": "a", "extra": ""},
                             {"db": "x", "name": "b", "extra": ""}]}
    orig_tcm = qb._tcm_names_by_ik
    qb._tcm_names_by_ik = lambda ik, n: []          # noqa: ARG005
    try:
        one = qb.names_of_inchikey("IK", limit=1)
        two = qb.names_of_inchikey("IK", limit=2)
    finally:
        qb._tcm_names_by_ik = orig_tcm
        qb._NAMES_SCAN = None
        qb._NAMES_MEM.clear()
    check("名称缓存不再按首次 limit 固化", len(one) == 1 and len(two) == 2,
          "%d/%d" % (len(one), len(two)))

    print("\n失败 %d 项" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
