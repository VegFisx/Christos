"""发布闸门（release gate）：一次跑完"该跑的检查"，写一份可存档的成绩单。

为什么要有它：这是个会不停打补丁的系统。补丁之后必须能回答两个问题——
(1) 旧成绩有没有掉？(2) 新补丁是不是只对"我们拿来调参的那批案例"有效？

本脚本跑六项，逐项与上一份成绩单比较：

    1. safety    映射安全审计（ERROR 必须 0）
    2. holdout   预注册炮制留出集（data/holdout_paozhi.json，预期只读不写）
    3. smoke     8 个炮制/煎煮场景的产物数（必须逐项与基线一致）
    4. forward   正向基准子集召回（recall_1step）
    5. official  官方切分子集（recall_1step / top1 / mrr）
    6. multistep 逆向多步子集（depth≤N 成功率）

用法：

    python tools\\release_gate.py --profile quick
    python tools\\release_gate.py --profile quick --baseline reports/benchmarks/release-XXXX.json
    python tools\\release_gate.py --profile full --out reports/benchmarks/release-YYYY.json

退出码：0 = 全过；1 = 有硬失败（ERROR>0 / 步失败 / smoke 与基线不一致）；
        2 = 只掉软指标（相对基线超阈值）。

注意：quick 档约 10 分钟（含 8 个 smoke 场景），full 档更久。长跑请放后台。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PY = os.environ.get("CHEMREACT_PY") or sys.executable
BENCH_DIR = ROOT / "reports" / "benchmarks"
TCM_DB = os.environ.get("CHEMCREACT_TCM_DB") or "D:/TCMAI/tcm.db"

# 每档抽多少条：quick 用来日常提交前跑，full 用来发布前跑
PROFILES = {
    "quick": {"forward_n": 600, "official_n": 300, "ms_n": 50, "ms_depth": 2,
              "smoke": True, "holdout": True},
    "full": {"forward_n": 5000, "official_n": 1000, "ms_n": 150, "ms_depth": 3,
             "smoke": True, "holdout": True},
}

# 阈值：相对上一份成绩单允许的退步
THRESHOLDS = {
    "forward_recall_drop": 0.003,      # 0.3 pp
    "official_recall_drop": 0.003,
    "official_top1_drop": 0.005,
    "holdout_consistent_drop": 0,
    "multistep_rate_drop": 0.05,
}


def sh(cmd, env_extra=None, timeout=3600):
    """跑一个子进程，返回 (rc, stdout, stderr, 秒)。"""
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["CHEMCREACT_TCM_DB"] = TCM_DB
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=timeout)
        return r.returncode, r.stdout or "", r.stderr or "", time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or ""), (e.stderr or "") + "\n[timeout]", time.time() - t0


def git_rev():
    for cand in (["git"], [str(Path("D:/ProgramData/DSHNS/tools/git.cmd"))]):
        try:
            r = subprocess.run(cand + ["rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            continue
    return "unknown"


def git_dirty():
    for cand in (["git"], [str(Path("D:/ProgramData/DSHNS/tools/git.cmd"))]):
        try:
            r = subprocess.run(cand + ["status", "--porcelain", "--untracked-files=no"],
                               cwd=str(ROOT), capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                # 闸门自己会改写这两个产物：把它们排除，否则每跑一次 dirty 都加一，
                # 记录里就永远看不到「这棵树上跑出这个成绩」这件事。
                IGNORE = ("reports/benchmarks/release-", "reports/holdout_paozhi_")
                lines = [x for x in r.stdout.splitlines()
                         if x.strip() and not any(p in x for p in IGNORE)]
                return len(lines)
        except Exception:
            continue
    return -1


# ---------------- 各项检查 ----------------

def step_safety():
    rc, out, err, secs = sh([PY, "-I", "-X", "utf8", "tools/audit_mapped_safety.py"], timeout=600)
    txt = out + err
    m_err = re.search(r"\bERROR\b[^0-9]{0,10}(\d+)", txt)
    m_warn = re.search(r"\bWARN\b[^0-9]{0,10}(\d+)", txt)
    return {
        "step": "safety", "rc": rc, "seconds": round(secs, 1),
        "errors": int(m_err.group(1)) if m_err else None,
        "warnings": int(m_warn.group(1)) if m_warn else None,
        "tail": txt.strip().splitlines()[-6:],
    }


def step_holdout():
    rc, out, err, secs = sh([PY, "-I", "-X", "utf8", "tools/run_holdout_paozhi.py"], timeout=1800)
    txt = out + err
    path = ROOT / "reports" / ("holdout_paozhi_%s.json" % datetime.now().strftime("%Y%m%d"))
    d = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    cases = d.get("cases") or []
    consistent = len([c for c in cases if str(c.get("actual_status")) == "consistent"])
    return {
        "step": "holdout", "rc": rc, "seconds": round(secs, 1),
        "n_cases": len(cases), "n_consistent": consistent,
        "n_prediction_hits": d.get("n_prediction_hits"),
        "source": path.name if path.exists() else None,
        "tail": txt.strip().splitlines()[-8:],
    }


def step_smoke():
    rc, out, err, secs = sh([PY, "-I", "-X", "utf8", "tools/run_paozhi_smoke.py"], timeout=3600)
    txt = out
    counts = {}
    for line in txt.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[0] and parts[0] != "tag":
            try:
                counts[parts[0]] = int(parts[2])
            except ValueError:
                continue
    return {"step": "smoke", "rc": rc, "seconds": round(secs, 1),
            "counts": counts, "tail": (out + err).strip().splitlines()[-8:]}


def step_forward(n, workers=2):
    out_dir = BENCH_DIR / "gate_forward_tmp"
    rc, out, err, secs = sh(
        [PY, "-I", "-X", "utf8", "tools/paper_bench_50k_forward.py", str(n), str(workers)],
        env_extra={"CHEMCREACT_BENCH_OUT": str(out_dir), "CHEMCREACT_BENCH_TAG": "gate"},
        timeout=7200)
    # 输出名是 forward_50k__<TAG>.json（TAG 默认 v0，这里显式给 gate）
    f = out_dir / "forward_50k__gate.json"
    d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return {"step": "forward", "rc": rc, "seconds": round(secs, 1),
            "n": d.get("n_reactions"), "recall": d.get("recall_1step"),
            "n_errors": d.get("n_errors"),
            "tail": (out + err).strip().splitlines()[-6:]}


def step_official(n, workers=2):
    out_dir = BENCH_DIR / "gate_official_tmp"
    tag = "gate"
    rc, out, err, secs = sh(
        [PY, "-I", "-X", "utf8", "tools/paper_bench_official_test.py", str(workers)],
        env_extra={"CHEMCREACT_BENCH_OUT": str(out_dir),
                   "CHEMCREACT_BENCH_TAG": tag,
                   "CHEMCREACT_BENCH_LIMIT": str(n)}, timeout=7200)
    f = out_dir / ("forward_official_test__%s.json" % tag)
    d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return {"step": "official", "rc": rc, "seconds": round(secs, 1),
            "n": d.get("n_scored"), "recall": d.get("recall_1step"),
            "top1": d.get("top1"), "mrr": d.get("mrr"),
            "n_errors": d.get("n_errors"),
            "tail": (out + err).strip().splitlines()[-6:]}


def step_multistep(n, depth, beam=4):
    tpl = ROOT / "reports" / "paper" / "data" / "lib_uspto50k_excl_v2_freq10.jsonl"
    env = {"CHEMCREACT_MS_TAG": "gate"}
    if tpl.exists():
        env["CHEMCREACT_MS_TPL"] = str(tpl)
    rc, out, err, secs = sh(
        [PY, "-I", "-X", "utf8", "tools/bench_multistep.py", str(n), str(depth), str(beam),
         "--use-lib", "--heuristic3"], env_extra=env, timeout=7200)
    f = ROOT / "reports" / "bench_multistep__gate.json"
    d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return {"step": "multistep", "rc": rc, "seconds": round(secs, 1),
            "n": d.get("n_targets"), "rate": d.get("rate"),
            "templates": d.get("n_templates"),
            "tail": (out + err).strip().splitlines()[-6:]}


# ---------------- 判定 ----------------

def compare(res, base):
    """返回 (hard_fails, soft_fails)。没有基线时只做硬检查。"""
    hard, soft = [], []
    s = res["safety"]
    if s.get("rc") != 0:
        hard.append("safety: audit 脚本退出码 %s" % s.get("rc"))
    if s.get("errors") not in (0, None):
        hard.append("safety: ERROR=%s（必须 0）" % s.get("errors"))

    h = res["holdout"]
    if h.get("rc") != 0:
        hard.append("holdout: 退出码 %s" % h.get("rc"))

    sm = res["smoke"]
    if sm.get("rc") != 0:
        hard.append("smoke: 退出码 %s" % sm.get("rc"))
    if base:
        bcounts = (base.get("results", {}).get("smoke", {}) or {}).get("counts") or {}
        for tag, want in bcounts.items():
            got = (sm.get("counts") or {}).get(tag)
            if got != want:
                hard.append("smoke: %s 产物数 %s ≠ 基线 %s" % (tag, got, want))

    for key, label in (("forward", "forward"), ("official", "official")):
        r = res[key]
        if r.get("rc") != 0:
            hard.append("%s: 退出码 %s" % (label, r.get("rc")))
        if r.get("n_errors"):
            hard.append("%s: n_errors=%s" % (label, r.get("n_errors")))

    if base:
        b = base.get("results", {})
        bf = (b.get("forward") or {}).get("recall")
        if bf is not None and res["forward"].get("recall") is not None:
            d = bf - res["forward"]["recall"]
            if d > THRESHOLDS["forward_recall_drop"]:
                soft.append("forward: 召回 %.4f → %.4f（−%.4f 超阈值 %.4f）"
                            % (bf, res["forward"]["recall"], d, THRESHOLDS["forward_recall_drop"]))
        bo = (b.get("official") or {})
        if bo.get("recall") is not None and res["official"].get("recall") is not None:
            d = bo["recall"] - res["official"]["recall"]
            if d > THRESHOLDS["official_recall_drop"]:
                soft.append("official: 召回 %.4f → %.4f（−%.4f）"
                            % (bo["recall"], res["official"]["recall"], d))
        if bo.get("top1") is not None and res["official"].get("top1") is not None:
            d = bo["top1"] - res["official"]["top1"]
            if d > THRESHOLDS["official_top1_drop"]:
                soft.append("official: top1 %.4f → %.4f（−%.4f）"
                            % (bo["top1"], res["official"]["top1"], d))
        bh = (b.get("holdout") or {}).get("n_consistent")
        if bh is not None and h.get("n_consistent") is not None:
            if h["n_consistent"] < bh - THRESHOLDS["holdout_consistent_drop"]:
                soft.append("holdout: 结构级 %s → %s" % (bh, h["n_consistent"]))
        bm = (b.get("multistep") or {}).get("rate")
        if bm is not None and res["multistep"].get("rate") is not None:
            d = bm - res["multistep"]["rate"]
            if d > THRESHOLDS["multistep_rate_drop"]:
                soft.append("multistep: 成功率 %.3f → %.3f（−%.3f）"
                            % (bm, res["multistep"]["rate"], d))
    return hard, soft


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="quick", choices=sorted(PROFILES))
    ap.add_argument("--baseline", default="", help="上一份成绩单路径；不给则只做硬检查")
    ap.add_argument("--out", default="", help="输出路径；默认 reports/benchmarks/release-<rev>-<date>.json")
    ap.add_argument("--skip-smoke", action="store_true")
    args = ap.parse_args()
    prof = PROFILES[args.profile]

    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    rev = git_rev()
    res = {}
    print("[gate] profile=%s rev=%s dirty=%d" % (args.profile, rev, git_dirty()), flush=True)

    res["safety"] = step_safety()
    print("[gate] safety    ERROR=%s WARN=%s (%.0fs)"
          % (res["safety"].get("errors"), res["safety"].get("warnings"), res["safety"]["seconds"]), flush=True)

    if prof["holdout"]:
        res["holdout"] = step_holdout()
        print("[gate] holdout   %s/%s consistent (%.0fs)"
              % (res["holdout"].get("n_consistent"), res["holdout"].get("n_cases"),
                 res["holdout"]["seconds"]), flush=True)
    else:
        res["holdout"] = {"step": "holdout", "rc": 0, "skipped": True}

    if prof["smoke"] and not args.skip_smoke:
        res["smoke"] = step_smoke()
        print("[gate] smoke     %s (%.0fs)" % (res["smoke"].get("counts"), res["smoke"]["seconds"]), flush=True)
    else:
        res["smoke"] = {"step": "smoke", "rc": 0, "skipped": True, "counts": {}}

    res["forward"] = step_forward(prof["forward_n"])
    print("[gate] forward   n=%s recall=%s (%.0fs)"
          % (res["forward"].get("n"), res["forward"].get("recall"), res["forward"]["seconds"]), flush=True)

    res["official"] = step_official(prof["official_n"])
    print("[gate] official  n=%s recall=%s top1=%s (%.0fs)"
          % (res["official"].get("n"), res["official"].get("recall"),
             res["official"].get("top1"), res["official"]["seconds"]), flush=True)

    res["multistep"] = step_multistep(prof["ms_n"], prof["ms_depth"])
    print("[gate] multistep n=%s rate=%s (%.0fs)"
          % (res["multistep"].get("n"), res["multistep"].get("rate"),
             res["multistep"]["seconds"]), flush=True)

    base = None
    if args.baseline:
        bp = Path(args.baseline)
        if not bp.is_absolute():
            bp = ROOT / bp
        if bp.exists():
            base = json.loads(bp.read_text(encoding="utf-8"))
        else:
            print("[gate] 警告：基线文件不存在，跳过对比：%s" % bp, flush=True)

    hard, soft = compare(res, base)
    verdict = "fail" if hard else ("regress" if soft else "pass")
    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "profile": args.profile,
        "git_rev": rev,
        "git_dirty_files": git_dirty(),
        "python": sys.version.split()[0],
        "tcm_db": TCM_DB,
        "profile_params": prof,
        "thresholds": THRESHOLDS,
        "baseline": str(args.baseline) if args.baseline else None,
        "verdict": verdict,
        "hard_failures": hard,
        "soft_regressions": soft,
        "results": res,
    }
    dst = Path(args.out) if args.out else BENCH_DIR / (
        "release-%s-%s.json" % (rev, datetime.now().strftime("%Y%m%d-%H%M")))
    if not dst.is_absolute():
        dst = ROOT / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("[gate] verdict = %s" % verdict)
    for x in hard:
        print("   HARD  " + x)
    for x in soft:
        print("   SOFT  " + x)
    print("[gate] written " + str(dst))
    if hard:
        return 1
    return 2 if soft else 0


if __name__ == "__main__":
    sys.exit(main())
