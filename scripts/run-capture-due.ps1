param(
    [int]$MaxAttempts = 3,
    [double]$BackoffSeconds = 2
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$python = Join-Path $backendDir ".venv\Scripts\python.exe"
$logDir = Join-Path $repoRoot "logs"
$logFile = Join-Path $logDir "capture-due.log"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment not found at $python"
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$startedAt = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"

Push-Location $backendDir
try {
    "[$startedAt] capture-due started" | Add-Content -LiteralPath $logFile
    & $python -m app.cli capture-due `
        --max-attempts $MaxAttempts `
        --backoff-seconds $BackoffSeconds 2>&1 |
        ForEach-Object {
            "[$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK')] $_" |
                Add-Content -LiteralPath $logFile
        }
    $exitCode = $LASTEXITCODE
    "[$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK')] capture-due finished exit=$exitCode" |
        Add-Content -LiteralPath $logFile
    exit $exitCode
}
catch {
    "[$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK')] capture-due crashed: $($_.Exception.Message)" |
        Add-Content -LiteralPath $logFile
    exit 2
}
finally {
    Pop-Location
}
