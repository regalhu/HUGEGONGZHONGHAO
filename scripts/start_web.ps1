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

try {
  $Health = Invoke-WebRequest "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 3
  if ($Health.StatusCode -eq 200) {
    Write-WebLog "Web dashboard already running on port=$Port"
    exit 0
  }
} catch {
  Write-WebLog "Web dashboard not running, starting port=$Port"
}

if (Test-Path ".venv\Scripts\python.exe") {
  $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
} else {
  $Python = "python"
}

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

Start-Sleep -Seconds 3

try {
  $Health = Invoke-WebRequest "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 5
  Write-WebLog "Web dashboard started port=$Port status=$($Health.StatusCode)"
  exit 0
} catch {
  Write-WebLog "Web dashboard failed to start port=$Port error=$($_.Exception.Message)"
  exit 1
}
