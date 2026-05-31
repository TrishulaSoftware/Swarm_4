# ============================================================
# Q-MATRIX -- TASK SCHEDULER SETUP  (3x Daily + Sunday Earnings)
# ============================================================
# Registers FOUR scheduled tasks:
#   Mon-Fri 09:30 AM ET  -- Market Open sweep
#   Mon-Fri 12:00 PM ET  -- Midday sweep
#   Mon-Fri 03:30 PM ET  -- Power Hour sweep
#   Sunday  12:00 PM ET  -- Weekly Earnings Preview (all reporters)
#
# Run ONCE as Administrator:
#   powershell -ExecutionPolicy Bypass -File setup_scanner_scheduler.ps1
# ============================================================

# Self-elevate if not running as Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")) {
    Write-Host "Not running as Administrator. Re-launching elevated..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$PythonExe = (python -c "import sys; print(sys.executable)" 2>$null)
if (-not $PythonExe) {
    Write-Error "Python not found on PATH. Install Python and retry."
    exit 1
}

$ScriptPath     = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging\_run_full_stack.py'
$EarningsScript = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging\_run_sunday_earnings.py'
$LogDir         = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging\logs'
$WorkDir        = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 90) `
    -MultipleInstances  IgnoreNew `
    -StartWhenAvailable

$Principal = New-ScheduledTaskPrincipal `
    -UserId    $env:USERNAME `
    -LogonType Interactive `
    -RunLevel  Highest

function Register-QMatrixTask {
    param(
        [string]$TaskName,
        [string]$FireTime,
        [string]$Label,
        [string]$LogFile
    )

    # Build the argument string for cmd.exe — use single backslash paths
    $Arg = "/c " + $PythonExe + " -u " + $ScriptPath + " >> " + $LogFile + " 2>&1"

    $Action = New-ScheduledTaskAction `
        -Execute          "cmd.exe" `
        -Argument         $Arg `
        -WorkingDirectory $WorkDir

    $Trigger = New-ScheduledTaskTrigger `
        -Weekly `
        -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
        -At $FireTime

    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    $Params = @{
        TaskName    = $TaskName
        Action      = $Action
        Trigger     = $Trigger
        Settings    = $Settings
        Principal   = $Principal
        Description = "Q-Matrix - $Label sweep to Discord (Mon-Fri)."
    }
    Register-ScheduledTask @Params | Out-Null

    Write-Host "  [OK] $TaskName  --  fires $Label" -ForegroundColor Green
}

function Register-EarningsTask {
    $LogFile = $LogDir + '\scanner_earnings_sunday.log'
    $Arg = "/c " + $PythonExe + " -u " + $EarningsScript + " >> " + $LogFile + " 2>&1"

    $Action = New-ScheduledTaskAction `
        -Execute          "cmd.exe" `
        -Argument         $Arg `
        -WorkingDirectory $WorkDir

    $Trigger = New-ScheduledTaskTrigger `
        -Weekly `
        -DaysOfWeek Sunday `
        -At "12:00PM"

    Unregister-ScheduledTask -TaskName "QMatrix_SundayEarnings" -Confirm:$false -ErrorAction SilentlyContinue

    $Params = @{
        TaskName    = "QMatrix_SundayEarnings"
        Action      = $Action
        Trigger     = $Trigger
        Settings    = $Settings
        Principal   = $Principal
        Description = "Q-Matrix Sunday Earnings Preview - posts weekly earnings calendar."
    }
    Register-ScheduledTask @Params | Out-Null

    Write-Host "  [OK] QMatrix_SundayEarnings  --  fires Sunday 12:00 PM" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Q-MATRIX  v4.0  --  REGISTERING 4 SCHEDULED TASKS"         -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Register-QMatrixTask `
    -TaskName "QMatrix_Open" `
    -FireTime "09:30AM" `
    -Label    "Market Open 09:30 ET" `
    -LogFile  ($LogDir + '\scanner_open.log')

Register-QMatrixTask `
    -TaskName "QMatrix_Midday" `
    -FireTime "12:00PM" `
    -Label    "Midday 12:00 ET" `
    -LogFile  ($LogDir + '\scanner_midday.log')

Register-QMatrixTask `
    -TaskName "QMatrix_PowerHour" `
    -FireTime "03:30PM" `
    -Label    "Power Hour 15:30 ET" `
    -LogFile  ($LogDir + '\scanner_powerhour.log')

Register-EarningsTask

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ALL 4 TASKS REGISTERED" -ForegroundColor Green
Write-Host ""
Write-Host "  Mon-Fri 09:30  -> QMatrix_Open"          -ForegroundColor White
Write-Host "  Mon-Fri 12:00  -> QMatrix_Midday"        -ForegroundColor White
Write-Host "  Mon-Fri 15:30  -> QMatrix_PowerHour"     -ForegroundColor White
Write-Host "  Sunday  12:00  -> QMatrix_SundayEarnings" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Logs -> $LogDir" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To remove all tasks:" -ForegroundColor Yellow
Write-Host '  Unregister-ScheduledTask -TaskName QMatrix_Open,QMatrix_Midday,QMatrix_PowerHour,QMatrix_SundayEarnings -Confirm:$false' -ForegroundColor White
