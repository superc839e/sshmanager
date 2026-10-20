@echo off
rem Instala SSH Manager y crea el comando "sshmanager"
setlocal
set "APP=%LOCALAPPDATA%\sshmanager"
set "BIN=%LOCALAPPDATA%\Microsoft\WindowsApps"
if not exist "%APP%" mkdir "%APP%"

where py >nul 2>nul
if errorlevel 1 (set "PY=python") else (set "PY=py -3")

%PY% -m venv "%APP%\venv"
if errorlevel 1 goto nopython

"%APP%\venv\Scripts\python.exe" -m pip install --quiet --upgrade pip textual paramiko
if errorlevel 1 goto fallo

copy /Y "%~dp0ssh_manager.py" "%APP%\ssh_manager.py" >nul
> "%BIN%\sshmanager.bat" echo @"%APP%\venv\Scripts\python.exe" "%APP%\ssh_manager.py" %%*

echo.
echo Listo. Abre Windows Terminal o PowerShell y escribe: sshmanager
pause
exit /b 0

:nopython
echo No se encontro Python. Instalalo desde python.org y marca "Add python.exe to PATH".
pause
exit /b 1

:fallo
echo Fallo la instalacion de dependencias. Revisa tu conexion a internet.
pause
exit /b 1
