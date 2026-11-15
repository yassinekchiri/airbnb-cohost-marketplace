import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))  # scraping needs ~300 until Celery (Phase 6)
keepalive = 5
preload_app = True

# Logging
_log = os.getenv("GUNICORN_LOG_DIR")  # unset => stdout/stderr (containers)
accesslog = f"{_log}/gunicorn_access.log" if _log else "-"
errorlog = f"{_log}/gunicorn_error.log" if _log else "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sus'
