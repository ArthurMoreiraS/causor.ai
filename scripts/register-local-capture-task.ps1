param(
    [string]$TaskName = "Causor Capture Due",
    [int]$IntervalMinutes = 60
)

$ErrorActionPreference = "Stop"
if ($IntervalMinutes -lt 15) {
    throw "IntervalMinutes must be at least 15."
}

$runner = Join-Path $PSScriptRoot "run-capture-due.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "Capture runner not found at $runner"
}
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $backendDir

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Runs Causor monitored OAB capture every $IntervalMinutes minutes." `
    -Force | Out-Null

Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State, TaskPath
