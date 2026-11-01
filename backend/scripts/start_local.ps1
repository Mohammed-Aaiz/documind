param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$backendDir = Split-Path -Parent $PSScriptRoot
$projectDir = Split-Path -Parent $backendDir
$pythonExe = Join-Path $backendDir 'venv/Scripts/python.exe'
$viteScript = Join-Path $projectDir 'node_modules/vite/bin/vite.js'
$dbHelper = Join-Path $PSScriptRoot 'local_database_ops.py'

foreach ($requiredPath in @($pythonExe, $viteScript, $dbHelper)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required existing dependency is missing: $requiredPath. Run the documented setup first."
    }
}
$nodeExe = (Get-Command node.exe -ErrorAction Stop).Source
if ($CheckOnly) {
    Write-Output 'Existing Python, Node, Vite and database startup helper found. No process was started.'
    exit 0
}

# Only the existing verified cluster can be started. No init/reset, dependency
# installation, environment-file changes, service registration or OS autostart.
& $pythonExe $dbHelper start
if ($LASTEXITCODE -ne 0) { throw 'Database startup was refused; see the local database logs.' }
$databaseReady = $false
for ($attempt = 0; $attempt -lt 120; $attempt++) {
    & $pythonExe $dbHelper verify *> $null
    if ($LASTEXITCODE -eq 0) { $databaseReady = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $databaseReady) { throw 'The existing database is not ready. No reset was attempted.' }

$apiListener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $apiListener) {
    Start-Process -FilePath $pythonExe -ArgumentList '-B','-m','uvicorn','main:app','--host','127.0.0.1','--port','8000' `
        -WorkingDirectory $backendDir -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $backendDir 'api-runtime.log') `
        -RedirectStandardError (Join-Path $backendDir 'api-runtime-error.log')
}
$apiReady = $false
for ($attempt = 0; $attempt -lt 120; $attempt++) {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        if ($health.service -ne 'documind-api') { throw 'Port 8000 belongs to another service.' }
        if ($health.status -eq 'healthy') { $apiReady = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
}
if (-not $apiReady) { throw 'DocuMind API did not become healthy. Existing listeners were never stopped.' }

$webListener = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if (-not $webListener) {
    Start-Process -FilePath $nodeExe -ArgumentList "`"$viteScript`"",'--host','127.0.0.1','--port','3000','--strictPort' `
        -WorkingDirectory $projectDir -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $backendDir 'frontend-runtime.log') `
        -RedirectStandardError (Join-Path $backendDir 'frontend-runtime-error.log')
}
$webReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $page = Invoke-WebRequest 'http://127.0.0.1:3000/' -TimeoutSec 2 -UseBasicParsing
        if ($page.StatusCode -eq 200 -and $page.Content -match 'DocuMind') { $webReady = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
}
if (-not $webReady) { throw 'DocuMind frontend is unavailable on 3000. No existing listener was stopped.' }
Write-Output 'DocuMind is ready at http://127.0.0.1:3000/. Logs are under backend/. Keep credentials in the existing server environment.'
