import os
import multiprocessing

# Server socket
bind = "127.0.0.1:8000"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

# Process naming
proc_name = "agency_dashboard"

# Logging
accesslog = "/var/log/agency_dashboard/access.log"
errorlog = "/var/log/agency_dashboard/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process management
daemon = False
pidfile = "/var/run/agency_dashboard/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# Server mechanics
reload = False
daemon = False

# SSL (if using HTTPS)
# keyfile = "/path/to/ssl/key.pem"
# certfile = "/path/to/ssl/cert.pem"

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    pass

def when_ready(server):
    """Called just after the server is started."""
    pass

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    pass

def pre_exec(server):
    """Called just before a new master process is forked."""
    pass

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    pass

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    pass

def pre_request(worker, req):
    """Called just before a worker processes the request."""
    pass

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    pass
