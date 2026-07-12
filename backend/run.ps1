Write-Host "Starting Auto-Gaffer Backend..." -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path "venv")) {
    Write-Host "Creating Virtual Environment (venv)..." -ForegroundColor Cyan
    python -m venv venv
}

Write-Host "Installing/Updating dependencies in venv..." -ForegroundColor Cyan
.\venv\Scripts\pip install -r requirements.txt

Write-Host "Starting FastAPI Server on http://localhost:8000" -ForegroundColor Green
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
.\venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000