@echo off
setlocal
rem The native launcher includes the updater; Python is not required.
if /i "%~1"=="--shortcut" goto shortcut
"%~dp0LaserForge-Portable.exe"
exit /b

:shortcut
rem Use the branded executable icon, not the generic batch-file icon.
set "LASERFORGE_HOME=%~dp0"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $homeDir=$env:LASERFORGE_HOME; $shell=New-Object -ComObject WScript.Shell; $link=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Laser Forge.lnk')); $link.TargetPath=(Join-Path $homeDir 'Start-LaserForge.cmd'); $link.WorkingDirectory=$homeDir; $link.IconLocation=((Join-Path $homeDir 'LaserForge-Portable.exe')+',0'); $link.Description='Laser Forge'; $link.Save()"
if errorlevel 1 exit /b 1
echo Laser Forge desktop shortcut created.

