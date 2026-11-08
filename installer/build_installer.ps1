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

$iscc = $null
$command = Get-Command iscc -ErrorAction SilentlyContinue
if ($command) {
    $iscc = $command.Source
} else {
    $candidates = @(
        "$env:USERPROFILE\scoop\shims\iscc.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            $iscc = $candidate
            break
        }
    }
}

if (-not $iscc) {
    throw "ISCC.exe not found. Install Inno Setup 6 with: scoop install inno-setup"
}

$junction = Join-Path $env:APPDATA "FreeCAD\v1-1\Mod\LearnCad"
if (Test-Path -LiteralPath $junction) {
    $item = Get-Item -LiteralPath $junction
    if ($item.LinkType) {
        Write-Warning "A development junction exists at $junction. Do not run the installer on this machine; test on a clean profile or VM."
    }
}

$dist = Join-Path $repo "dist"
New-Item -ItemType Directory -Path $dist -Force | Out-Null
$target = Join-Path $dist "LearnCad-Setup-$Version.exe"
if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Force
}

$addonSource = Join-Path $repo "freecad\CADet"
Get-ChildItem -LiteralPath $addonSource -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "__pycache__" } |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $addonSource -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in ".pyc", ".pyo" } |
    Remove-Item -Force

$legacy = Join-Path $env:APPDATA "FreeCAD\v1-1\Mod\CADet"
if (Test-Path -LiteralPath $legacy) {
    Write-Warning "A legacy development junction exists at $legacy. Remove it before running the installer on this machine."
}

Write-Host "Building LearnCad $Version installer..."
& $iscc "/DMyAppVersion=$Version" (Join-Path $PSScriptRoot "LearnCad.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $target)) {
    throw "Expected installer was not created: $target"
}

$hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
$size = (Get-Item -LiteralPath $target).Length
Write-Host ""
Write-Host "Built: $target"
Write-Host "Size:  $([math]::Round($size / 1MB, 2)) MB"
Write-Host "SHA256: $hash"
