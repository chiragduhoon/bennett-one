# Starts everything BENNETT ONE needs, each in its own window.
#   .\scripts\start.ps1
# Then open http://localhost:5173
$root = Split-Path $PSScriptRoot -Parent

# 1) Project database (PostgreSQL on port 5433)
& "$PSScriptRoot\db.ps1" start

# 2) SSH tunnel to the GPU server running Ollama (Qwen3-14B + bge-m3); host comes from GPU_SSH_HOST in backend/.env
Start-Process powershell -ArgumentList "-NoExit", "-File", "$PSScriptRoot\tunnel.ps1"

# 3) Backend API (FastAPI) on :8000  — docs at http://localhost:8000/docs
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; uv run uvicorn app.main:app --port 8000"

# 4) Frontend (React/Vite) on :5173
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Write-Host "Starting... open http://localhost:5173 in ~15 seconds."
