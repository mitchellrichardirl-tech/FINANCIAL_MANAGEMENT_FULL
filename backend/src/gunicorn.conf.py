import os
workers = int(os.environ.get("WEB_CONCURRENCY", 2))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))