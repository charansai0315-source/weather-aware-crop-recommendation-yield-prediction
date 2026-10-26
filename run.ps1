$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required. Install it, then run this script again."
}

& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is installed but not running. Open Docker Desktop, wait until its engine is ready, then run .\run.ps1 again."
}

Write-Host "Building and starting MySQL, the Spring Boot API, and the Python ML service..." -ForegroundColor Green
Write-Host "The first build downloads dependencies and trains both models; it can take a few minutes." -ForegroundColor DarkGray
Write-Host "When ready, open http://localhost:8081" -ForegroundColor Cyan
& docker compose up --build
if ($LASTEXITCODE -ne 0) {
    throw "The project did not start. Review the Docker Compose output above."
}
