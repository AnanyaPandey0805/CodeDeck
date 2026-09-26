#!/usr/bin/env pwsh
# CodeDeck Midsem Demo Script
# Usage: .\scripts\run_demo.ps1

$ErrorActionPreference = "Stop"

$BACKEND = "http://localhost:8000"
$DEMO_REPO = "https://github.com/tiangolo/full-stack-fastapi-template"  # known-good FastAPI repo
# Change DEMO_REPO to any supported Python/Node repo you prefer

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  CodeDeck — Midsem Demo" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ─── 1. Start Docker Compose ────────────────────────────────────────────────
Write-Host "[1/10] Starting Docker Compose..." -ForegroundColor Yellow
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Write-Host "Docker Compose failed" -ForegroundColor Red; exit 1 }

# ─── 2. Wait for backend health ─────────────────────────────────────────────
Write-Host "[2/10] Waiting for backend to be healthy..." -ForegroundColor Yellow
$deadline = (Get-Date).AddSeconds(90)
$up = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-RestMethod "$BACKEND/health" -TimeoutSec 3
        if ($r.status -eq "ok") { $up = $true; break }
    } catch { }
    Start-Sleep 3
    Write-Host "  ... waiting" -ForegroundColor DarkGray
}
if (-not $up) { Write-Host "Backend did not start in time" -ForegroundColor Red; exit 1 }
Write-Host "  Backend healthy ✓" -ForegroundColor Green

# ─── 3. System status ───────────────────────────────────────────────────────
Write-Host "[3/10] Checking system status..." -ForegroundColor Yellow
try {
    $status = Invoke-RestMethod "$BACKEND/api/system/status"
    Write-Host "  Backend  : $($status.backend.message)"
    Write-Host "  Database : $($status.database.message)"
    Write-Host "  Docker   : $($status.docker.message)"
    Write-Host "  kind     : $($status.kind.message)"
    Write-Host "  kubectl  : $($status.kubectl.message)"
    if (-not $status.kind.ok) {
        Write-Host ""
        Write-Host "  WARNING: kind cluster not ready." -ForegroundColor Yellow
        Write-Host "  Create one with: kind create cluster --name deploymind" -ForegroundColor Yellow
        Write-Host "  Deployment steps will fail without a cluster." -ForegroundColor Yellow
        Write-Host ""
    }
} catch {
    Write-Host "  Could not retrieve system status: $_" -ForegroundColor DarkGray
}

# ─── 4. Create project ──────────────────────────────────────────────────────
Write-Host "[4/10] Creating project for: $DEMO_REPO" -ForegroundColor Yellow
$project = Invoke-RestMethod "$BACKEND/api/projects" -Method POST `
    -ContentType "application/json" `
    -Body (ConvertTo-Json @{ repository_url = $DEMO_REPO })
$pid = $project.id
Write-Host "  Project created: id=$pid name=$($project.repository_name) ✓" -ForegroundColor Green

# ─── 5. Run analysis ────────────────────────────────────────────────────────
Write-Host "[5/10] Running repository analysis (may take 2-5 minutes)..." -ForegroundColor Yellow
$analysis = Invoke-RestMethod "$BACKEND/api/projects/$pid/analyze" -Method POST -TimeoutSec 600
Write-Host "  Language  : $($analysis.language)"
Write-Host "  Framework : $($analysis.framework)"
Write-Host "  Entry     : $($analysis.entrypoint)"
Write-Host "  Port      : $($analysis.analysis_result.port)"
Write-Host "  Dockerfile: $($analysis.has_dockerfile)"
Write-Host "  Analysis complete ✓" -ForegroundColor Green

# ─── 6. Ask Q&A question ────────────────────────────────────────────────────
Write-Host "[6/10] Asking repository Q&A question..." -ForegroundColor Yellow
$qa = Invoke-RestMethod "$BACKEND/api/projects/$pid/qa" -Method POST `
    -ContentType "application/json" `
    -Body (ConvertTo-Json @{ question = "What framework does this project use?" })
