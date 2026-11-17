$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

function Find-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($candidate in @(
            (Join-Path $env:USERPROFILE '.local\bin\uv.exe'),
            (Join-Path $env:LOCALAPPDATA 'uv\uv.exe')
        )) {
        if (Test-Path $candidate) { return $candidate }
    }
    throw 'uv.exe 를 찾지 못했습니다.'
}

function Find-Iscc {
    foreach ($candidate in @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )) {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

$uv = Find-Uv
$ver = (& $uv run python -c "import hantts; print(hantts.__version__)").Trim()
if (-not $ver) { throw '앱 버전을 읽지 못했습니다.' }

$wheels = Join-Path $root 'dist\wheels'
if (Test-Path $wheels) { Remove-Item $wheels -Recurse -Force }
New-Item -ItemType Directory -Force -Path $wheels | Out-Null
& $uv build --wheel (Join-Path $root 'worker_pkg') -o $wheels
if ($LASTEXITCODE -ne 0) { throw '워커 휠 빌드에 실패했습니다.' }

& $uv run pyinstaller (Join-Path $root 'installer\hantts.spec') --noconfirm --clean `
    --distpath (Join-Path $root 'dist') `
    --workpath (Join-Path $root 'build\pyinstaller')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 빌드에 실패했습니다.' }

$bundle = Join-Path $root 'dist\HanTTS'
if (-not (Test-Path (Join-Path $bundle 'HanTTS.exe'))) {
    throw 'dist\HanTTS\HanTTS.exe 가 없습니다.'
}

& (Join-Path $root 'tools\fetch_uv.ps1') (Join-Path $bundle 'uv.exe')

$catalogDest = Join-Path $bundle 'engines\catalog'
if (Test-Path $catalogDest) { Remove-Item $catalogDest -Recurse -Force }
Copy-Item (Join-Path $root 'engines\catalog') $catalogDest -Recurse -Force

$wheelDest = Join-Path $bundle 'wheels'
New-Item -ItemType Directory -Force -Path $wheelDest | Out-Null
Copy-Item (Join-Path $wheels '*') $wheelDest -Force

$iscc = Find-Iscc
if (-not $iscc) {
    throw 'Inno Setup 6 (ISCC.exe) 이 없습니다. 설치한 뒤 installer\build.ps1 을 다시 실행하세요.'
}
& $iscc "/DAppVersion=$ver" (Join-Path $root 'installer\hantts.iss')
if ($LASTEXITCODE -ne 0) { throw "ISCC 실패: $LASTEXITCODE" }

$setup = Join-Path $root "dist\installer\HanTTS-Setup-$ver-x64.exe"
if (-not (Test-Path $setup)) { throw "인스톨러가 없습니다: $setup" }
Write-Output "인스톨러: $setup"
