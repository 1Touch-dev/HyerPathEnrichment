# PowerShell wrapper for the bash proof harness.
# This remains a valid entrypoint on Windows, but the actual proof contract
# lives in `run_real_infrastructure_tests.sh` so there is only one harness to
# keep consistent with Compose and pytest.

$ErrorActionPreference = "Stop"

if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: Must run from backend/docker directory" -ForegroundColor Red
    Write-Host "  cd backend\docker" -ForegroundColor Yellow
    Write-Host "  .\run_real_infrastructure_tests.ps1" -ForegroundColor Yellow
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$unixScriptDir = $scriptDir -replace "\\", "/"
if ($unixScriptDir -match "^[A-Za-z]:/") {
    $drive = $unixScriptDir.Substring(0, 1).ToLowerInvariant()
    $rest = $unixScriptDir.Substring(2)
    $unixScriptDir = "/mnt/$drive$rest"
}

$realInfraEnv = $env:REAL_INFRA_ENV_FILE
if (-not $realInfraEnv) {
    $realInfraEnv = "../.env.production"
}

$wslCommand = @(
    "cd '$unixScriptDir'"
    "export REAL_INFRA_ENV_FILE=" + [System.Management.Automation.Language.CodeGeneration]::QuoteArgument($realInfraEnv)
    "bash ./run_real_infrastructure_tests.sh"
) -join " && "

wsl bash -lc $wslCommand
exit $LASTEXITCODE
