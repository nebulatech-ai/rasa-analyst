@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  where uv >nul 2>nul
  if %ERRORLEVEL%==0 (
    uv venv .venv
    uv pip install --python .venv\Scripts\python.exe -r requirements.txt
  ) else (
    py -3 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  )
)
echo.
echo RASA-Analyst → http://127.0.0.1:8787
echo Keep Ollama running. Model: nebulatech/rasa-analyst
echo.
set RASA_ENV=production
set RASA_HOST=127.0.0.1
set RASA_PORT=8787
".venv\Scripts\python.exe" run.py
