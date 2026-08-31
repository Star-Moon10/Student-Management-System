param(
    [string]$Model = 'student-qwen:latest'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDirectory = Join-Path $ProjectRoot 'tools\ollama'
$Runtime = Join-Path $RuntimeDirectory 'ollama.exe'
$ModelPath = Join-Path $ProjectRoot 'models\ollama'
$ModelImportDirectory = Join-Path $ProjectRoot 'models\imports'
$ModelFile = Join-Path $ModelImportDirectory 'Qwen2.5-7B-Instruct-Q5_K_M.gguf'
$ModelFileDefinition = Join-Path $ModelImportDirectory 'Modelfile'
$CudaModel = 'student-qwen-cuda:latest'
$CudaModelDefinition = Join-Path $ProjectRoot 'models\cuda.Modelfile'
$TemporaryDirectory = Join-Path $ProjectRoot 'tmp'
$Archive = Join-Path $TemporaryDirectory 'ollama-windows-amd64.zip'
$RuntimeUrl = 'https://ollama.com/download/ollama-windows-amd64.zip'

New-Item -ItemType Directory -Force -Path $RuntimeDirectory, $ModelPath, $TemporaryDirectory | Out-Null
if (-not (Test-Path $Runtime)) {
    Write-Output 'Downloading the Ollama Windows runtime into the project...'
    Invoke-WebRequest -UseBasicParsing -Uri $RuntimeUrl -OutFile $Archive
    Expand-Archive -Path $Archive -DestinationPath $RuntimeDirectory -Force
    Remove-Item -LiteralPath $Archive -Force
}

if (-not (Test-Path $Runtime)) {
    throw "Ollama runtime was not found at $Runtime after extraction."
}

& (Join-Path $PSScriptRoot 'stop-project-ai.ps1')
& (Join-Path $PSScriptRoot 'start-project-ai.ps1')

$env:OLLAMA_MODELS = $ModelPath
if (Test-Path $ModelFile) {
    if (-not (Test-Path $ModelFileDefinition)) {
        throw "Expected Modelfile was not found at $ModelFileDefinition."
    }
    Push-Location $ModelImportDirectory
    try {
        & $Runtime create $Model -f $ModelFileDefinition
        if ($LASTEXITCODE -ne 0) {
            throw "Local model import failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
    Remove-Item -LiteralPath $ModelFile -Force
}

$models = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 15
if (-not ($models.models.name -contains $Model)) {
    throw "Model $Model is not available. Place the GGUF file in $ModelImportDirectory and run this script again."
}
& $Runtime create $CudaModel -f $CudaModelDefinition
if ($LASTEXITCODE -ne 0) {
    throw "CUDA model configuration failed with exit code $LASTEXITCODE."
}
Write-Output "Project-local AI is ready. Model: $CudaModel"
