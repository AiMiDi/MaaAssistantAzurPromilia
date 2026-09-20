$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required.' }
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
New-Item -ItemType Directory -Force .cache | Out-Null

$ocrPath = Join-Path $PSScriptRoot 'assets\resource\model\ocr'
$ocrComplete = (Test-Path (Join-Path $ocrPath 'rec.onnx')) -and (Test-Path (Join-Path $ocrPath 'det.onnx')) -and (Test-Path (Join-Path $ocrPath 'keys.txt'))
if (-not $ocrComplete) {
    Invoke-WebRequest 'https://download.maafw.xyz/MaaCommonAssets/OCR/ppocr_v6/ppocr_v6-small.zip' -OutFile '.cache\ocr.zip'
    Expand-Archive -LiteralPath '.cache\ocr.zip' -DestinationPath '.cache\ocr' -Force
    New-Item -ItemType Directory -Force $ocrPath | Out-Null
    foreach ($name in @('det.onnx', 'rec.onnx', 'keys.txt')) {
        $item = Get-ChildItem '.cache\ocr' -Recurse -File -Filter $name | Select-Object -First 1
        if (-not $item) { throw "OCR archive missing $name" }
        Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $ocrPath $name)
    }
}

if (-not (Test-Path 'install\MFAAvalonia.exe')) {
    Invoke-WebRequest 'https://github.com/MaaXYZ/MFAAvalonia/releases/download/v2.16.1/MFAAvalonia-v2.16.1-win-x64.zip' -OutFile '.cache\mfa.zip'
    Expand-Archive -LiteralPath '.cache\mfa.zip' -DestinationPath 'install' -Force
}

& .\.venv\Scripts\python.exe -X utf8 tools\package_local.py
if ($LASTEXITCODE -ne 0) { throw 'UI assembly failed.' }
$dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnet -or -not ((& $dotnet.Source --list-runtimes) -match '^Microsoft.NETCore.App 10\.')) {
    Write-Warning 'MFAAvalonia needs .NET Runtime 10 x64: https://dotnet.microsoft.com/download/dotnet/10.0'
}
Write-Output 'Setup complete. Double-click Start.cmd to open the assistant.'
