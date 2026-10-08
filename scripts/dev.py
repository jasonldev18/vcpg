"""Start the API and the UI together; stop both when either exits or on Ctrl+C."""

import shutil
import subprocess
import sys
import time


def stop(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":  # npm runs vite in a child process; kill the whole tree
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()


procs = [
    subprocess.Popen([sys.executable, "-m", "backend"]),
    subprocess.Popen([shutil.which("npm") or "npm", "--prefix", "frontend", "run", "dev"]),
]
try:
    while all(p.poll() is None for p in procs):
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for p in procs:
        stop(p)
