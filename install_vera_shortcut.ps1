# Installs a VERA desktop shortcut with a custom icon.
# Run this from your VERA project root (C:\Users\P01yG107\Desktop\vera),
# after vera_icon.ico is dropped into that same folder.

$veraRoot = $PSScriptRoot
$iconPath = Join-Path $veraRoot "vera_icon.ico"
$launcher = Join-Path $veraRoot "vera.bat"

if (-not (Test-Path $iconPath)) {
    Write-Host "vera_icon.ico not found in $veraRoot -- place it there first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $launcher)) {
    Write-Host "vera.bat not found in $veraRoot -- can't build a shortcut to it." -ForegroundColor Red
    exit 1
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "VERA.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $veraRoot
$shortcut.IconLocation = $iconPath
$shortcut.WindowStyle = 1
$shortcut.Description = "VERA -- Verified Execution Reasoning Agent"
$shortcut.Save()

Write-Host "VERA shortcut installed at: $shortcutPath" -ForegroundColor Green
