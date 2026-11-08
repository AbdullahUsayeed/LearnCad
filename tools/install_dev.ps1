# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the LearnCad addon.
[CmdletBinding()]
param(
    [string]$FreeCADVersion = "v1-1",
    [string]$RepoRoot = "",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "package.xml"))) {
    throw "package.xml not found in $RepoRoot. Run this script from the LearnCad repository."
}

$modRoot = Join-Path $env:APPDATA "FreeCAD\$FreeCADVersion\Mod"
$target = Join-Path $modRoot "LearnCad"
$legacy = Join-Path $modRoot "CADet"

function Remove-Link([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.LinkType -eq "Junction" -or $item.LinkType -eq "SymbolicLink") {
        & cmd /c rmdir "$Path" | Out-Null
        if ($LASTEXITCODE -ne 0 -and (Test-Path -LiteralPath $Path)) {
            throw "Could not remove the junction at $Path. Remove it manually."
        }
    }
}

if ($Remove) {
    Remove-Link $target
    Remove-Link $legacy
    Write-Host "Removed LearnCad links from $modRoot"
    return
}

if (-not (Test-Path -LiteralPath $modRoot)) {
    New-Item -ItemType Directory -Path $modRoot | Out-Null
}

if (Test-Path -LiteralPath $legacy) {
    Remove-Link $legacy
    Write-Host "Removed legacy CADet junction: $legacy"
}

if (Test-Path -LiteralPath $target) {
    $item = Get-Item -LiteralPath $target
    if ($item.LinkType -eq "Junction" -or $item.LinkType -eq "SymbolicLink") {
        $targets = @($item.Target)
        if ($targets -contains $RepoRoot) {
            Write-Host "Already linked: $target -> $RepoRoot"
            return
        }
        Remove-Link $target
    } else {
        throw "$target already exists as a real folder. Move it aside or remove it manually."
    }
}

New-Item -ItemType Junction -Path $target -Target $RepoRoot | Out-Null
Write-Host "Linked:"
Write-Host "  $target"
Write-Host "  -> $RepoRoot"
Write-Host ""
Write-Host "Restart FreeCAD, then select 'LearnCad' in the workbench selector."
Write-Host "Or press Ctrl+Shift+M."
Write-Host ""
Write-Host "To remove the link: .\tools\install_dev.ps1 -Remove"
