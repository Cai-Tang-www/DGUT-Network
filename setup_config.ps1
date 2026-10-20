# Generate config.yaml from config.yaml.example.
# Inputs come from environment variables CU_USER / CU_PASS (avoids quoting issues).
# ASCII only; output is UTF-8 without BOM.

$ErrorActionPreference = 'Stop'

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$tpl = Join-Path $dir 'config.yaml.example'
$out = Join-Path $dir 'config.yaml'

if (-not (Test-Path -LiteralPath $tpl)) {
    Write-Host "[ERR] template not found: $tpl"
    exit 3
}

$user = $env:CU_USER
$pass = $env:CU_PASS
if ([string]::IsNullOrWhiteSpace($user) -or [string]::IsNullOrWhiteSpace($pass)) {
    Write-Host '[ERR] CU_USER / CU_PASS not set'
    exit 4
}

$text = [IO.File]::ReadAllText($tpl, [Text.Encoding]::UTF8)
$lines = [IO.File]::ReadAllLines($tpl, [Text.Encoding]::UTF8)
$seenUser = $false
$seenPass = $false
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^user_id:') {
        $lines[$i] = 'user_id: "' + $user + '"'
        $seenUser = $true
    }
    elseif ($lines[$i] -match '^password:') {
        $lines[$i] = 'password: "' + $pass + '"'
        $seenPass = $true
    }
}

if (-not $seenUser -or -not $seenPass) {
    Write-Host '[ERR] template missing user_id / password line'
    exit 5
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines($out, $lines, $utf8)

if ($pass.Contains('"')) {
    Write-Host '[WARN] password contains a double quote; YAML quoting may break, edit config.yaml manually.'
}

Write-Host "[OK] config.yaml written (user_id=$user)"
exit 0
