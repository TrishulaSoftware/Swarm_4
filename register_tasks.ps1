# Q-Matrix Task Scheduler Registration
# Run this script directly as Administrator

$PythonExe  = (& python -c "import sys; print(sys.executable)")
$LogDir     = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging\logs'
$WorkDir    = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging'
$FullStack  = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging\_run_full_stack.py'
$EarnScript = 'H:\Trishula\Swarm_4_Integration\Salvo_Staging\_run_sunday_earnings.py'

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 90) -MultipleInstances IgnoreNew -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

$Weekdays = @('Monday','Tuesday','Wednesday','Thursday','Friday')

# --- QMatrix_Open: 9:30 AM Mon-Fri ---
$LogOpen = $LogDir + '\scanner_open.log'
$ArgOpen = '/c ' + $PythonExe + ' -u ' + $FullStack + ' >> ' + $LogOpen + ' 2>&1'
$ActionOpen  = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $ArgOpen -WorkingDirectory $WorkDir
$TriggerOpen = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekdays -At '09:30AM'
Unregister-ScheduledTask -TaskName 'QMatrix_Open' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName 'QMatrix_Open' -Action $ActionOpen -Trigger $TriggerOpen -Settings $Settings -Principal $Principal -Description 'Q-Matrix Market Open 09:30 ET' | Out-Null
Write-Host '  [OK] QMatrix_Open -> Mon-Fri 09:30 AM ET' -ForegroundColor Green

# --- QMatrix_Midday: 12:00 PM Mon-Fri ---
$LogMid = $LogDir + '\scanner_midday.log'
$ArgMid = '/c ' + $PythonExe + ' -u ' + $FullStack + ' >> ' + $LogMid + ' 2>&1'
$ActionMid  = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $ArgMid -WorkingDirectory $WorkDir
$TriggerMid = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekdays -At '12:00PM'
Unregister-ScheduledTask -TaskName 'QMatrix_Midday' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName 'QMatrix_Midday' -Action $ActionMid -Trigger $TriggerMid -Settings $Settings -Principal $Principal -Description 'Q-Matrix Midday 12:00 ET' | Out-Null
Write-Host '  [OK] QMatrix_Midday -> Mon-Fri 12:00 PM ET' -ForegroundColor Green

# --- QMatrix_PowerHour: 3:30 PM Mon-Fri ---
$LogPH = $LogDir + '\scanner_powerhour.log'
$ArgPH = '/c ' + $PythonExe + ' -u ' + $FullStack + ' >> ' + $LogPH + ' 2>&1'
$ActionPH  = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $ArgPH -WorkingDirectory $WorkDir
$TriggerPH = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekdays -At '03:30PM'
Unregister-ScheduledTask -TaskName 'QMatrix_PowerHour' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName 'QMatrix_PowerHour' -Action $ActionPH -Trigger $TriggerPH -Settings $Settings -Principal $Principal -Description 'Q-Matrix Power Hour 15:30 ET' | Out-Null
Write-Host '  [OK] QMatrix_PowerHour -> Mon-Fri 03:30 PM ET' -ForegroundColor Green

# --- QMatrix_SundayEarnings: 12:00 PM Sunday ---
$LogEarn = $LogDir + '\scanner_earnings_sunday.log'
$ArgEarn = '/c ' + $PythonExe + ' -u ' + $EarnScript + ' >> ' + $LogEarn + ' 2>&1'
$ActionEarn  = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $ArgEarn -WorkingDirectory $WorkDir
$TriggerEarn = New-ScheduledTaskTrigger -Weekly -DaysOfWeek 'Sunday' -At '12:00PM'
Unregister-ScheduledTask -TaskName 'QMatrix_SundayEarnings' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName 'QMatrix_SundayEarnings' -Action $ActionEarn -Trigger $TriggerEarn -Settings $Settings -Principal $Principal -Description 'Q-Matrix Sunday Earnings Calendar' | Out-Null
Write-Host '  [OK] QMatrix_SundayEarnings -> Sunday 12:00 PM ET' -ForegroundColor Yellow

Write-Host ''
Write-Host 'Verification:' -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -like 'QMatrix_*' } | Select-Object TaskName, State | Format-Table -AutoSize
