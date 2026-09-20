"""
Gunicorn server configuration.
Settings here are about the HTTP server only. Application settings live in
src/config.py. Both read the same environment, so the layering is the same:
real environment variables, then backend/.env, then the defaults below.
Run with:  gunicorn -c gunicorn.conf.py "src.api:create_app()"
"""
import multiprocessing
import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent

# This file is executed by the Gunicorn master before the app is imported, so
# src/config.py hasn't run yet and backend/.env hasn't been read. Load it here
# so dev overrides apply to server settings too. override=False keeps real
# environment variables (Dockerfile ENV, compose) in front. Workers inherit
# this environment through fork, so the app sees the same values.
load_dotenv(BACKEND_DIR / ".env", override=False)
APP_ENV = os.environ.get("APP_ENV", "development")

def _int(name, default):
    return int(os.environ.get(name, default))

# ── Socket ────────────────────────────────────────────────────────────
# 0.0.0.0 in the container so nginx can reach it. Localhost in dev.
_host = "0.0.0.0" if APP_ENV == "production" else "127.0.0.1"
bind = os.environ.get("GUNICORN_BIND", f"{_host}:{_int('PORT', 5000)}")
backlog = 2048

# ── Worker model ──────────────────────────────────────────────────────
# gthread, not sync. With sync workers the master kills any request that runs
# longer than `timeout`, including healthy SSE streams. gthread runs requests
# in threads while the main loop keeps sending heartbeats, so a long upload
# stream is no longer treated as a hung worker.
worker_class = "gthread"
workers = _int("WEB_CONCURRENCY", min(2, multiprocessing.cpu_count()))

# Each in-flight request holds a thread for its entire duration, and a receipt
# upload stream can run for minutes. threads is the ceiling on concurrent
# uploads per worker. Outbound Gemini calls peak at
# threads * GEMINI_MAX_CONCURRENCY per worker.
threads = _int("GUNICORN_THREADS", 4)

# ── Timeouts ──────────────────────────────────────────────────────────
# With gthread this is a liveness check on the worker's main loop, not a limit
# on request duration. Request duration is bounded by RECEIPT_STREAM_TIMEOUT in
# src/config.py. Keep this generous: it should only fire if a worker is truly
# wedged.
timeout = _int("GUNICORN_TIMEOUT", 120)

# On SIGTERM, how long workers get to finish in-flight requests. Must comfortably
# exceed RECEIPT_STREAM_HEARTBEAT (10s) so a stream can notice the shutdown,
# cancel its tasks, and emit a final event.
graceful_timeout = _int("GUNICORN_GRACEFUL_TIMEOUT", 30)

# Keep-alive for connections from nginx. Should be below nginx's
# keepalive_timeout.
keepalive = _int("GUNICORN_KEEPALIVE", 5)

# ── Worker recycling ──────────────────────────────────────────────────
# Guards against slow leaks. Restarts happen between requests, so an in-flight
# upload is never interrupted. Jitter stops all workers recycling together.
max_requests = _int("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = _int("GUNICORN_MAX_REQUESTS_JITTER", 100)

# Heartbeat file goes on a tmpfs. On some container filesystems a disk-backed
# heartbeat file stalls and the master kills healthy workers.
worker_tmp_dir = "/dev/shm" if Path("/dev/shm").exists() else None

# Don't preload. With preload_app the app is imported once in the master and
# forked, which would start APScheduler before the fork and leave its threads
# in an undefined state. It also breaks code reload on restart.
preload_app = False

# ── Proxy ─────────────────────────────────────────────────────────────
# Trust X-Forwarded-* from nginx only. "*" would let clients spoof the scheme.
forwarded_allow_ips = os.environ.get("GUNICORN_FORWARDED_ALLOW_IPS", "127.0.0.1")

# ── Logging ───────────────────────────────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# %(M)s is request duration in ms, which makes slow uploads easy to spot.
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms "%(a)s"'

# ── Hooks ─────────────────────────────────────────────────────────────
def on_starting(server):
    server.log.info(
        f"Gunicorn starting | env={APP_ENV} | bind={bind} | "
        f"{worker_class} workers={workers} threads={threads} | "
        f"timeout={timeout}s graceful={graceful_timeout}s"
    )

def worker_abort(worker):
    """
    Called when the master is about to kill a worker for exceeding `timeout`.
    Dump every thread's stack so the next WORKER TIMEOUT comes with evidence
    instead of the misleading "Perhaps out of memory?" message.
    """
    import faulthandler
    import sys
    worker.log.error(f"Worker {worker.pid} timed out. Thread stacks follow:")
    faulthandler.dump_traceback(file=sys.stderr)
    
def worker_int(worker):
    worker.log.info(f"Worker {worker.pid} interrupted, shutting down")