#Requires -Version 5.1
<#
.SYNOPSIS
    Copies generated JSON output into tests/golden/ after a validated generate run.

.DESCRIPTION
    Run this script after executing pbi-grid generate for both themes and
    confirming the output is correct in Power BI. It copies two folders:
      - definition/                        (pages, visuals, report.json)
      - StaticResources/RegisteredResources/ (custom theme JSON only, no binaries)
    Binary files (.png, .abf) and volatile settings are excluded.

.PARAMETER Theme
    Which theme to update: 'default', 'govbr', or 'all' (default).

.EXAMPLE
    .\util\update-golden.ps1
    .\util\update-golden.ps1 -Theme govbr
    .\util\update-golden.ps1 -Theme default
#>

param(
    [ValidateSet('default', 'govbr', 'all')]
    [string]$Theme = 'all'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ROOT   = Split-Path $PSScriptRoot -Parent
$OUTPUT = Join-Path $ROOT 'output'
$GOLDEN = Join-Path $ROOT 'tests\golden\countries_population'

$THEMES = @('default', 'govbr')

function Sync-Dir {
    param([string]$Src, [string]$Dst, [string[]]$ExcludeDirs = @(), [string[]]$ExcludeFiles = @())

    $args = @($Src, $Dst, '/S', '/NP', '/NFL', '/NDL')
    if ($ExcludeDirs)  { $args += '/XD'; $args += $ExcludeDirs }
    if ($ExcludeFiles) { $args += '/XF'; $args += $ExcludeFiles }

    $result   = & robocopy @args 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -ge 8) {
        Write-Host "  x robocopy failed (exit $exitCode): $Src" -ForegroundColor Red
        Write-Host $result
        return $false
    }
    return $true
}

function Update-Theme {
    param([string]$Name)

    $reportRoot = Join-Path $OUTPUT "$Name\countries_population\countries_population.Report"

    if (-not (Test-Path $reportRoot)) {
        Write-Host "  x Source not found: $reportRoot" -ForegroundColor Red
        Write-Host "    Run pbi-grid generate with theme '$Name' first."
        return
    }

    Write-Host ''
    Write-Host "  Updating golden: $Name" -ForegroundColor Cyan

    # 1. definition/ — pages, visuals, report.json (exclude volatile .pbi/)
    $ok1 = Sync-Dir `
        -Src (Join-Path $reportRoot 'definition') `
        -Dst (Join-Path $GOLDEN "$Name\definition") `
        -ExcludeDirs @('.pbi')

    # 2. StaticResources/RegisteredResources/ — custom theme JSON only (exclude PNGs)
    $ok2 = Sync-Dir `
        -Src (Join-Path $reportRoot 'StaticResources\RegisteredResources') `
        -Dst (Join-Path $GOLDEN "$Name\StaticResources\RegisteredResources") `
        -ExcludeFiles @('*.png')

    if ($ok1 -and $ok2) {
        Write-Host "  v golden/$Name updated" -ForegroundColor Green
    }
}

# ── Run ────────────────────────────────────────────────────────────────────────

Write-Host ''
Write-Host 'update-golden: syncing tests/golden/ from output/' -ForegroundColor White

$targets = if ($Theme -eq 'all') { $THEMES } else { @($Theme) }

foreach ($t in $targets) {
    Update-Theme -Name $t
}

Write-Host ''
Write-Host '  Done. Review with: git diff tests/golden/' -ForegroundColor White
Write-Host '  Commit only after validating the output in Power BI.'
Write-Host ''
