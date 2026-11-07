"""Download the two public test sets the paper uses.

The derived artifacts (mined templates, retrosynthesis template libraries,
canonicalised USPTO-50k) ship with the repository. Only these two inputs are
large enough to keep out of git:

  * the official USPTO-50k test split (1.9 MB) — already shipped, but this
    script can refresh it
  * USPTO-MIT (53.8 MB) — needed only for the 480K split experiment

Raw ORD records and the herbal database (`tcm.db`) are not redistributable;
the README explains what they are used for.

Usage:
    python tools/fetch_data.py            # both
    python tools/fetch_data.py official   # 50k test split only
    python tools/fetch_data.py mit        # USPTO-MIT only
"""
import sys
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "reports" / "paper" / "data"

TARGETS = {
    "official": (
        "https://cdn.jsdelivr.net/gh/uta-smile/RetroComposer@master/data/USPTO50K/raw_test.csv",
        DATA / "uspto50k_official" / "raw_test.csv",
        1_977_289,
    ),
    "mit": (
        "https://deepchemdata.s3.us-west-1.amazonaws.com/datasets/USPTO_MIT.csv",
        DATA / "uspto_mit" / "USPTO_MIT.csv",
        56_441_634,
    ),
}


def fetch(url: str, dest: Path, expect: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == expect:
        print(f"ok (cached): {dest.relative_to(ROOT)} ({expect} bytes)")
        return
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as r, dest.open("wb") as f:
        f.write(r.read())
    got = dest.stat().st_size
    mark = "ok" if got == expect else "WARNING: size differs from the paper's run"
    print(f"{mark}: {dest.relative_to(ROOT)} ({got} bytes, expected {expect})")


def main() -> None:
    which = sys.argv[1:] or list(TARGETS)
    for name in which:
        if name not in TARGETS:
            raise SystemExit(f"unknown target {name!r}; choose from {list(TARGETS)}")
        url, dest, expect = TARGETS[name]
        fetch(url, dest, expect)


if __name__ == "__main__":
    main()
