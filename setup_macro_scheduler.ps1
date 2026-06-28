# setup_macro_scheduler.ps1
# Registers the "MacroCompass-Daily" Windows Task Scheduler job:
#   refreshes macro.db (prices + signals + history) every weekday at 5:30 PM ET,
#   after the TSX/US close and staggered behind the Northstar-Daily job (5:15 PM).
#
# Runs as the current user (no elevation required). To register:
#   powershell -ExecutionPolicy Bypass -File setup_macro_scheduler.ps1

$ProjectDir = "C:\Users\zachc\Desktop\macro_sentiment"
$TaskName   = "MacroCompass-Daily"
$BatFile    = Join-Path $ProjectDir "run_macro_daily.bat"

Write-Host ""
Write-Host "Macro Compass Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Project: $ProjectDir"
Write-Host "Action : $BatFile"
Write-Host ""

if (-not (Test-Path $BatFile)) {
    Write-Host "  [FAIL] run_macro_daily.bat not found." -ForegroundColor Red
    exit 1
}

# Remove existing task if present
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  Removed existing task: $TaskName" -ForegroundColor Yellow
}

$Action  = New-ScheduledTaskAction -Execute $BatFile -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 5:30PM
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Settings $Settings `
        -Description "Taynton Bay Capital - Macro Compass daily refresh (prices + signals). Weekdays 5:30 PM ET." `
        -Force | Out-Null
    Write-Host "  [OK] Task registered: $TaskName - weekdays at 5:30 PM" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $TaskName : $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Verify in Task Scheduler (taskschd.msc), or run now to test:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
