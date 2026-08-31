param(
  [Parameter(Mandatory = $true)]
  [string]$JobPath
)

$ErrorActionPreference = 'Stop'

function Write-UpdateStatus {
  param([string]$State, [string]$Message, [int]$Progress, [string]$Error = '')
  $status = [ordered]@{
    state = $State
    message = $Message
    progress = $Progress
    error = $Error
    updated_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffK')
  }
  $temporary = "$StatusPath.tmp"
  $status | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporary -Encoding UTF8
  Move-Item -LiteralPath $temporary -Destination $StatusPath -Force
}

function Write-UpdateTransaction {
  param([hashtable]$Transaction)
  $Transaction.updated_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffK')
  $temporary = "$TransactionPath.tmp"
  $Transaction | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporary -Encoding UTF8
  Move-Item -LiteralPath $temporary -Destination $TransactionPath -Force
}

function Remove-UpdateTransaction {
  Remove-Item -LiteralPath $TransactionPath -Force -ErrorAction SilentlyContinue
}

function Assert-ProjectChild {
  param([string]$PathValue)
  $resolved = [IO.Path]::GetFullPath($PathValue)
  if (-not $resolved.StartsWith($ProjectRootWithSlash, [StringComparison]::OrdinalIgnoreCase)) {
    throw "更新路径不在项目目录内：$resolved"
  }
  return $resolved
}

function Copy-AllowedRuntime {
  param([string]$SourceRoot, [string]$DestinationRoot)
  foreach ($directory in $AllowedDirectories) {
    $source = Join-Path $SourceRoot $directory
    if (Test-Path -LiteralPath $source) {
      Copy-Item -LiteralPath $source -Destination (Join-Path $DestinationRoot $directory) -Recurse -Force
    }
  }
  foreach ($file in $AllowedFiles) {
    $source = Join-Path $SourceRoot $file
    if (Test-Path -LiteralPath $source) {
      Copy-Item -LiteralPath $source -Destination (Join-Path $DestinationRoot $file) -Force
    }
  }
}

function Replace-Runtime {
  param([string]$SourceRoot)
  foreach ($directory in $AllowedDirectories) {
    $target = Assert-ProjectChild (Join-Path $ProjectRoot $directory)
    if (Test-Path -LiteralPath $target) {
      Remove-Item -LiteralPath $target -Recurse -Force
    }
    $source = Join-Path $SourceRoot $directory
    if (Test-Path -LiteralPath $source) {
      Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
    }
  }
  foreach ($file in $AllowedFiles) {
    $target = Assert-ProjectChild (Join-Path $ProjectRoot $file)
    $source = Join-Path $SourceRoot $file
    if (Test-Path -LiteralPath $source) {
      Copy-Item -LiteralPath $source -Destination $target -Force
    }
  }
}

function Stop-ManagedServer {
  $pidFile = Join-Path $ProjectRoot 'run\server.pid'
  if (-not (Test-Path -LiteralPath $pidFile)) { return }
  $processId = (Get-Content -LiteralPath $pidFile -Raw).Trim()
  if ($processId -match '^\d+$') {
    $process = Get-CimInstance Win32_Process -Filter ("ProcessId = " + $processId) -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -match 'uvicorn app.main:app') {
      Stop-Process -Id ([int]$processId) -Force -ErrorAction SilentlyContinue
      Start-Sleep -Seconds 1
    }
  }
  Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

function Start-ManagedServer {
  $env:SMS_NO_BROWSER = '1'
  try {
    $launcher = Join-Path $ProjectRoot 'start-system.bat'
    $command = 'call "{0}"' -f $launcher
    Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/c', $command) -WorkingDirectory $ProjectRoot -WindowStyle Hidden
  } finally {
    Remove-Item Env:SMS_NO_BROWSER -ErrorAction SilentlyContinue
  }
}

function Wait-ForHealth {
  $python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $python)) { throw '未找到项目虚拟环境，无法执行更新后的健康检查' }
  for ($index = 0; $index -lt 60; $index += 1) {
    try {
      & $python -c "import json, urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=3); payload = json.load(response); raise SystemExit(0 if payload.get('status') == 'ok' else 1)" | Out-Null
      if ($LASTEXITCODE -eq 0) { return }
    } catch {}
    Start-Sleep -Seconds 1
  }
  throw '更新后的服务未能在 60 秒内通过健康检查'
}

