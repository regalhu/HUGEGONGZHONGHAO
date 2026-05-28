$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null
$LogPath = Join-Path $LogDir "run_daily.log"
$LockDir = Join-Path $ProjectRoot ".run_daily.lock"
$StaleLockMinutes = 20

function Write-RunLog {
  param([string]$Message)
  $Line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
  Add-Content -LiteralPath $LogPath -Value $Line -Encoding UTF8
  Write-Host $Line
}

function Complete-Run {
  param([int]$Code)
  if (Test-Path $LockDir) {
    Remove-Item -LiteralPath $LockDir -Force
  }
  exit $Code
}

if (Test-Path $LockDir) {
  $Lock = Get-Item -LiteralPath $LockDir
  $LockAgeMinutes = ((Get-Date) - $Lock.LastWriteTime).TotalMinutes
  if ($LockAgeMinutes -gt $StaleLockMinutes) {
    Remove-Item -LiteralPath $LockDir -Force
    Write-RunLog "Removed stale lock age_minutes=$([math]::Round($LockAgeMinutes, 1))"
  }
}

try {
  New-Item -ItemType Directory -Path $LockDir -ErrorAction Stop | Out-Null
} catch {
  Write-RunLog "Another run is already active, skip."
  exit 0
}

try {
  $PublicIp = (Invoke-RestMethod https://api.ipify.org -TimeoutSec 15)
  Write-RunLog "Started run_daily.ps1 public_ip=$PublicIp"
} catch {
  Write-RunLog "Started run_daily.ps1 public_ip_check_failed=$($_.Exception.Message)"
}

$Today = Get-Date -Format "yyyy-MM-dd"
$MetadataPath = Join-Path $ProjectRoot "outputs\$Today\metadata.json"
if (Test-Path $MetadataPath) {
  $Metadata = Get-Content $MetadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($Metadata.draft_media_id) {
    $DraftMediaId = $Metadata.draft_media_id
    Write-RunLog "Draft already exists today, skip upload: $DraftMediaId"
    Complete-Run 0
  }
}

if (Test-Path ".venv\Scripts\python.exe") {
  $Python = ".venv\Scripts\python.exe"
} else {
  $Python = "python"
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
Write-RunLog "Running generator with $Python"
& $Python -m huge_catering.cli --upload-draft *>&1 | Tee-Object -FilePath $LogPath -Append
$ExitCode = $LASTEXITCODE
Write-RunLog "Finished generator exit_code=$ExitCode"
Complete-Run $ExitCode
