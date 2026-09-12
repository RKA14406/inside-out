param(
    [string]$Python = 'python',
    [switch]$SkipAssets,
    [switch]$UseSystemPackages
)
$ErrorActionPreference = 'Stop'
$insideoutRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$insideoutEnv = Join-Path $insideoutRoot '.venv-desktop'
$insideoutPython = Join-Path $insideoutEnv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $insideoutPython)) {
    $venvArguments = @('-m', 'venv')
    if ($UseSystemPackages) { $venvArguments += '--system-site-packages' }
    $venvArguments += $insideoutEnv
    & $Python @venvArguments
    if ($LASTEXITCODE -ne 0) { throw 'Environment creation failed. Use 64-bit Python 3.12.' }
}
& $insideoutPython -m pip install -r (Join-Path $insideoutRoot 'requirements-desktop.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if (-not $SkipAssets) {
    & $insideoutPython (Join-Path $insideoutRoot 'scripts\download_demo_models.py')
    if ($LASTEXITCODE -ne 0) { throw 'Asset/weight download failed. Re-run setup to retry.' }
    & $insideoutPython (Join-Path $insideoutRoot 'scripts\ingest_models.py')
    if ($LASTEXITCODE -ne 0) { throw 'Model preprocessing failed. See the output above.' }
    & $insideoutPython (Join-Path $insideoutRoot 'scripts\build_competition_index.py')
    if ($LASTEXITCODE -ne 0) { throw 'Three-class competition index build failed. See the output above.' }
}
Write-Host 'Build prepared. Launch with .\start_insideout.bat'
Write-Host 'Setup builds assets; it does not launch or test the application.'
