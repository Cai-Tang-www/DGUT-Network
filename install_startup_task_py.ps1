param(
    [string]$TaskName = "CampusLoginAutoLoopPy",
    [string]$LauncherPath = "",
    [int]$Interval = 0,
    [switch]$AtStartupSystem
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $LauncherPath) {
    $LauncherPath = Join-Path $scriptDir "start_hidden_py.ps1"
}
if (-not (Test-Path -LiteralPath $LauncherPath)) {
    throw "Launcher script not found: $LauncherPath"
}

$resolvedLauncher = (Resolve-Path -LiteralPath $LauncherPath).Path
$powershellExe = "$env:WINDIR\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$resolvedLauncher`""
if ($Interval -gt 0) {
    $arguments += " -Interval $Interval"
}

$action = New-ScheduledTaskAction -Execute $powershellExe -Argument $arguments
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

if ($AtStartupSystem) {
    $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
    if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "AtStartupSystem mode requires Administrator PowerShell."
    }

    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
}
else {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
    $principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Highest
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Output "[OK] Installed task: $TaskName"
if ($AtStartupSystem) {
    Write-Output "[INFO] Mode: AtStartup + SYSTEM"
}
else {
    Write-Output "[INFO] Mode: AtLogOn + CurrentUser"
}
Write-Output "[INFO] View task:   Get-ScheduledTask -TaskName `"$TaskName`""
Write-Output "[INFO] Delete task: Unregister-ScheduledTask -TaskName `"$TaskName`" -Confirm:`$false"