function Get-FileHashValue {
  param([string]$PathValue)
  $stream = [IO.File]::OpenRead($PathValue)
  $algorithm = [Security.Cryptography.SHA256]::Create()
  try {
    return -join ($algorithm.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') })
  } finally {
    $algorithm.Dispose()
    $stream.Dispose()
  }
}

$job = Get-Content -LiteralPath $JobPath -Raw | ConvertFrom-Json
$ProjectRoot = [IO.Path]::GetFullPath([string]$job.project_root)
$ProjectRootWithSlash = $ProjectRoot.TrimEnd([char]92) + [char]92
$StatusPath = Assert-ProjectChild ([string]$job.status_path)
$JobDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($JobPath))
$AllowedDirectories = @('app', 'scripts', 'docs')
$AllowedFiles = @('.env.example', 'Dockerfile', 'LICENSE', 'README.md', 'VERSION', 'docker-compose.yml', 'pyproject.toml', 'requirements.lock')
$RollbackDirectory = Assert-ProjectChild (Join-Path $JobDirectory 'rollback')
$StageDirectory = Assert-ProjectChild (Join-Path $JobDirectory 'stage')
$PackagePath = Assert-ProjectChild (Join-Path $JobDirectory 'student-management-update.zip')
$DatabasePath = Join-Path $ProjectRoot 'data\student_management.db'
$DatabaseRollbackPath = Join-Path $RollbackDirectory 'student_management.db'
$TransactionPath = Assert-ProjectChild (Join-Path $ProjectRoot 'run\update-transaction.json')
$RecoverySource = Assert-ProjectChild (Join-Path $ProjectRoot 'scripts\recover-interrupted-update.py')
$RecoveryRuntime = Assert-ProjectChild (Join-Path $ProjectRoot 'run\update-recovery.py')
$serverStopped = $false
$transaction = $null

