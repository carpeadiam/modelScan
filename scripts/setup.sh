#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
npm install
(npm --prefix dashboard install)
(cd worker && npm install)
echo 'PipelineGuard dependencies installed. Run: source .venv/bin/activate; then copy .env.example to .env and configure credentials.'
