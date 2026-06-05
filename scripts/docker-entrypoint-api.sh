#!/bin/sh
set -e

uv run alembic -c packages/storage/alembic.ini upgrade head
exec uv run uvicorn chengdu_edu_api.main:app --host 0.0.0.0 --port 8000
