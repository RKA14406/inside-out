param(
    [string]$Output = ''
)

$ErrorActionPreference = 'Stop'
$InsideOutRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ReleaseRoot = Join-Path $InsideOutRoot 'release'
$StageRoot = Join-Path $ReleaseRoot '.insideout-release-stage'
if (-not $Output) { $Output = Join-Path $ReleaseRoot 'insideout-release.zip' }
$Output = [IO.Path]::GetFullPath($Output)

foreach ($path in @($ReleaseRoot, $StageRoot)) {
    $resolved = [IO.Path]::GetFullPath($path)
    if (-not $resolved.StartsWith($InsideOutRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe release path: $resolved"
    }
}

if (Test-Path -LiteralPath $StageRoot) {
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $Output) -Force | Out-Null

$RootFiles = @(
    '.gitattributes',
    '.gitignore',
    'AGENTS.md',
    'ATTRIBUTION.md',
    'README.md',
    'README_CN.md',
    'insideout.py',
    'requirements-desktop.txt',
    'setup_insideout.ps1',
    'start_insideout.bat'
)
$RootFiles += Get-ChildItem -LiteralPath $InsideOutRoot -File -Filter 'AIO 2026*.pdf' |
    ForEach-Object { $_.Name }

$Directories = @(
    'desktop',
    'docs',
    'scripts',
    'screenshots prototype',
    'evaluation\competition_sketches',
    'evaluation\competition_frames',
    'assets\desktop\sources'
)

foreach ($relative in $RootFiles) {
    $source = Join-Path $InsideOutRoot $relative
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $StageRoot $relative) -Force
    }
}

foreach ($relative in $Directories) {
    $source = Join-Path $InsideOutRoot $relative
    if (-not (Test-Path -LiteralPath $source)) { continue }
    $destination = Join-Path $StageRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

foreach ($relative in @('assets\logo-light.svg', 'assets\logo-dark.svg',
        'assets\desktop\manifest.json', 'data\model_index\competition.npz',
        'data\weights\OPENCLIP_MODEL_CARD.md')) {
    $source = Join-Path $InsideOutRoot $relative
    if (-not (Test-Path -LiteralPath $source)) { continue }
    $destination = Join-Path $StageRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

Get-ChildItem -LiteralPath $StageRoot -Recurse -Directory -Filter '__pycache__' |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $StageRoot -Recurse -File -Include '*.pyc','*.pyo','*.log','*.partial' |
    Remove-Item -Force

$BuildInfo = @(
    'InsideOut source release',
    ('Built: ' + (Get-Date).ToString('s')),
    'Run setup_insideout.ps1 after extraction.',
    'The Python environment and 605 MB OpenCLIP checkpoint are intentionally not bundled.',
    'See README.md and ATTRIBUTION.md before redistribution.'
)
Set-Content -LiteralPath (Join-Path $StageRoot 'BUILD_INFO.txt') -Value $BuildInfo -Encoding UTF8

if (Test-Path -LiteralPath $Output) {
    Remove-Item -LiteralPath $Output -Force
}
Compress-Archive -Path (Join-Path $StageRoot '*') -DestinationPath $Output -CompressionLevel Optimal
Remove-Item -LiteralPath $StageRoot -Recurse -Force

$Archive = Get-Item -LiteralPath $Output
$Hash = Get-FileHash -LiteralPath $Output -Algorithm SHA256
Write-Host ("Release: {0}" -f $Archive.FullName)
Write-Host ("Bytes: {0}" -f $Archive.Length)
Write-Host ("SHA256: {0}" -f $Hash.Hash)