Write-Host "  Q: What framework does this project use?"
Write-Host "  A: $($qa.answer)"
Write-Host "  Sources: $($qa.sources.Count) retrieved ✓" -ForegroundColor Green

# ─── 7. Run AI-generated tests ──────────────────────────────────────────────
Write-Host "[7/10] Running AI-generated tests..." -ForegroundColor Yellow
try {
    $tests = Invoke-RestMethod "$BACKEND/api/projects/$pid/ai-tests" -Method POST -TimeoutSec 300
    Write-Host "  Status : $($tests.status)"
    Write-Host "  Message: $($tests.message)"
    if ($tests.status -eq "passed") {
        Write-Host "  AI tests PASSED ✓" -ForegroundColor Green
    } elseif ($tests.status -eq "skipped") {
        Write-Host "  AI tests SKIPPED (not supported for this repo type)" -ForegroundColor Yellow
    } else {
        Write-Host "  AI tests FAILED — see failure analysis in UI" -ForegroundColor Red
    }
} catch {
    Write-Host "  AI test call failed: $_" -ForegroundColor Yellow
}

# ─── 8. Deploy staging ──────────────────────────────────────────────────────
Write-Host "[8/10] Deploying to staging (Docker + kind)..." -ForegroundColor Yellow
Write-Host "  This may take 5-10 minutes for Docker build + kind load + rollout."
try {
    $deploy = Invoke-RestMethod "$BACKEND/api/projects/$pid/deploy/staging" -Method POST -TimeoutSec 900
    Write-Host "  Deploy initiated: $($deploy.status) — $($deploy.message)"

    # Wait for deployment to finish
    $limit = (Get-Date).AddMinutes(12)
    while ((Get-Date) -lt $limit) {
        Start-Sleep 8
        $proj = Invoke-RestMethod "$BACKEND/api/projects/$pid"
        Write-Host "  ... project status: $($proj.status)"
        if ($proj.status -eq "staging_healthy" -or $proj.status -eq "staging_failed" -or $proj.status -eq "failed") { break }
    }

    $proj = Invoke-RestMethod "$BACKEND/api/projects/$pid"
    if ($proj.status -eq "staging_healthy") {
        Write-Host "  Staging deployment HEALTHY ✓" -ForegroundColor Green
    } else {
        Write-Host "  Staging deployment status: $($proj.status)" -ForegroundColor Red
        Write-Host "  Check the Kubernetes page in the UI for logs." -ForegroundColor Yellow
    }
} catch {
    Write-Host "  Staging deploy failed: $_" -ForegroundColor Red
    Write-Host "  Check that the kind cluster 'deploymind' is running." -ForegroundColor Yellow
}

# ─── 9. Get pipeline summary ────────────────────────────────────────────────
Write-Host "[9/10] Pipeline summary..." -ForegroundColor Yellow
$pipeline = Invoke-RestMethod "$BACKEND/api/projects/$pid/pipeline"
foreach ($step in $pipeline) {
    $icon = switch ($step.status) {
        "completed" { "✓" }
        "failed"    { "✗" }
        "running"   { "●" }
        "warning"   { "⚠" }
        default     { "○" }
    }
    $color = switch ($step.status) {
        "completed" { "Green" }
        "failed"    { "Red" }
        "warning"   { "Yellow" }
        default     { "Gray" }
    }
    Write-Host ("  {0} {1,-30} [{2}]" -f $icon, $step.name, $step.status) -ForegroundColor $color
}

# ─── 10. Final summary ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Demo Complete" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Open the dashboard: http://localhost:3000" -ForegroundColor White
Write-Host "  API docs:           http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Project ID:         $pid" -ForegroundColor White
Write-Host ""
Write-Host "  Next steps in the UI:" -ForegroundColor Yellow
Write-Host "    1. Select the project in Overview"
Write-Host "    2. Go to AI Assistant → ask questions"
Write-Host "    3. Go to Testing → review AI test results"
Write-Host "    4. Go to Kubernetes → check deployment status"
Write-Host "    5. Go to Settings → verify system health"
Write-Host ""
