# Foundation Week 1 - Real Infrastructure Testing Script (PowerShell)
# This script tests with REAL services: PostgreSQL, Redis, R2, OpenAI
# ⚠️  WARNING: This will incur real costs (~$0.01 per run)

$ErrorActionPreference = "Stop"

Write-Host "`n╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Foundation Week 1 - Real Infrastructure Tests      ║" -ForegroundColor Cyan
Write-Host "║  ⚠️  Uses REAL services & incurs costs               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# Check we're in the right directory
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: Must run from backend/docker directory" -ForegroundColor Red
    Write-Host "cd backend\docker" -ForegroundColor Yellow
    Write-Host ".\run_real_infrastructure_tests.ps1" -ForegroundColor Yellow
    exit 1
}

# Load production config
if (-not (Test-Path "../.env.production")) {
    Write-Host "ERROR: .env.production not found" -ForegroundColor Red
    exit 1
}

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "Phase 1: Infrastructure Startup" -ForegroundColor Blue
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Blue

Write-Host "Starting services (this may take 60-90 seconds)..." -ForegroundColor White

# Use WSL to run docker compose (since Docker Desktop on Windows uses WSL2 backend)
wsl bash -c "cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker && docker compose --env-file ../.env.production -f docker-compose.yml -f docker-compose.foundation.yml up -d --build"

Write-Host "`nWaiting for services to be healthy...`n" -ForegroundColor White

# Function to check service health
function Test-ServiceHealth {
    param(
        [string]$ServiceName,
        [int]$MaxWaitSeconds
    )

    Write-Host "  Checking $ServiceName... " -NoNewline

    $elapsed = 0
    $interval = 5

    while ($elapsed -lt $MaxWaitSeconds) {
        $status = wsl bash -c "cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker && docker compose ps $ServiceName | grep 'Up (healthy)'"

        if ($status) {
            Write-Host "OK (${elapsed}s)" -ForegroundColor Green
            return $true
        }

        Start-Sleep -Seconds $interval
        $elapsed += $interval
        Write-Host "." -NoNewline
    }

    Write-Host "TIMEOUT (>$MaxWaitSeconds)" -ForegroundColor Red
    return $false
}

# Check critical services
if (-not (Test-ServiceHealth "hyer-postgres" 60)) { exit 1 }
if (-not (Test-ServiceHealth "hyer-redis" 30)) { exit 1 }
if (-not (Test-ServiceHealth "hyer-api" 90)) { exit 1 }
if (-not (Test-ServiceHealth "hyer-worker-document" 45)) { exit 1 }
if (-not (Test-ServiceHealth "hyer-worker-embedding" 45)) { exit 1 }

Write-Host "`n✓ All services are healthy!`n" -ForegroundColor Green

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "Phase 2: Database & Extension Verification" -ForegroundColor Blue
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Blue

Write-Host "  Checking pgvector extension... " -NoNewline
$pgvectorVersion = wsl bash -c "docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c 'SELECT extversion FROM pg_extension WHERE extname=''vector'';' 2>/dev/null | xargs"

if ($pgvectorVersion) {
    Write-Host "OK (version: $pgvectorVersion)" -ForegroundColor Green
} else {
    Write-Host "FAIL - pgvector extension not loaded!" -ForegroundColor Red
    exit 1
}

# Get baseline counts
$docCountBefore = wsl bash -c "docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c 'SELECT COUNT(*) FROM candidate_documents;' 2>/dev/null | xargs"
$embCountBefore = wsl bash -c "docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c 'SELECT COUNT(*) FROM document_embeddings;' 2>/dev/null | xargs"

Write-Host "  Current documents: $docCountBefore" -ForegroundColor White
Write-Host "  Current embeddings: $embCountBefore`n" -ForegroundColor White

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "Phase 3: Cost Tracking Baseline" -ForegroundColor Blue
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Blue

