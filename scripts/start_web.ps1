$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "logs"
$LogPath = Join-Path $LogDir "web.log"
$Port = if ($env:WEB_PORT) { [int]$env:WEB_PORT } else { 8766 }

New-Item -ItemType Directory -Force $LogDir | Out-Null
Set-Location $ProjectRoot

function Write-WebLog {
  param([string]$Message)
  $Line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
  Add-Content -LiteralPath $LogPath -Value $Line -Encoding UTF8
  Write-Host $Line
}

Write-WebLog "start_web.ps1 invoked project=$ProjectRoot port=$Port"

try {
  $Health = Invoke-WebRequest "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 3
  if ($Health.StatusCode -eq 200) {
    Write-WebLog "Web dashboard already running on port=$Port"
    exit 0
  }
} catch {
  Write-WebLog "Web dashboard not running, starting port=$Port"
}

if (Test-Path ".venv\Scripts\pythonw.exe") {
  $Python = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
} elseif (Test-Path ".venv\Scripts\python.exe") {
  $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
} else {
  $Python = "python"
}

Write-WebLog "Launching web dashboard with python=$Python"

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$OutputLog = Join-Path $LogDir "web.stdout.log"
$ErrorLog = Join-Path $LogDir "web.stderr.log"

Start-Process `
  -FilePath $Python `
  -ArgumentList "-m", "huge_catering.webapp", "--host", "127.0.0.1", "--port", "$Port" `
  -WorkingDirectory $ProjectRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput $OutputLog `
  -RedirectStandardError $ErrorLog

for ($Attempt = 1; $Attempt -le 15; $Attempt++) {
  Start-Sleep -Seconds 2
  try {
    $Health = Invoke-WebRequest "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 5
    Write-WebLog "Web dashboard started port=$Port status=$($Health.StatusCode) attempt=$Attempt"
    exit 0
  } catch {
    Write-WebLog "Waiting for web dashboard port=$Port attempt=$Attempt error=$($_.Exception.Message)"
  }
}

Write-WebLog "Web dashboard failed to start port=$Port after=30s"
exit 1
