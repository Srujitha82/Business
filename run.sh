#!/usr/bin/env bash
# ShopPulse: Python only (no Node.js needed).   Usage:  bash run.sh
cd "$(dirname "$0")"
python3 -m pip install -r backend/requirements.txt
(sleep 2; command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:5050 || command -v open >/dev/null && open http://127.0.0.1:5050) &
python3 backend/app.py
