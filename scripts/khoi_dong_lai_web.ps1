param([int[]]$Ports = @(8501, 8502), [switch]$ChiDung)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtimePath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$webLogDir = Join-Path $projectRoot 'logs'
New-Item -ItemType Directory -Path $webLogDir -Force | Out-Null
foreach ($webPort in $Ports) {
    $owners = @(Get-NetTCPConnection -LocalPort $webPort -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($ownerId in $owners) {
        $ownerInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerId"
        $parentInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($ownerInfo.ParentProcessId)"
        if ($ownerInfo.CommandLine -notmatch '-m\s+streamlit\s+run\s+app\.py' -or
            ($ownerInfo.ExecutablePath -ne $runtimePath -and $parentInfo.ExecutablePath -ne $runtimePath)) {
            throw "Port $webPort belongs to another application; leaving it untouched."
        }
        Stop-Process -Id $ownerId -Force
        if ($parentInfo.ExecutablePath -eq $runtimePath -and $parentInfo.CommandLine -match '-m\s+streamlit\s+run\s+app\.py') {
            Stop-Process -Id $parentInfo.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    if ($ChiDung) {
        Write-Output "Chatbot stopped safely on port $webPort"
        continue
    }
    $webArgs = @('-m', 'streamlit', 'run', 'app.py', '--server.port', "$webPort", '--server.address', '127.0.0.1', '--server.headless', 'true')
    Start-Process -FilePath $runtimePath -ArgumentList $webArgs -WorkingDirectory $projectRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $webLogDir "web_${webPort}_stdout.log") `
        -RedirectStandardError (Join-Path $webLogDir "web_${webPort}_stderr.log")
    $healthy = $false
    $lastHealthError = ''
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$webPort/_stcore/health" -UseBasicParsing -NoProxy -TimeoutSec 3
            if ($response.StatusCode -eq 200) { $healthy = $true; break }
        } catch { $lastHealthError = $_.Exception.Message; Start-Sleep -Milliseconds 500 }
    }
    if (-not $healthy) { throw "Web port $webPort did not become healthy: $lastHealthError. See logs." }
    Write-Output "Chatbot restarted and healthy: http://localhost:$webPort"
}
