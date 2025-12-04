#!/usr/bin/env bash
# start.sh
gunicorn M.0.1:app_mount --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT