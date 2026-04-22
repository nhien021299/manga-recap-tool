# Setup script for Manhwa Recap Tool (Windows)
# Requirements: Python 3.10+, Node.js 18+

Write-Host "--- Manhwa Recap Tool Setup ---" -ForegroundColor Cyan

# 1. Check Python
$pythonCmd = "python"
try {
    $version = python --version 2>$null
    if ($null -eq $version) {
        $pythonCmd = "py"
        py --version 2>$null
    }
} catch {
    Write-Error "Python not found. Please install Python 3.10 or higher."
    exit 1
}

# 2. Setup Backend Venv (Vieneu default)
Write-Host "`n[1/4] Setting up backend environment..." -ForegroundColor Yellow
cd backend
if (-not (Test-Path ".bench\vieneu-venv")) {
    & $pythonCmd -m venv .bench\vieneu-venv
}
& .bench\vieneu-venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created backend/.env from example." -ForegroundColor Green
}
cd ..

# 3. Setup Frontend
Write-Host "`n[2/4] Setting up frontend environment..." -ForegroundColor Yellow
cd web-app
npm install
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created web-app/.env from example." -ForegroundColor Green
}
cd ..

# 4. Check canonical VieNeu voice assets
Write-Host "`n[3/4] Checking local voice assets..." -ForegroundColor Yellow
if (-not (Test-Path "backend\.models\vieneu-voices\voices.json")) {
    Write-Host "Warning: backend/.models/vieneu-voices/voices.json was not found." -ForegroundColor DarkYellow
    Write-Host "Build the cached preset with backend/scripts/build_voice_default_preset.py before using TTS."
} else {
    Write-Host "VieNeu preset manifest found." -ForegroundColor Green
}

# 5. Success
Write-Host "`n[4/4] Setup complete!" -ForegroundColor Cyan
Write-Host "`nTo start development:" -ForegroundColor White
Write-Host "1. Root: npm run dev:be  (Starts Backend)"
Write-Host "2. Root: npm run dev:web (Starts Frontend)"
Write-Host "`nDon't forget to add your GEMINI_API_KEY to both .env files!" -ForegroundColor Magenta
