# -*- coding: utf-8 -*-
r"""
搬运预演：在【快照副本】上把新引擎装进去，逐条验证你项目的调用点
================================================================

★ 绝对不碰 D:\TCMAI

  流程：
    1. 快照 → 临时副本
    2. 把新引擎（core/conditions/rules/sources/api）拷进副本
    3. 生成一个 `tcm_analyzer` 的替代模块（保留旧 API、内部走新引擎）
    4. 逐条模拟你项目里的 7 处 predict_reactions 调用 + 其它入口
    5. 检查每个调用点的返回值结构是否满足

★ 为什么要这样做
  "方案说不会弄坏" 和 "真的不会弄坏" 是两回事。
  在副本上真跑一遍，才知道哪些调用点会出问题。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
SNAP_ROOT = STAGE / "snapshots"
WORK = STAGE / "migration-rehearsal"

TCMAI_SRC = Path(r"D:\TCMAI\src")


def latest_snapshot() -> Path:
    snaps = sorted([d for d in SNAP_ROOT.iterdir()
                    if d.is_dir() and (d / "_MANIFEST.json").exists()])
    if not snaps:
        raise SystemExit("没有可用快照")
    return snaps[-1]


def main() -> int:
    snap = latest_snapshot()
    print(f"快照: {snap.name}")
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    proj = WORK / "TCMAI"
    shutil.copytree(snap, proj)
    print(f"副本: {proj}")

    src = proj / "src"
    if not src.is_dir():
        print(f"★ 副本里没有 src/，实际: {[p.name for p in proj.iterdir()]}")
        return 2

    # ---- 1. 把新引擎装进去 ----
    # ★ 目录布局（这也是真实搬运时要用的布局）★
    #   D:\TCMAI\src\chemreact\   ← 新引擎整包放在项目自己的 src 下
    #   好处：不动原有文件的相对导入，摘掉整个目录就回到原状
    engine_dir = src / "chemreact"
    engine_dir.mkdir(exist_ok=True)
    for d in ("core", "conditions", "rules", "sources", "api"):
        s = STAGE / d
        if s.is_dir():
            shutil.copytree(s, engine_dir / d,
                            ignore=shutil.ignore_patterns("__pycache__"))
    libs = STAGE / "libs"
    if libs.is_dir():
        shutil.copytree(libs, engine_dir / "libs",
                        ignore=shutil.ignore_patterns("__pycache__"))
    print(f"引擎已装入: {engine_dir}")

    # ---- 2. 生成 tcm_analyzer 的替代模块 ----
    # 思路：保留所有旧函数名，内部转调 compat 层
    shim = textwrap.dedent('''
        # 搬运预演用的 tcm_analyzer 替代模块
        # 保留旧 API 全部名字，内部走新引擎的 compat 层
        import sys
        from pathlib import Path
        _ENGINE = Path(__file__).resolve().parent / "chemreact"
        for _d in ("api", "core", "conditions", "rules", "sources", "libs"):
            _p = _ENGINE / _d
            if _p.is_dir():
                sys.path.insert(0, str(_p))
        sys.path.insert(0, str(_ENGINE / "api"))

        from compat import (predict_reactions, find_final_products,
                            get_reactions, REACTIONS, _LAST_RXN_STATS)

        TOXIC_KEYWORDS = []       # 剥离后为空

        def check_toxicity(compound):
            return []             # 剥离后恒返回空

        def _valid_product(mol, min_mw=100, min_heavy=10):
            return True           # 新引擎在别处做过滤

        def analyze(*a, **kw):
            raise NotImplementedError("预演不覆盖 analyze")
    ''').strip() + "\n"
    (src / "_tcm_analyzer_new.py").write_text(shim, encoding="utf-8")
    print(f"已生成替代模块: src/_tcm_analyzer_new.py")

    # ---- 3. 逐条模拟调用点 ----
    driver = WORK / "drive_callsites.py"
    driver.write_text(textwrap.dedent(f'''
        import sys, json, traceback
        from pathlib import Path
        PROJ = Path(r"{proj}")
        sys.path.insert(0, str(PROJ / "src"))
        from _tcm_analyzer_new import (predict_reactions, find_final_products,
                                       get_reactions, REACTIONS, _LAST_RXN_STATS)

        OK, BAD = [], []
        def chk(name, fn):
            try:
                r = fn()
                OK.append((name, r))
                print(f"  ✓ {{name}}")
                return r
            except Exception as e:
                BAD.append((name, e))
                print(f"  ✗ {{name}}  {{type(e).__name__}}: {{str(e)[:80]}}")
                traceback.print_exc()
                return None

        print("=" * 88)
        print("模拟你项目里的调用点")
        print("=" * 88)

        # ---- 调用点 1：predict_reactions(compounds)，compounds 是 dict 列表 ----
        #   对应 plot_any_group.py:76 / plot_compare.py:69 / run_admet_products_all.py:136
        comps = [
            {{"smiles": "COC(=O)c1ccccc1", "name": "苯甲酸甲酯", "herb_name": "测试"}},
            {{"smiles": "Oc1ccc(O)cc1", "name": "对苯二酚", "herb_name": "测试"}},
            {{"smiles": "OC[C@H]1O[C@@H](Oc2ccccc2CO)[C@H](O)[C@@H](O)[C@@H]1O",
              "name": "水杨苷", "herb_name": "测试"}},
        ]
        ps = chk("predict_reactions(compounds)", lambda: predict_reactions(comps))
        if ps is not None:
            need = {{"from_herb","from_compound","rxn","formula","smiles","mw"}}
            miss = need - set(ps[0].keys()) if ps else set()
            if miss:
                print(f"    ★ 返回缺键: {{miss}}")
                BAD.append(("返回结构", miss))
            else:
                print(f"    ✓ 返回 {{len(ps)}} 个产物，六个旧键齐全")

        # ---- 调用点 2：frontier 格式（cascade_reactions.py:57 用的就是这种）----
        frontier = [{{"smiles": "CC(=O)Oc1ccccc1", "name": "R2 底物",
                      "source": "cascade", "herb_name": "cascade"}}]
        chk("predict_reactions(frontier)  frontier 带 source/herb_name",
            lambda: predict_reactions(frontier))

        # ---- 调用点 3：tuple 形式 (herb, name, smi) ----
        chk("predict_reactions(tuple 形式)",
            lambda: predict_reactions([("甘草", "甘草酸", "CC(C)=O")]))

        # ---- 调用点 4：rule_limits 参数（旧版有）----
        chk("predict_reactions(..., rule_limits={{}})",
            lambda: predict_reactions(comps, rule_limits={{"酯水解": 1}}))

        # ---- 调用点 5：get_reactions()（cascade_reactions._irreversible_rules 用）----
        rxn = chk("get_reactions()", get_reactions)
        if rxn:
            one = next(iter(rxn.values()))
            need = {{"name","rxn","desc","irreversible"}}
            miss = need - set(one.keys())
            if miss:
                print(f"    ★ 缺键: {{miss}}")
                BAD.append(("get_reactions 结构", miss))
            else:
                print(f"    ✓ {{len(rxn)}} 条，旧四键齐全；"
                      f"irreversible 可筛出 "
                      f"{{sum(1 for v in rxn.values() if v['irreversible'])}} 条")

        # ---- 调用点 6：REACTIONS 模块级 dict ----
        chk("REACTIONS dict", lambda: (len(REACTIONS), next(iter(REACTIONS.values()))))

        # ---- 调用点 7：_LAST_RXN_STATS 原地更新 ----
        def stat_check():
            before = id(_LAST_RXN_STATS)
            predict_reactions(comps)
            assert id(_LAST_RXN_STATS) == before, "对象被重新赋值了！外部引用会失效"
            assert len(_LAST_RXN_STATS) > 0, "统计为空"
            return len(_LAST_RXN_STATS)
        chk("_LAST_RXN_STATS 原地更新", stat_check)

        # ---- 调用点 8：find_final_products（llm_agent.py:409）----
        res = chk("find_final_products(uniq, max_rounds=3)",
                  lambda: find_final_products(comps, max_rounds=3, min_new=5))
        if res:
            need = {{"products","total","rounds","round_stats","converged","by_round"}}
            miss = need - set(res.keys())
            if miss:
                print(f"    ★ 缺键: {{miss}}")
                BAD.append(("find_final_products 结构", miss))
            else:
                print(f"    ✓ {{res['total']}} 个产物，{{res['rounds']}} 轮，"
                      f"收敛={{res['converged']}}，旧六键齐全")

        # ---- 调用点 9：旧产物过滤器对比 ----
        def filter_check():
            keep = predict_reactions(comps)
            legacy = predict_reactions(comps, legacy_filter=True)
            return len(keep), len(legacy)
        chk("legacy_filter 开关（对比误杀）", filter_check)

        print()
        print("=" * 88)
        print(f"结果：{{len(OK)}} 通过 / {{len(BAD)}} 失败")
        for n, e in BAD:
            print(f"  ✗ {{n}}: {{e}}")
        print("=" * 88)
    '''), encoding="utf-8")

    print("\n" + "=" * 88)
    print("在副本上跑调用点验证")
    print("=" * 88)
    py = str(Path(r"D:\TCMAI\venv\Scripts\python.exe"))
    r = subprocess.run([py, "-X", "utf8", str(driver)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    print(r.stdout)
    if r.stderr.strip():
        print("--- stderr ---")
        print(r.stderr[-2000:])

    print(f"\n副本保留在 {WORK}")
    print("D:\\TCMAI 一个字节都没动。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
