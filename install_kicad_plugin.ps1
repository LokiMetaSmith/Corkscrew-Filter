<#
.SYNOPSIS
Installs the OpenAuto EM Live KiCad Action Plugin into KiCad 10 / 9 / 8 / 7.

.EXAMPLE
.\install_kicad_plugin.ps1
.\install_kicad_plugin.ps1 -Symlink
.\install_kicad_plugin.ps1 -Dir "C:\custom\path"
#>
param(
    [switch]$Symlink,
    [string]$Dir
)

$ErrorActionPreference = "Stop"

# Use local virtual environment python if present, else system python
$pythonExe = "python"
if (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe") {
    $pythonExe = "$PSScriptRoot\.venv\Scripts\python.exe"
}

$scriptArgs = @("$PSScriptRoot\kicad_plugin\install_plugin.py")
if ($Symlink) {
    $scriptArgs += "--symlink"
} else {
    $scriptArgs += "--copy"
}
if ($Dir) {
    $scriptArgs += @("--dir", $Dir)
}

Write-Host "Running OpenAuto EM Live Plugin Installer..." -ForegroundColor Cyan
& $pythonExe @scriptArgs
