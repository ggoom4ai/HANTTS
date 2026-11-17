$ErrorActionPreference = 'Stop'
# uv 0.13.8 Windows x64. SHA256 은 GitHub Release asset digest.
$Version = '0.13.8'
$Sha256 = '529e78a9cec6cd7e3e014f7ecd8bda0c113969d4ed0f2efeedb85c30943325b8'
$Dest = if ($args.Count -ge 1) { $args[0] } else { Join-Path (Resolve-Path '.') 'dist\HanTTS\uv.exe' }
$Url = "https://github.com/astral-sh/uv/releases/download/$Version/uv-x86_64-pc-windows-msvc.zip"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) "hantts-uv-$Version.zip"
Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing
$hash = (Get-FileHash -Algorithm SHA256 $tmp).Hash.ToLower()
if ($hash -ne $Sha256) {
    Remove-Item $tmp -Force
    throw "uv SHA256 불일치: $hash"
}
$unpack = Join-Path ([System.IO.Path]::GetTempPath()) "hantts-uv-$Version"
if (Test-Path $unpack) { Remove-Item $unpack -Recurse -Force }
Expand-Archive -Path $tmp -DestinationPath $unpack -Force
$exe = Get-ChildItem $unpack -Recurse -Filter uv.exe | Select-Object -First 1
New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
Copy-Item $exe.FullName $Dest -Force
Write-Output "uv $Version -> $Dest"
