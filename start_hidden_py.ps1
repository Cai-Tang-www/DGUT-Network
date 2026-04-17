param(
    [string]$PyPath = "",
    [string]$ScriptPath = "",
    [string]$ConfigPath = "",
    [int]$Interval = 0
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $ScriptPath) {
    $ScriptPath = Join-Path $scriptDir "campus_login.py"
}
if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "campus_login.py not found: $ScriptPath"
}

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $scriptDir "config.yaml"
}
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "config.yaml not found: $ConfigPath"
}

if (-not $PyPath) {
    try {
        $pyCmd = Get-Command py -ErrorAction Stop
        $PyPath = $pyCmd.Source
    }
    catch {
        try {
            $pythonCmd = Get-Command python -ErrorAction Stop
            $PyPath = $pythonCmd.Source
        }
        catch {
            throw "Python launcher not found. Please install Python or pass -PyPath explicitly."
        }
    }
}

if (-not (Test-Path -LiteralPath $PyPath)) {
    throw "Python executable not found: $PyPath"
}

$resolvedPy = (Resolve-Path -LiteralPath $PyPath).Path
$resolvedScript = (Resolve-Path -LiteralPath $ScriptPath).Path
$resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$workDir = Split-Path -Parent $resolvedScript

try {
    $running = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        ($_.Name -in @("python.exe", "pythonw.exe", "py.exe")) -and
        $_.CommandLine -like "*$resolvedScript*" -and
        $_.CommandLine -like "*--loop*"
    }
    if ($running) {
        Write-Output "[INFO] Already running: $resolvedScript --loop"
        exit 0
    }
}
catch {
    # Continue startup if process enumeration is restricted.
}

$env:CAMPUS_CONFIG_FILE = $resolvedConfig
$arguments = @($resolvedScript, "--loop")
if ($Interval -gt 0) {
    $arguments += @("--interval", "$Interval")
}

Start-Process -FilePath $resolvedPy -ArgumentList $arguments -WorkingDirectory $workDir -WindowStyle Hidden
Write-Output "[OK] Started hidden: $resolvedPy $($arguments -join ' ')"
