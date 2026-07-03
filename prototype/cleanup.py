# prototype/cleanup.py — 孤儿进程清理
# 用法: 在实验脚本开头 `import prototype.cleanup`
# 自动注册 atexit handler，确保无论什么方式退出，子进程都被回收。
#
# 也支持手动调用: python -m prototype.cleanup

import atexit, os, signal, sys, subprocess

_CLEANUP_REGISTERED = False


def kill_orphan_python():
    """终止所有属于当前进程树的 Python 子进程。
    Windows: 用 taskkill 杀所有 python.exe（除了自己）。
    """
    current_pid = os.getpid()

    if sys.platform == "win32":
        try:
            # Use wmic to kill child processes of this process
            subprocess.run(
                ["wmic", "process", "where",
                 f"(ParentProcessId={current_pid} and Name='python.exe')",
                 "delete"],
                capture_output=True, timeout=10
            )
        except Exception:
            pass
    else:
        # Unix: use pkill
        try:
            subprocess.run(
                ["pkill", "-P", str(current_pid), "python"],
                capture_output=True, timeout=10
            )
        except Exception:
            pass


def cleanup():
    """atexit handler — 在 Python 进程退出时自动调用。"""
    kill_orphan_python()


def register():
    """注册 atexit handler。幂等——多次调用只注册一次。"""
    global _CLEANUP_REGISTERED
    if not _CLEANUP_REGISTERED:
        atexit.register(cleanup)
        _CLEANUP_REGISTERED = True


# ─── Auto-register on import ───
register()


# ─── Manual invocation support ───
if __name__ == "__main__":
    print("Killing orphan python processes...")
    kill_orphan_python()
    print("Done.")
