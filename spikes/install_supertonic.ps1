# Supertonic 3 격리 venv. 모델은 카탈로그 설치기가 SHA256으로 받는다.
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Venv = Join-Path $Root ".spikes\supertonic"
uv venv $Venv --python 3.11
uv pip install --python (Join-Path $Venv "Scripts\python.exe") "supertonic==1.3.1"
Write-Host "venv: $Venv"
