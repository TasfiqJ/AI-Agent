# ============================================================
#  test-guardian - one command to scan any API project
#
#  Usage:
#    .\test-guardian -Dashboard        Open web dashboard
#    .\test-guardian <path>            Scan & show endpoints
#    .\test-guardian <path> -Run       Scan + generate tests
#    .\test-guardian <path> -Trust     Scan + auto-approve tests
#    .\test-guardian -Eval             Evaluate demo repos
#    .\test-guardian -Full             Evaluate all repos + checkpoint
#    .\test-guardian -Help             Show help
# ============================================================

param(
    [Parameter(Position=0)]
    [string]$Path,

    [switch]$Run,
    [switch]$Trust,
    [Alias("ui", "web")]
    [switch]$Dashboard,
    [switch]$Eval,
    [switch]$Full,
    [switch]$Status,
    [switch]$Revert,
    [Alias("h")]
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AgentDir = Join-Path $Root "agent"
$CLI = Join-Path $Root "packages\cli\src\index.tsx"
$BackendUrl = "http://127.0.0.1:8000"
$DashboardUrl = "$BackendUrl/dashboard/"

# --Helpers ------------------------------------------------

function Write-Header {
    Write-Host ""
    Write-Host "  test-guardian" -ForegroundColor Cyan -NoNewline
    Write-Host " v0.1.0" -ForegroundColor DarkGray
}

function Test-Backend {
    try {
        $response = Invoke-WebRequest -Uri "$BackendUrl/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Start-Backend {
    if (Test-Backend) {
        Write-Host "  Backend:  " -NoNewline
        Write-Host "Connected" -ForegroundColor Green
        return
    }

    Write-Host "  Backend:  " -NoNewline
    Write-Host "Starting..." -ForegroundColor Yellow

    # Start backend in background
    $job = Start-Process -FilePath "python" `
        -ArgumentList "-m", "uvicorn", "guardian.server:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $AgentDir `
        -WindowStyle Hidden `
        -PassThru

    # Wait up to 15 seconds
    $attempts = 0
    while ($attempts -lt 30) {
        Start-Sleep -Milliseconds 500
        if (Test-Backend) {
            Write-Host "  Backend:  " -NoNewline
            Write-Host "Ready" -ForegroundColor Green
            return
        }
        $attempts++
    }

    Write-Host ""
    Write-Host "  Error: Backend failed to start." -ForegroundColor Red
    Write-Host "  Try manually: cd agent && uvicorn guardian.server:app --reload" -ForegroundColor DarkGray
    Write-Host ""
    exit 1
}

function Show-Help {
    Write-Host ""
    Write-Host "  test-guardian" -ForegroundColor Cyan -NoNewline
    Write-Host " - Agentic API test generator" -ForegroundColor White
    Write-Host ""
    Write-Host "  USAGE:" -ForegroundColor White
    Write-Host "    .\test-guardian -Dashboard         " -ForegroundColor Yellow -NoNewline
    Write-Host "Open web dashboard in browser"
    Write-Host '    .\test-guardian <path>             ' -ForegroundColor Yellow -NoNewline
    Write-Host "Scan project, show detected endpoints"
    Write-Host '    .\test-guardian <path> -Run        ' -ForegroundColor Yellow -NoNewline
    Write-Host "Scan + generate tests (with approval)"
    Write-Host '    .\test-guardian <path> -Trust      ' -ForegroundColor Yellow -NoNewline
    Write-Host "Scan + generate tests (auto-approve)"
    Write-Host "    .\test-guardian -Eval              " -ForegroundColor Yellow -NoNewline
    Write-Host "Evaluate against 3 demo repos"
    Write-Host "    .\test-guardian -Full              " -ForegroundColor Yellow -NoNewline
    Write-Host "Evaluate all repos + checkpoint"
    Write-Host "    .\test-guardian -Status            " -ForegroundColor Yellow -NoNewline
    Write-Host "Show status of last run"
    Write-Host "    .\test-guardian -Revert            " -ForegroundColor Yellow -NoNewline
    Write-Host "Revert changes from last run"
    Write-Host ""
    Write-Host "  EXAMPLES:" -ForegroundColor White
    Write-Host "    .\test-guardian -Dashboard" -ForegroundColor DarkGray
    Write-Host "    .\test-guardian .\demo\flask-todo-api" -ForegroundColor DarkGray
    Write-Host "    .\test-guardian .\demo\fastapi-notes -Run" -ForegroundColor DarkGray
    Write-Host "    .\test-guardian C:\path\to\my-api -Trust" -ForegroundColor DarkGray
    Write-Host ""
}

# --Main ------------------------------------------------

if ($Help) {
    Show-Help
    exit 0
}

# Dashboard mode
if ($Dashboard) {
    Write-Header
    Write-Host "  Mode:     " -NoNewline
    Write-Host "Web Dashboard" -ForegroundColor Cyan
    Write-Host ""
    Start-Backend
    Write-Host ""
    Write-Host "  Dashboard: " -NoNewline
    Write-Host $DashboardUrl -ForegroundColor Cyan
    Write-Host "  Press Ctrl+C to stop." -ForegroundColor DarkGray
    Write-Host ""
    Start-Process $DashboardUrl
    # Keep alive so the user can Ctrl+C to stop
    while ($true) { Start-Sleep -Seconds 60 }
}

# Eval modes
if ($Eval) {
    Write-Header
    Write-Host "  Mode:     " -NoNewline
    Write-Host "Demo Evaluation (3 repos)" -ForegroundColor Magenta
    Write-Host ""
    Start-Backend
    Write-Host ""
    Push-Location $Root
    python eval\run_eval.py
    Pop-Location
    exit $LASTEXITCODE
}

if ($Full) {
    Write-Header
    Write-Host "  Mode:     " -NoNewline
    Write-Host "Full Evaluation (all repos + checkpoint)" -ForegroundColor Magenta
    Write-Host ""
    Start-Backend
    Write-Host ""
    Push-Location $Root
    python eval\run_eval.py --full
    Pop-Location
    exit $LASTEXITCODE
}

# Status / Revert
if ($Status) {
    Start-Backend
    Push-Location $Root
    npx tsx $CLI status
    Pop-Location
    exit 0
}

if ($Revert) {
    Start-Backend
    Push-Location $Root
    npx tsx $CLI revert
    Pop-Location
    exit 0
}

# Require a path for scan/run/trust
if (-not $Path) {
    Show-Help
    exit 0
}

# Resolve to absolute path
if (-not (Test-Path $Path)) {
    Write-Host ""
    Write-Host "  Error: " -ForegroundColor Red -NoNewline
    Write-Host "Path not found: $Path"
    Write-Host ""
    exit 1
}
$TargetPath = (Resolve-Path $Path).Path

Write-Header
Write-Host "  Scanning: " -NoNewline
Write-Host $TargetPath -ForegroundColor White
Write-Host ""

Start-Backend
Write-Host ""

if ($Trust) {
    Write-Host "  Mode:     " -NoNewline
    Write-Host "Trust (auto-approve all changes)" -ForegroundColor Yellow
    Write-Host ""
    Push-Location $TargetPath
    npx tsx $CLI run --trust
    Pop-Location
    exit $LASTEXITCODE
}

if ($Run) {
    Write-Host "  Mode:     " -NoNewline
    Write-Host "Plan -> Act -> Verify" -ForegroundColor Magenta
    Write-Host ""
    Push-Location $TargetPath
    npx tsx $CLI run
    Pop-Location
    exit $LASTEXITCODE
}

# Default: just scan
Push-Location $Root
npx tsx $CLI init $TargetPath
Pop-Location
