$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$port = if ($env:FINORA_DEMO_PORT) { [int]$env:FINORA_DEMO_PORT } else { 8000 }
$baseUrl = "http://127.0.0.1:$port"

Write-Host "Starting FINORA API on $baseUrl"
$api = Start-Process `
    -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "aurum.api.main:app", "--host", "127.0.0.1", "--port", "$port") `
    -PassThru `
    -WindowStyle Hidden

try {
    $healthy = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $health = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get
            $healthy = $true
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    if (-not $healthy) {
        throw "FINORA API did not become healthy at $baseUrl"
    }

    Write-Host "`nHealth"
    $health | Format-List

    $forecastBody = @{
        target = "DEMO"
        values = @(
            100.0, 100.8, 101.2, 100.9, 101.7,
            102.4, 102.1, 102.9, 103.5, 103.1,
            104.0, 104.6, 104.2, 105.0, 105.7,
            106.1, 105.8, 106.6, 107.2, 107.8,
            108.1, 108.7, 109.3, 109.0, 109.8
        )
        dates = @(
            "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05",
            "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-10",
            "2026-01-11", "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15",
            "2026-01-16", "2026-01-17", "2026-01-18", "2026-01-19", "2026-01-20",
            "2026-01-21", "2026-01-22", "2026-01-23", "2026-01-24", "2026-01-25"
        )
        horizon = 3
        frequency = "daily"
        forecast_start = "2026-01-26T00:00:00Z"
    } | ConvertTo-Json -Depth 5

    $forecast = Invoke-RestMethod -Uri "$baseUrl/v1/forecast" -Method Post -ContentType "application/json" -Body $forecastBody
    Write-Host "`nForecast"
    [pscustomobject]@{
        target = $forecast.forecast.target
        model_used = $forecast.forecast.model_used
        point_forecast = $forecast.forecast.point_forecast
        risk_observations = $forecast.risk.observations
        audit_run_id = $forecast.audit.run_id
    } | Format-List

    $sentimentBody = @{ text = "Revenue growth was strong, but management warned about margin pressure." } | ConvertTo-Json
    $sentiment = Invoke-RestMethod -Uri "$baseUrl/v1/sentiment" -Method Post -ContentType "application/json" -Body $sentimentBody
    Write-Host "`nSentiment"
    $sentiment | Format-List

    $finalHealth = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get
    Write-Host "`nAudit status"
    [pscustomobject]@{
        audit_chain_valid = $finalHealth.audit_chain_valid
        mode = $finalHealth.mode
    } | Format-List
} finally {
    if ($api -and -not $api.HasExited) {
        Stop-Process -Id $api.Id -Force
        Write-Host "Stopped FINORA API process $($api.Id)"
    }
}
