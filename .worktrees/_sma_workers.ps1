# ============================================================================
# Start Celery Workers on Host Machine (Windows PowerShell)
# ============================================================================
# This script runs Celery workers on the host machine instead of Docker.
#
# WHY: ChromeDriver inside Multilogin rejects all non-localhost connections.
#      Docker containers use host.docker.internal which gets blocked.
#      Running workers on host allows localhost connections to Multilogin.
#
# PREREQUISITES:
#   1. Docker infrastructure running: docker compose -f docker-compose.windows.yml up -d
#   2. Multilogin app running on host
#   3. Poetry installed and project dependencies set up
#
# USAGE:
#   .\scripts\start_workers.ps1           # Run all workers
#   .\scripts\start_workers.ps1 campaign  # Run only campaign worker
#   .\scripts\start_workers.ps1 ocr       # Run only OCR worker
# ============================================================================

param(
    [string]$WorkerType = "all"
)

# Change to project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path -Parent $ScriptDir)

Write-Host "============================================" -ForegroundColor Blue
Write-Host " Social Media Automation - Worker Launcher " -ForegroundColor Blue
Write-Host "============================================" -ForegroundColor Blue

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "Error: .env file not found!" -ForegroundColor Red
    Write-Host "Please copy env.example to .env and configure it."
    exit 1
}

# Load .env file
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim().Trim('"')
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Write-Host "Checking Redis connection..." -ForegroundColor Yellow

# Function to start a worker in a new window using poetry
function Start-Worker {
    param(
        [string]$Queue,
        [string]$Name
    )
    Write-Host "Starting $Name worker (queue: $Queue)..." -ForegroundColor Green
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "poetry run celery -A core.celery_app.celery_app worker -Q $Queue --loglevel=info --hostname=$Name@%COMPUTERNAME%"
}

switch ($WorkerType.ToLower()) {
    "campaign" {
        Write-Host "Starting Campaign Worker only..." -ForegroundColor Yellow
        Start-Worker -Queue "campaign_queue" -Name "campaign"
    }
    "instagram" {
        Write-Host "Starting Instagram Worker only..." -ForegroundColor Yellow
        Start-Worker -Queue "instagram_queue" -Name "instagram"
    }
    "ocr" {
        Write-Host "Starting OCR Worker only..." -ForegroundColor Yellow
        Start-Worker -Queue "ocr_queue" -Name "ocr"
    }
    "s3" {
        Write-Host "Starting S3 Upload Worker only..." -ForegroundColor Yellow
        Start-Worker -Queue "s3_upload_queue" -Name "s3upload"
    }
    "persona" {
        Write-Host "Starting Persona Worker only..." -ForegroundColor Yellow
        Start-Worker -Queue "persona_queue" -Name "persona"
    }
    "all" {
        Write-Host "Starting ALL workers..." -ForegroundColor Yellow
        Start-Worker -Queue "campaign_queue" -Name "campaign"
        Start-Sleep -Seconds 2
        Start-Worker -Queue "instagram_queue" -Name "instagram"
        Start-Sleep -Seconds 2
        Start-Worker -Queue "ocr_queue" -Name "ocr"
        Start-Sleep -Seconds 2
        Start-Worker -Queue "s3_upload_queue" -Name "s3upload"
        Start-Sleep -Seconds 2
        Start-Worker -Queue "persona_queue" -Name "persona"
    }
    default {
        Write-Host "Unknown worker type: $WorkerType" -ForegroundColor Red
        Write-Host "Usage: .\start_workers.ps1 [campaign|instagram|ocr|s3|persona|all]"
        exit 1
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Workers started in separate windows!      " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "SELENIUM_HOST=$env:SELENIUM_HOST" -ForegroundColor Blue
Write-Host "REDIS_URL=$env:REDIS_URL" -ForegroundColor Blue
