#!/usr/bin/env bash
# Bootstrap a local development environment.
set -euo pipefail

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — fill in real values before running the app."
fi

python -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete. Run: uvicorn app.main:app --reload"
