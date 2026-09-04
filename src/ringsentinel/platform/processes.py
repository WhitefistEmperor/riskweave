"""Terminate only a subprocess tree launched and still owned by this executor."""

import os
import signal
import subprocess


def terminate_child(process: subprocess.Popen):
    if process.poll() is not None:
        return
    if os.name == "nt":
        # Windows venv python.exe may be a launcher with another Python process beneath it.
        # Killing just the launcher does not stop analysis or release the child's OS lock.
        subprocess.run(
            [
                os.path.join(
                    os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "taskkill.exe"
                ),
                "/PID",
                str(process.pid),
                "/T",
                "/F",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    elif os.getpgid(process.pid) == process.pid:
        # Only kill a group whose leader is our own newly launched child, never our API group.
        os.killpg(process.pid, signal.SIGKILL)
    else:
        process.kill()
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)