try {
  Write-UpdateStatus 'downloading' '正在获取更新包并校验 SHA-256' 10
  New-Item -ItemType Directory -Force -Path $JobDirectory | Out-Null
  if ($job.source -eq 'offline') {
    Copy-Item -LiteralPath ([string]$job.offline_package) -Destination $PackagePath -Force
    $expectedHash = [string]$job.offline_checksum
  } else {
    $headers = @{}
    $token = [string]$env:SMS_UPDATE_GITHUB_TOKEN
    $packageUrl = [string]$job.release.package.browser_url
    $checksumUrl = [string]$job.release.checksum.browser_url
    if ($token) {
      $headers['Authorization'] = "Bearer $token"
      $headers['Accept'] = 'application/octet-stream'
      $packageUrl = [string]$job.release.package.url
      $checksumUrl = [string]$job.release.checksum.url
    }
    Invoke-WebRequest -Uri $packageUrl -Headers $headers -OutFile $PackagePath -UseBasicParsing
    $checksumResponse = Invoke-WebRequest -Uri $checksumUrl -Headers $headers -UseBasicParsing
    $checksumContent = if ($checksumResponse.Content -is [byte[]]) { [System.Text.Encoding]::UTF8.GetString($checksumResponse.Content) } else { [string]$checksumResponse.Content }
    $expectedHash = ([regex]::Match($checksumContent, '(?i)[a-f0-9]{64}')).Value.ToLowerInvariant()
  }
  if (-not $expectedHash -or (Get-FileHashValue $PackagePath) -ne $expectedHash.ToLowerInvariant()) {
    throw '更新包 SHA-256 校验失败，已拒绝安装'
  }

  Write-UpdateStatus 'validating' '正在验证更新包清单' 25
  if (Test-Path -LiteralPath $StageDirectory) { Remove-Item -LiteralPath $StageDirectory -Recurse -Force }
  Expand-Archive -LiteralPath $PackagePath -DestinationPath $StageDirectory -Force
  $manifestPath = Join-Path $StageDirectory 'manifest.json'
  if (-not (Test-Path -LiteralPath $manifestPath)) { throw '更新包缺少 manifest.json' }
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if ([int]$manifest.format -ne 1 -or -not $manifest.version) { throw '更新包 manifest 格式无效' }
  foreach ($file in $manifest.files.PSObject.Properties) {
    $candidate = Assert-ProjectChild (Join-Path $StageDirectory ([string]$file.Name))
    if (-not (Test-Path -LiteralPath $candidate) -or (Get-FileHashValue $candidate) -ne ([string]$file.Value).ToLowerInvariant()) {
      throw "更新包文件校验失败：$($file.Name)"
    }
  }
  foreach ($item in (Get-ChildItem -LiteralPath $StageDirectory -Force)) {
    if ($item.Name -notin @($AllowedDirectories + $AllowedFiles + 'manifest.json')) {
      throw "更新包包含未允许的路径：$($item.Name)"
    }
  }

  Write-UpdateStatus 'backing_up' '正在保存更新前代码和数据库副本' 40
  New-Item -ItemType Directory -Force -Path $RollbackDirectory | Out-Null
  Copy-AllowedRuntime $ProjectRoot $RollbackDirectory
  if (Test-Path -LiteralPath $RecoverySource) { Copy-Item -LiteralPath $RecoverySource -Destination $RecoveryRuntime -Force }
  $transaction = [ordered]@{
    format = 1
    job_id = [string]$job.job_id
    state = 'prepared'
    project_root = $ProjectRoot
    rollback_directory = $RollbackDirectory
    database_path = $DatabasePath
    database_rollback_path = $DatabaseRollbackPath
  }
  Write-UpdateTransaction $transaction

  Write-UpdateStatus 'applying' '正在停止服务并替换程序文件' 55
  $transaction.state = 'applying'
  Write-UpdateTransaction $transaction
  Stop-ManagedServer
  $serverStopped = $true
  if (Test-Path -LiteralPath $DatabasePath) { Copy-Item -LiteralPath $DatabasePath -Destination $DatabaseRollbackPath -Force }
  Replace-Runtime $StageDirectory

  Write-UpdateStatus 'installing' '正在更新依赖并升级数据库结构' 70
  $transaction.state = 'installing'
  Write-UpdateTransaction $transaction
  $Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $Python)) { throw '未找到项目虚拟环境，请先运行 setup.bat' }
  & $Python -m pip install --disable-pip-version-check -r (Join-Path $ProjectRoot 'requirements.lock')
  if ($LASTEXITCODE -ne 0) { throw 'Python 依赖更新失败' }
  & $Python -m pip install --disable-pip-version-check --no-deps -e $ProjectRoot
  if ($LASTEXITCODE -ne 0) { throw '项目本体安装失败' }
  & $Python -c 'from app.db import init_db; init_db()'
  if ($LASTEXITCODE -ne 0) { throw '数据库升级失败' }

  Write-UpdateStatus 'restarting' '正在重新启动服务并等待健康检查' 88
  $transaction.state = 'restarting'
  Write-UpdateTransaction $transaction
  Start-ManagedServer
  Wait-ForHealth
  Remove-UpdateTransaction
  Write-UpdateStatus 'completed' ("已更新至 v" + [string]$manifest.version) 100
  exit 0
} catch {
  $failure = $_.Exception.Message
  Write-UpdateStatus 'rolling_back' '更新失败，正在恢复上一版本' 92 $failure
  try {
    if ($transaction) {
      $transaction.state = 'rolling_back'
      Write-UpdateTransaction $transaction
    }
    if ($serverStopped) { Stop-ManagedServer }
    if (Test-Path -LiteralPath $RollbackDirectory) {
      Replace-Runtime $RollbackDirectory
      if (Test-Path -LiteralPath $DatabaseRollbackPath) { Copy-Item -LiteralPath $DatabaseRollbackPath -Destination $DatabasePath -Force }
      $Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
      if (Test-Path -LiteralPath $Python) {
        & $Python -m pip install --disable-pip-version-check --no-deps -e $ProjectRoot | Out-Null
      }
      Start-ManagedServer
      Wait-ForHealth
      Remove-UpdateTransaction
      Write-UpdateStatus 'rolled_back' '更新失败，已自动恢复上一版本' 100 $failure
    } else {
      Write-UpdateStatus 'failed' '更新失败，未找到代码回滚副本' 100 $failure
    }
  } catch {
    Write-UpdateStatus 'failed' '更新失败，自动回滚也未完成，请使用更新前备份恢复' 100 ($failure + '；回滚错误：' + $_.Exception.Message)
  }
  exit 1
}
