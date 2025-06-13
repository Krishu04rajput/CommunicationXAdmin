import multiprocessing

bind = "0.0.0.0:5000"
workers = 1
worker_class = "gevent"
worker_connections = 1000
timeout = 30
keepalive = 2
preload_app = False  # Faster startup
max_requests = 1000
max_requests_jitter = 100
reload = True
reload_extra_files = ["templates/", "static/"]