#requires -RunAsAdministrator
# Campus auto-login autostart: single ONLOGON task, current user, highest privileges,
# battery restriction RESTORED (task will not start while on battery).
# Idempotent: safe to run repeatedly.

$ErrorActionPreference = 'Stop'

function Say($msg) { Write-Host $msg }

# ---- 0. sanity ----
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Say '[ERR] Not elevated. Right-click the .bat and choose "Run as administrator".'
    exit 2
}

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $dir 'campus_login.py'
$taskName = 'CampusLoginAutoLoopPy_Logon'

$oldTasks = @(
    'CampusLoginAutoLoopPy',
    'CampusLoginAutoLoopPy_OnStart_SYSTEM',
    'CampusLoginAutoLoopPy_Watchdog_SYSTEM',
    'CampusLoginAutoLoopPy_OnStart',
    'CampusLoginAutoLoopPy_OnLogon',
    'CampusLoginAutoLoopPy_Watchdog'
)

$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$runValue = 'CampusLoginAutoStart'
$taskDir = 'C:\Windows\System32\Tasks'
$treeRoot = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\Tree'

if (-not (Test-Path -LiteralPath $pyScript)) {
    Say "[ERR] script not found: $pyScript"
    exit 3
}

$pyw = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\pythonw.exe'
if (-not (Test-Path -LiteralPath $pyw)) {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd) { $pyw = $cmd.Source }
}
if (-not (Test-Path -LiteralPath $pyw)) {
    Say '[ERR] pythonw.exe not found'
    exit 4
}

$user = "$env:USERDOMAIN\$env:USERNAME"
Say "[INFO] user   = $user"
Say "[INFO] python = $pyw"
Say "[INFO] script = $pyScript"

