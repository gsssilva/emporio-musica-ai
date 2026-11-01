$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$portable = Join-Path $projectRoot 'runtime\tools\ollama\ollama.exe'
if (Test-Path -LiteralPath $portable -PathType Leaf) {
    $binary = $portable
} else {
    $installed = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $installed) { throw 'Instale o Ollama pelo site oficial ou disponibilize o pacote portátil em runtime\tools\ollama.' }
    $binary = $installed.Source
}
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path $projectRoot 'runtime\ollama-models'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_CONTEXT_LENGTH = '8192'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_FLASH_ATTENTION = '1'
$env:OLLAMA_KV_CACHE_TYPE = 'q8_0'
& $binary serve