Write-Host "  Recording baseline costs..." -ForegroundColor White
$costBefore = try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/admin/costs" -ErrorAction SilentlyContinue
    $response.data.today.total_usd
} catch {
    "0"
}
Write-Host "  Starting cost: `$$costBefore`n" -ForegroundColor White

Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║  ⚠️  ABOUT TO RUN TESTS WITH REAL INFRASTRUCTURE    ║" -ForegroundColor Yellow
Write-Host "║                                                      ║" -ForegroundColor Yellow
Write-Host "║  This will:                                          ║" -ForegroundColor Yellow
Write-Host "║  • Upload documents to R2 (cloud storage)            ║" -ForegroundColor Yellow
Write-Host "║  • Call OpenAI API for embeddings (~`$0.01)          ║" -ForegroundColor Yellow
Write-Host "║  • Store data in PostgreSQL                          ║" -ForegroundColor Yellow
Write-Host "║                                                      ║" -ForegroundColor Yellow
Write-Host "║  Expected cost: ~`$0.01 per test run                 ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════╝`n" -ForegroundColor Yellow

$confirm = Read-Host "Continue? (yes/no)"
if ($confirm -ne "yes" -and $confirm -ne "y") {
    Write-Host "Aborted." -ForegroundColor Yellow
    exit 0
}

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "Phase 4: Running Integration Tests" -ForegroundColor Blue
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Blue

Write-Host "Running tests (this may take 2-5 minutes)...`n" -ForegroundColor White

# Run tests in Docker container with real infrastructure
$testExitCode = 0
try {
    wsl bash -c @"
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker
docker exec hyer-api bash -c 'cd /app/backend && \
    export PYTHONPATH=/app/backend && \
    export DATABASE_URL=postgresql+asyncpg://hyrepath:password@postgres:5432/hyrepath && \
    export REDIS_URL=redis://redis:6379/0 && \
    python -m pytest tests/test_foundation_week1_integration.py -v --tb=short --color=yes'
"@
} catch {
    $testExitCode = 1
}

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "Phase 5: Post-Test Verification" -ForegroundColor Blue
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor Blue

# Get final counts
$docCountAfter = wsl bash -c "docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c 'SELECT COUNT(*) FROM candidate_documents;' 2>/dev/null | xargs"
$embCountAfter = wsl bash -c "docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c 'SELECT COUNT(*) FROM document_embeddings;' 2>/dev/null | xargs"

Write-Host "  Documents after tests: $docCountAfter (+$($docCountAfter - $docCountBefore))" -ForegroundColor White
Write-Host "  Embeddings after tests: $embCountAfter (+$($embCountAfter - $embCountBefore))" -ForegroundColor White

# Check embedding dimensions
if ([int]$embCountAfter -gt 0) {
    $avgDim = wsl bash -c "docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c 'SELECT AVG(array_length(embedding, 1)) FROM document_embeddings;' 2>/dev/null | xargs"
    Write-Host "  Average embedding dimensions: $avgDim" -ForegroundColor White

    if ($avgDim -match "1536") {
        Write-Host "  ✓ Embeddings have correct dimensions (1536)" -ForegroundColor Green
    }
}

# Final cost
$costAfter = try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/admin/costs" -ErrorAction SilentlyContinue
    $response.data.today.total_usd
} catch {
    "0"
}
Write-Host "  Ending cost: `$$costAfter" -ForegroundColor White

if ($costAfter -ne "0" -and $costBefore -ne "0") {
    $testCost = [decimal]$costAfter - [decimal]$costBefore
    Write-Host "  Test run cost: `$$testCost" -ForegroundColor White
}

Write-Host "`n╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              Test Execution Complete                 ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

if ($testExitCode -eq 0) {
    Write-Host "✓ ALL TESTS PASSED`n" -ForegroundColor Green
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  1. Review cost usage in OpenAI dashboard" -ForegroundColor White
    Write-Host "  2. Verify R2 bucket contents" -ForegroundColor White
    Write-Host "  3. Check pgvector search performance`n" -ForegroundColor White
} else {
    Write-Host "✗ SOME TESTS FAILED`n" -ForegroundColor Red
    Write-Host "Troubleshooting:" -ForegroundColor White
    Write-Host "  1. Check worker logs: wsl docker logs hyer-worker-document" -ForegroundColor White
    Write-Host "  2. Check API logs: wsl docker logs hyer-api" -ForegroundColor White
    Write-Host "  3. Verify OpenAI API key is valid" -ForegroundColor White
    Write-Host "  4. Check R2 credentials`n" -ForegroundColor White
}

Write-Host "To stop all services:" -ForegroundColor Yellow
Write-Host "  wsl bash -c 'cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker && docker compose -f docker-compose.yml -f docker-compose.foundation.yml down'`n" -ForegroundColor Yellow

exit $testExitCode
