# -*- coding: utf-8 -*-
r"""Christos（炼膏师）**Windows 桌面程序**入口（第七十五轮）。

做法（薄壳，不重打包 500 MB 依赖）：
  1. 在本进程里起一个本地 HTTP 服务（复用 ``ui.Handler``，只绑 127.0.0.1）；
  2. 用 **WebView2 原生窗口**（pywebview）加载这个地址 —— 不是浏览器标签页；
  3. 引擎的「跑批」仍交给用户 venv 里的 python（``CHEMREACT_PY``），
     所以 exe 只有几 MB，升级引擎不用重新打包。

打包：
    D:\TCMAI\venv\Scripts\pyinstaller.exe desktop.py --noconfirm --windowed `
        --name chemreact --add-data "ui.py;." --add-data "chemreact.py;." `
        --add-data "ui_page.html;." --hidden-import webview

直接运行（开发态）：``D:\TCMAI\venv\Scripts\python.exe desktop.py``
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FROZEN = bool(getattr(sys, "frozen", False))
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

# ★ 数据根目录：**便携式**，放在 exe 旁边（`runtime\`）。
#   为什么不放 %APPDATA%：冻结后的 exe 在那里建子目录会莫名 WinError 5（ACL 明明允许），
#   而 exe 同目录一定可写（用户自己解压的）。
DATAROOT = (Path(sys.executable).resolve().parent if FROZEN else BASE) / "runtime"

# ★ windowed 打包后 sys.stdout/stderr 是 None：print 会抛异常（exe 静默退出）。
#   这里改成写日志文件；**多级回退，且日志失败绝不拖垮程序**。
def _open_log():
    cands = [DATAROOT]
    for root in (os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA"),
                 tempfile.gettempdir()):
        if root:
            cands.append(Path(root) / "chemreact")
    for d in cands:
        try:
            d.mkdir(parents=True, exist_ok=True)
            return open(d / "app.log", "a", encoding="utf-8", buffering=1)
        except Exception:                                    # noqa: BLE001
            continue
    return None


LOG = None
LOGDIR = DATAROOT
if sys.stdout is None or sys.stderr is None:
    _fh = _open_log()
    if _fh is not None:
        LOG = getattr(_fh, "name", None)
        if sys.stdout is None:
            sys.stdout = _fh
        if sys.stderr is None:
            sys.stderr = _fh

# ★ 引擎解释器：打包后必须指向用户 venv，否则 sys.executable 会是 exe 自身
VENV_PY = r"D:\TCMAI\venv\Scripts\python.exe"
if FROZEN:
    os.environ.setdefault("CHEMREACT_PY", VENV_PY)


def free_port(preferred: int = 8765) -> int:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def main() -> int:
    print("\n==== %s 启动（frozen=%s, base=%s）===="
          % (time.strftime("%Y-%m-%d %H:%M:%S"), FROZEN, BASE))
    # ui.py 在 import 时按 __file__ 算 HERE；打包后它在 _MEIPASS 里，正好能找到
    # 我们 --add-data 带进去的 ui_page.html / chemreact.py。
    sys.path.insert(0, str(BASE))
    import ui

    # 产物目录：不要写进程序自身目录（打包后可能只读）——放到 %LOCALAPPDATA%\chemreact\out
    out_dir = DATAROOT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    ui.OUT_DIR = out_dir

    port = free_port(8765)
    ui.PORT = port
    url = "http://127.0.0.1:%d/" % port

    def serve():
        try:
            ui.main()
        except Exception:                                    # noqa: BLE001
            traceback.print_exc()

    threading.Thread(target=serve, daemon=True).start()
    for _ in range(100):                                     # 等服务起来
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)

    def edge_app(u: str) -> bool:
        r"""用 Edge 的 **app 模式**开一个独立窗口（自己的用户数据目录，**不碰用户正在用的 Edge**）。"""
        edge = (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
                r"\0C:\Program Files\Microsoft\Edge\Application\msedge.exe").split("\0")
        prof = LOGDIR / "edge-profile"
        prof.mkdir(parents=True, exist_ok=True)
        for e in edge:
            if Path(e).exists():
                try:
                    # ★ windowed 打包后 sys.stdout/stderr 是 None：不给显式句柄时
                    #   Popen 会因"无效句柄"失败（这就是之前窗口不出现的真凶）。
                    subprocess.Popen([e, "--app=%s" % u,
                                      "--user-data-dir=%s" % prof,
                                      "--window-size=1280,900",
                                      "--no-first-run", "--no-default-browser-check"],
                                     stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL,
                                     close_fds=True)
                    print("已用 Edge app 模式打开（独立 profile：%s）" % prof)
                    return True
                except Exception as ex:                      # noqa: BLE001
                    print("Edge app 启动失败：%s" % ex)
        return False

    # ★ 打包版：pythonnet 在 PyInstaller 下起不来 → 直接用 Edge 独立窗口（不再牵扯用户的 Edge）
    if FROZEN:
        if edge_app(url):
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            return 0
    try:
        import webview
        print("pywebview 可用，开原生窗口")
        webview.create_window("Christos（炼膏师） · 化学反应产物预测与药典判据溯源软件",
                              url, width=1280, height=900, min_size=(980, 700))
        webview.start()
        print("窗口已关闭，退出")
    except Exception as ex:                                  # noqa: BLE001
        # 没有 WebView2 运行时 → 退回到默认浏览器（仍然可用）
        print("[warn] 原生窗口不可用（%s: %s）→ 改用默认浏览器" % (type(ex).__name__, ex))
        traceback.print_exc()
        # 回退：Edge app 模式（独立 profile）→ 默认浏览器
        if not edge_app(url):
            import webbrowser
            webbrowser.open(url)
            print("已用默认浏览器打开")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
