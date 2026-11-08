# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
[CmdletBinding()]
param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

if (-not $Version) {
    $manifest = Get-Content -LiteralPath (Join-Path $repo "package.xml") -Raw
    if ($manifest -match "<version>([^<]+)</version>") {
        $Version = $Matches[1].Trim()
    } else {
        throw "Could not read <version> from package.xml"
    }
}

$dist = Join-Path $repo "dist"
New-Item -ItemType Directory -Path $dist -Force | Out-Null

$stage = Join-Path $env:TEMP "learncad-portable-$Version"
if (Test-Path -LiteralPath $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
$addon = Join-Path $stage "LearnCad"
New-Item -ItemType Directory -Path $addon -Force | Out-Null

Copy-Item -LiteralPath (Join-Path $repo "package.xml") -Destination $addon
Copy-Item -LiteralPath (Join-Path $repo "LICENSE") -Destination $addon
Copy-Item -LiteralPath (Join-Path $repo "README.md") -Destination $addon
New-Item -ItemType Directory -Path (Join-Path $addon "freecad") -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repo "freecad\CADet") -Destination (Join-Path $addon "freecad\CADet") -Recurse -Force

Get-ChildItem -LiteralPath $addon -Recurse -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq "__pycache__" } | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $addon -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in ".pyc", ".pyo" } | Remove-Item -Force

if (-not (Test-Path -LiteralPath (Join-Path $addon "package.xml"))) {
    throw "Portable staging is missing package.xml"
}
if (-not (Test-Path -LiteralPath (Join-Path $addon "freecad\CADet\init_gui.py"))) {
    throw "Portable staging is missing freecad\CADet\init_gui.py"
}

$zip = Join-Path $dist "LearnCad-$Version-portable.zip"
if (Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
}
Compress-Archive -LiteralPath $addon -DestinationPath $zip -CompressionLevel Optimal

$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
$size = (Get-Item -LiteralPath $zip).Length
Write-Host "Built: $zip"
Write-Host "Size:  $([math]::Round($size / 1KB, 1)) KB"
Write-Host "SHA256: $hash"
