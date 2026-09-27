# CodeDeck — End-to-End Workflow Script

$ErrorActionPreference = "Stop"

Write-Host "Starting CodeDeck environment..." -ForegroundColor Green
docker compose up -d --build

Write-Host "Waiting for backend health endpoint..." -ForegroundColor Yellow
$healthUrl = "http://localhost:8000/health"
$maxRetries = 30
$retryCount = 0
$isHealthy = $false

while (-not $isHealthy -and $retryCount -lt $maxRetries) {
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -Method Get -ErrorAction Stop
        if ($response.status -eq "ok") {
            $isHealthy = $true
            Write-Host "Backend is healthy!" -ForegroundColor Green
        }
    } catch {
        $retryCount++
        Write-Host "Waiting... ($retryCount/$maxRetries)" -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $isHealthy) {
    Write-Error "Backend failed to become healthy within the timeout period."
    exit 1
}

Write-Host "Checking system status..." -ForegroundColor Green
# System status checks can be expanded here

Write-Host "Creating project integration..." -ForegroundColor Green
$createProjectBody = @{
    repository_url = "https://github.com/tiangolo/full-stack-fastapi-template"
} | ConvertTo-Json

$projectResponse = Invoke-RestMethod -Uri "http://localhost:8000/projects/" -Method Post -Body $createProjectBody -ContentType "application/json"
$projectId = $projectResponse.id
Write-Host "Created Project ID: $projectId" -ForegroundColor Cyan

Write-Host "Running analysis..." -ForegroundColor Green
Invoke-RestMethod -Uri "http://localhost:8000/projects/$projectId/analyze" -Method Post

Write-Host "Running RAG Q&A test..." -ForegroundColor Green
$qaBody = @{
    query = "What is the main purpose of this repository?"
} | ConvertTo-Json
$qaResponse = Invoke-RestMethod -Uri "http://localhost:8000/projects/$projectId/qa" -Method Post -Body $qaBody -ContentType "application/json"
Write-Host "Q&A Answer: $($qaResponse.answer)" -ForegroundColor Cyan

Write-Host "Running AI tests generation..." -ForegroundColor Green
Invoke-RestMethod -Uri "http://localhost:8000/projects/$projectId/tests" -Method Post

Write-Host "Deploying to staging environment..." -ForegroundColor Green
Invoke-RestMethod -Uri "http://localhost:8000/projects/$projectId/deploy" -Method Post

Write-Host "Polling pipeline status..." -ForegroundColor Yellow
$statusUrl = "http://localhost:8000/projects/$projectId/status"
$isFinished = $false
while (-not $isFinished) {
    $statusResponse = Invoke-RestMethod -Uri $statusUrl -Method Get
    $state = $statusResponse.pipeline_status
    if ($state -eq "completed" -or $state -eq "failed") {
        $isFinished = $true
        Write-Host "Pipeline finished with status: $state" -ForegroundColor Cyan
    } else {
        Write-Host "Pipeline status: $state..." -ForegroundColor Gray
        Start-Sleep -Seconds 5
    }
}

Write-Host "Pipeline Summary:" -ForegroundColor Green
$statusResponse.steps | ForEach-Object {
    Write-Host " - $($_.name): $($_.status)"
}

Write-Host ""
Write-Host "Workflow completed successfully." -ForegroundColor Green
Write-Host "Access the dashboard at: http://localhost:3000" -ForegroundColor Cyan
