#!/bin/bash
set -e

echo "Starting gunicorn..."
exec gunicorn main:app --bind 0.0.0.0:8765 --workers 2 --timeout 180
