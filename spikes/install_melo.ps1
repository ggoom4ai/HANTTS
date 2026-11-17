# MeloTTS 격리 venv. 커밋은 docs/03 과 카탈로그 lock 과 같다.
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Venv = Join-Path $Root ".spikes\melo"
$Pin = "209145371cff8fc3bd60d7be902ea69cbdb7965a"
uv venv $Venv --python 3.11
uv pip install --python (Join-Path $Venv "Scripts\python.exe") "git+https://github.com/myshell-ai/MeloTTS.git@$Pin"
& (Join-Path $Venv "Scripts\python.exe") -m unidic download
Write-Host "venv: $Venv"
