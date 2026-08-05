# PowerShell script to run tests with PostgreSQL
# Run pytest with local PostgreSQL (Docker)

Write-Host "Starting PostgreSQL and Redis with Docker Compose..." -ForegroundColor Cyan
Set-Location docker
docker compose -f docker-compose.yml up -d postgres redis

Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# Check if PostgreSQL is healthy
$ready = $false
$attempts = 0
while (-not $ready -and $attempts -lt 30) {
    $result = docker exec hyer-postgres pg_isready -U hyrepath 2>&1
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
    } else {
        Write-Host "Waiting for PostgreSQL..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
        $attempts++
    }
}

if (-not $ready) {
    Write-Host "PostgreSQL failed to start!" -ForegroundColor Red
    exit 1
}

Write-Host "Running migrations..." -ForegroundColor Cyan
Set-Location ..
python -m alembic upgrade head

Write-Host "Running tests with PostgreSQL..." -ForegroundColor Cyan

# Load environment from .env.test.postgres
Get-Content .env.test.postgres | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
    }
}

python -m pytest tests/test_foundation_week1_integration.py -v --tb=short

Write-Host "Tests complete!" -ForegroundColor Green
