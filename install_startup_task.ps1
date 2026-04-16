param(
    [string]$TaskName = "CampusLoginAutoLoop",
    [string]$LauncherPath = ""
)

$ErrorActionPreference = "Stop"

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Please run this script as Administrator."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $LauncherPath) {
    $LauncherPath = Join-Path $scriptDir "start_hidden.ps1"
}

if (-not (Test-Path -LiteralPath $LauncherPath)) {
    throw "Launcher script not found: $LauncherPath"
}

$resolvedLauncher = (Resolve-Path -LiteralPath $LauncherPath).Path
$powershellExe = "$env:WINDIR\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$resolvedLauncher`""

$action = New-ScheduledTaskAction -Execute $powershellExe -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Output "[OK] Installed startup task: $TaskName"
Write-Output "[INFO] View task:   Get-ScheduledTask -TaskName `"$TaskName`""
Write-Output "[INFO] Delete task: Unregister-ScheduledTask -TaskName `"$TaskName`" -Confirm:`$false"
