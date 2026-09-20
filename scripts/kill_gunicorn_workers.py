"""
Simulate a worker crash: SIGKILL every gunicorn worker process.
A process counts as a worker if both it and its parent have 'gunicorn' in
their command line. This skips the master, shells, and the VS Code server.
Usage:
  python scripts/kill_gunicorn_workers.py --dry-run   # list only
  python scripts/kill_gunicorn_workers.py             # kill
"""
import os
import signal
import sys
def cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError:
        return ""
def parent_of(pid: int) -> int:
    with open(f"/proc/{pid}/stat") as f:
        # The process name can contain spaces, so split after the last ')'.
        return int(f.read().rsplit(")", 1)[1].split()[1])
def main() -> int:
    dry_run = "--dry-run" in sys.argv
    me = os.getpid()
    found = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid == me:
            continue
        try:
            ppid = parent_of(pid)
        except OSError:
            continue  # process exited while we were scanning
        cmd = cmdline(pid)
        print(f'PID: {pid}, PPID: {ppid}, CMD: {cmd}')
        if "gunicorn" in cmd and "gunicorn" in cmdline(ppid):
            found += 1
            action = "would kill" if dry_run else "SIGKILL ->"
            print(f"{action} {pid} (parent {ppid}): {cmd[:100]}")
            if not dry_run:
                os.kill(pid, signal.SIGKILL)
    if not found:
        print("No gunicorn workers found in this container")
        return 1
    return 0
if __name__ == "__main__":
    sys.exit(main())