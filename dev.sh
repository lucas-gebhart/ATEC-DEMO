#!/usr/bin/env bash
# Starts API (:8000) and web (:5173). Usage: ./dev.sh
set -e
cd "$(dirname "$0")"
[ -d api/.venv ] || (python3 -m venv api/.venv && api/.venv/bin/pip install -q -r api/requirements.txt)
[ -d web/node_modules ] || (cd web && npm ci)
(cd api && .venv/bin/uvicorn app.main:app --reload --port 8000) &
cd web && npm run dev
