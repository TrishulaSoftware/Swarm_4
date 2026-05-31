# ============================================================
# Q-MATRIX -- TASK RE-REGISTRATION (Run as Administrator)
# ============================================================
# Fixes the "C:\Users\War is not recognized" path bug by
# using the full quoted Python path correctly passed through
# Task Scheduler -> cmd.exe argument chain.
# ============================================================

$PythonExe  = 'C:\Users\War Machine\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$WorkDir    = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging'
$LogDir     = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging\logs'

# Ensure log dir exists
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Register-QTask {
    param($Name, $Script, $LogFile, $DaysOfWeek, $Hour, $Minute)

    # Unregister old version if it exists
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue

    # Build the action — use cmd /c with all paths double-quoted inside the argument string
    $CmdArgs = '/c ""{0}" "{1}\{2}" >> "{3}\{4}" 2>&1"' -f $PythonExe, $WorkDir, $Script, $LogDir, $LogFile
    $Action  = New-ScheduledTaskAction `
        -Execute 'cmd.exe' `
        -Argument $CmdArgs `
        -WorkingDirectory $WorkDir

    # Build trigger
    $Trigger = New-ScheduledTaskTrigger `
        -Weekly `
        -DaysOfWeek $DaysOfWeek `
        -At ('{0}:{1:D2}' -f $Hour, $Minute)

    # Settings — run whether logged on or not
    $Settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable:$false

    $Principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Highest

    Register-ScheduledTask `
        -TaskName $Name `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Force | Out-Null

    $info = Get-ScheduledTaskInfo -TaskName $Name
    Write-Host "  [OK] $Name -> Next: $($info.NextRunTime)"
}

$Weekdays = 'Monday','Tuesday','Wednesday','Thursday','Friday'

Write-Host ""
Write-Host "Registering Q-Matrix tasks..."
Write-Host ""

Register-QTask -Name 'QMatrix_Open'          -Script '_run_full_stack.py'       -LogFile 'scanner_open.log'      -DaysOfWeek $Weekdays           -Hour 9  -Minute 30
Register-QTask -Name 'QMatrix_Midday'        -Script '_run_full_stack.py'       -LogFile 'scanner_midday.log'    -DaysOfWeek $Weekdays           -Hour 12 -Minute 0
Register-QTask -Name 'QMatrix_PowerHour'     -Script '_run_full_stack.py'       -LogFile 'scanner_powerhour.log' -DaysOfWeek $Weekdays           -Hour 15 -Minute 30
Register-QTask -Name 'QMatrix_SundayEarnings'-Script '_run_sunday_earnings.py'  -LogFile 'scanner_sunday.log'    -DaysOfWeek 'Sunday'            -Hour 12 -Minute 0

Write-Host ""
Write-Host "Done. Verifying all 4 tasks:"
Get-ScheduledTask | Where-Object { $_.TaskName -like "QMatrix*" } | 
    ForEach-Object {
        $info = Get-ScheduledTaskInfo -TaskName $_.TaskName
        Write-Host ("  {0,-28} State={1}  Next={2}" -f $_.TaskName, $_.State, $info.NextRunTime)
    }
Write-Host ""
