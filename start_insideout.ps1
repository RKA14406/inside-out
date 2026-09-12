$ErrorActionPreference = 'Stop'
$insideoutRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$insideoutPython = Join-Path $insideoutRoot '.venv-desktop\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $insideoutPython)) {
    throw 'Desktop environment missing. Run .\setup_insideout.ps1 first.'
}
& $insideoutPython (Join-Path $insideoutRoot 'insideout.py') @args
exit $LASTEXITCODE
