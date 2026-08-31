#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python && ! -x .venv/Scripts/python ]]; then
  echo "Creating virtual environment..."
  if command -v uv >/dev/null 2>&1; then
    uv venv .venv
    uv pip install --python .venv/bin/python -r requirements.txt 2>/dev/null || uv pip install --python .venv/Scripts/python.exe -r requirements.txt
  else
    python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
  fi
fi
PY=.venv/bin/python
[[ -x $PY ]] || PY=.venv/Scripts/python.exe
echo
echo "RASA-Analyst → http://127.0.0.1:8787"
echo "Keep Ollama running. Model: nebulatech/rasa-analyst"
echo
export RASA_ENV=production
export RASA_HOST=127.0.0.1
export RASA_PORT=8787
exec "$PY" run.py
