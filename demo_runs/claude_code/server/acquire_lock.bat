@echo off
mkdir D:\bench\_heavy.lock 2>nul
if errorlevel 1 (echo HELD & type D:\bench\_heavy.lock\owner.txt & exit /b 1)
echo claude_code %date% %time% %1> D:\bench\_heavy.lock\owner.txt
echo GOT
