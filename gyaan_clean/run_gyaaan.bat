@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" (
  echo GROQ_API_KEY=gsk_your_groq_api_key_here>.env
  echo Created .env. Add your Groq API key before starting GYAAAN.
  pause
  exit /b 1
)

python -m pip install -r requirements.txt
python app.py