# ---- 1. register / update the elevated logon task (battery restriction ON) ----
try {
    $action = New-ScheduledTaskAction -Execute $pyw `
        -Argument ('"' + $pyScript + '" --loop') -WorkingDirectory $dir
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    # battery: do not auto-start on battery, but DO NOT kill a running instance
    # when the charger is unplugged (StopIfGoingOnBatteries=False would be needed
    # to keep running; we intentionally keep the task alive on battery switch).
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew
    $settings.DisallowStartIfOnBatteries = $true
    $settings.StopIfGoingOnBatteries = $false
    $principal = New-ScheduledTaskPrincipal -UserId $user -RunLevel Highest -LogonType Interactive
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Say "[OK] task registered: $taskName"
}
catch {
    Say "[ERR] failed to register task: $($_.Exception.Message)"
    Say '[ABORT] nothing was removed.'
    exit 5
}

$taskFile = Join-Path $taskDir $taskName
if (-not (Test-Path -LiteralPath $taskFile)) {
    Say '[ERR] task file not found after registration.'
    Say '[ABORT] nothing was removed.'
    exit 6
}
$check = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($check) {
    Say "[OK] verify: State=$($check.State) RunAs=$($check.Principal.UserId) RunLevel=$($check.Principal.RunLevel)"
    Say "[OK] battery: DisallowStartIfOnBatteries=$($check.Settings.DisallowStartIfOnBatteries) StopIfGoingOnBatteries=$($check.Settings.StopIfGoingOnBatteries)"
}
else {
    Say '[OK] task file written (enumeration API returned nothing, checking XML instead)'
    $xmlText = Get-Content -LiteralPath $taskFile -Encoding Unicode -Raw
    foreach ($tag in 'DisallowStartIfOnBatteries', 'StopIfGoingOnBatteries', 'RunLevel') {
        $m = [regex]::Match($xmlText, "<$tag>([^<]*)</$tag>")
        if ($m.Success) { Say "[OK] xml $tag = $($m.Groups[1].Value)" }
        else { Say "[??] xml $tag missing" }
    }
}

# ---- 2. remove legacy tasks + orphan TaskCache keys ----
foreach ($n in $oldTasks) {
    $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
    if ($t) {
        Unregister-ScheduledTask -TaskName $n -Confirm:$false
        Say "[OK] removed task: $n"
        continue
    }
    $xmlPath = Join-Path $taskDir $n
    $keyPath = Join-Path $treeRoot $n
    if (Test-Path -LiteralPath $xmlPath) {
        Remove-Item -LiteralPath $xmlPath -Force
        Say "[OK] removed leftover task file: $n"
    }
    if ((Test-Path -LiteralPath $keyPath) -and -not (Test-Path -LiteralPath $xmlPath)) {
        Remove-Item -LiteralPath $keyPath -Recurse -Force
        Say "[OK] removed orphan TaskCache key: $n"
    }
    if (-not (Test-Path -LiteralPath $xmlPath) -and -not (Test-Path -LiteralPath $keyPath)) {
        Say "[--] not present: $n"
    }
}

# ---- 3. remove HKCU Run entry ----
$prop = Get-ItemProperty -Path $runKey -Name $runValue -ErrorAction SilentlyContinue
if ($prop) {
    Remove-ItemProperty -Path $runKey -Name $runValue
    Say "[OK] removed HKCU Run value: $runValue"
}
else {
    Say "[--] not present: HKCU Run\$runValue"
}

# ---- 4. restart under the new task ----
$procs = Get-Process pythonw -ErrorAction SilentlyContinue
if ($procs) {
    $ids = $procs.Id -join ','
    $procs | Stop-Process -Force
    Say "[OK] stopped old pythonw: $ids"
    Start-Sleep -Seconds 2
}

Start-ScheduledTask -TaskName $taskName
Say '[INFO] task started, waiting 8s ...'
Start-Sleep -Seconds 8

$now = Get-Process pythonw -ErrorAction SilentlyContinue
if (-not $now) {
    Say '[WARN] task did not spawn pythonw, falling back to direct launch'
    Start-Process -FilePath $pyw -ArgumentList ('"' + $pyScript + '" --loop') -WorkingDirectory $dir -WindowStyle Hidden
    Start-Sleep -Seconds 6
    $now = Get-Process pythonw -ErrorAction SilentlyContinue
}

# ---- 5. report ----
Say ''
Say '===== RESULT ====='
$t = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$i = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
if ($t) {
    $b1 = $t.Settings.DisallowStartIfOnBatteries
    $b2 = $t.Settings.StopIfGoingOnBatteries
    Say "task      : $taskName  State=$($t.State)  RunLevel=$($t.Principal.RunLevel)  LastResult=$($i.LastTaskResult)"
    Say "battery   : DisallowStart=$b1  StopIfGoingOnBattery=$b2"
}
else {
    $xmlText = Get-Content -LiteralPath $taskFile -Encoding Unicode -Raw
    $b1 = ([regex]::Match($xmlText, '<DisallowStartIfOnBatteries>([^<]*)</')).Groups[1].Value
    $b2 = ([regex]::Match($xmlText, '<StopIfGoingOnBatteries>([^<]*)</')).Groups[1].Value
    Say "task      : $taskName  (not enumerable, read from XML)"
    Say "battery   : DisallowStart=$b1  StopIfGoingOnBattery=$b2"
}
if ($now) {
    foreach ($p in $now) {
        $o = Invoke-CimMethod -InputObject (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)") -MethodName GetOwner
        Say "process   : PID=$($p.Id)  Owner=$($o.Domain)\$($o.User)"
    }
}
else {
    Say 'process   : none (FAILED)'
}

Say ''
Say '--- campus_login.log (tail) ---'
$logPath = Join-Path $dir 'campus_login.log'
if (Test-Path -LiteralPath $logPath) {
    Get-Content -LiteralPath $logPath -Tail 5 -Encoding UTF8 | ForEach-Object { Say $_ }
}
else {
    Say '(no log yet)'
}

Say ''
Say '--- leftover check ---'
$left = Get-ScheduledTask | Where-Object { $_.TaskName -match 'CampusLogin' } | Select-Object -ExpandProperty TaskName
if ($left) { Say ('tasks: ' + ($left -join ', ')) } else { Say 'tasks: (none)' }
$files = Get-ChildItem -LiteralPath $taskDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'CampusLogin' } | Select-Object -ExpandProperty Name
if ($files) { Say ('task files: ' + ($files -join ', ')) } else { Say 'task files: (none)' }
$rv = (Get-ItemProperty -Path $runKey).$runValue
if ($rv) { Say "HKCU Run\$runValue = $rv" } else { Say "HKCU Run\$runValue = (absent)" }
Say '=================='
