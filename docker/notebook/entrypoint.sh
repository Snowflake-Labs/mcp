#!/bin/bash
set -e

echo "Starting marimo notebook server..."

exec marimo edit --host 0.0.0.0 --port 2718 --no-token
