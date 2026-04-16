param(
    [string]$ExePath = "",
    [string]$ConfigPath = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $ExePath) {
    $candidateA = Join-Path $scriptDir "campus_login.exe"
    $candidateB = Join-Path $scriptDir "dist\\campus_login.exe"
    if (Test-Path -LiteralPath $candidateA) {
        $ExePath = $candidateA
    }
    elseif (Test-Path -LiteralPath $candidateB) {
        $ExePath = $candidateB
    }
}

if (-not $ExePath -or -not (Test-Path -LiteralPath $ExePath)) {
    throw "campus_login.exe not found. Expected '$scriptDir\\campus_login.exe' or '$scriptDir\\dist\\campus_login.exe'"
}

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $scriptDir "config.yaml"
}

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "config.yaml not found: $ConfigPath"
}

$resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
$resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$exeFileName = [System.IO.Path]::GetFileName($resolvedExe)

try {
    $running = Get-CimInstance Win32_Process -Filter "Name='$exeFileName'" -ErrorAction Stop | Where-Object {
        $_.ExecutablePath -eq $resolvedExe -and $_.CommandLine -like "*--loop*"
    }
    if ($running) {
        Write-Output "[INFO] Already running: $resolvedExe --loop"
        exit 0
    }
}
catch {
    # Continue startup if process enumeration is restricted.
}

$env:CAMPUS_CONFIG_FILE = $resolvedConfig
$workDir = Split-Path -Parent $resolvedExe

Start-Process -FilePath $resolvedExe -ArgumentList @("--loop") -WorkingDirectory $workDir -WindowStyle Hidden
Write-Output "[OK] Started hidden: $resolvedExe --loop"
