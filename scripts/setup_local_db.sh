#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is not installed. Install PostgreSQL first (brew install postgresql@16)."
  exit 1
fi

if ! command -v pg_isready >/dev/null 2>&1; then
  echo "pg_isready is not installed. Install PostgreSQL first (brew install postgresql@16)."
  exit 1
fi

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "Created $BACKEND_DIR/.env from .env.example"
fi

echo "Checking PostgreSQL service on localhost:5432..."
if ! pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
  echo "PostgreSQL is not accepting connections on localhost:5432"
  echo "Start it with: brew services start postgresql@16"
  exit 1
fi

echo "Ensuring role postgres exists..."
if ! psql -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='postgres'" | grep -q 1; then
  psql -d postgres -c "CREATE ROLE postgres WITH LOGIN SUPERUSER PASSWORD 'postgres';"
fi

echo "Ensuring database residential_platform exists..."
if ! psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='residential_platform'" | grep -q 1; then
  psql -d postgres -c "CREATE DATABASE residential_platform OWNER postgres;"
fi

if [[ -d "$BACKEND_DIR/venv" ]]; then
  # shellcheck disable=SC1091
  source "$BACKEND_DIR/venv/bin/activate"
fi

echo "Running Alembic migrations..."
(cd "$BACKEND_DIR" && alembic upgrade head)

echo "Running seed data..."
(cd "$BACKEND_DIR" && python scripts/seed.py)

echo "Database setup complete."
