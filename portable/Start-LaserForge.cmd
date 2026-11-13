@echo off
rem Python 3.9+ is required only for the automatic update launch path.
py -3 "%~dp0update.py" --launch
if errorlevel 1 (
  echo Laser Forge could not start. Check the message above.
  echo To launch without automatic updates, open LaserForge-Portable.exe.
  pause
)
