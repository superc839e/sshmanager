@echo off
rem Instala (o reinstala) SSH Manager y crea el comando "sshmanager".
rem Funciona desde la carpeta con ssh_manager.py o descargandolo de GitHub.
setlocal
set "URL=https://raw.githubusercontent.com/superc839e/sshmanager/main/ssh_manager.py"
set "APP=%LOCALAPPDATA%\sshmanager"
set "BIN=%LOCALAPPDATA%\Microsoft\WindowsApps"
if not exist "%APP%" mkdir "%APP%"

where py >nul 2>nul
if errorlevel 1 (set "PY=python") else (set "PY=py -3")

%PY% -m venv "%APP%\venv"
if errorlevel 1 goto nopython

"%APP%\venv\Scripts\python.exe" -m pip install --quiet --upgrade pip textual paramiko
if errorlevel 1 goto fallo

if exist "%~dp0ssh_manager.py" goto copiar
echo Descargando ssh_manager.py desde GitHub...
"%APP%\venv\Scripts\python.exe" -c "import sys,urllib.request as u; u.urlretrieve(sys.argv[1], sys.argv[2])" "%URL%" "%APP%\ssh_manager.py"
if errorlevel 1 goto sinred
goto lanzador

:copiar
copy /Y "%~dp0ssh_manager.py" "%APP%\ssh_manager.py" >nul

:lanzador
> "%BIN%\sshmanager.bat" echo @"%APP%\venv\Scripts\python.exe" "%APP%\ssh_manager.py" %%*

echo.
echo Listo. Abre Windows Terminal o PowerShell y escribe: sshmanager
echo (manual: sshmanager -h)
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

:sinred
echo No pude descargar desde GitHub. Revisa tu conexion a internet.
pause
exit /b 1
