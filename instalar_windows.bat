@echo off
rem Instala (o reinstala) SSH Manager App y crea el comando "sshmanagerapp" y un acceso en el menu Inicio.
setlocal
set "BASE=https://raw.githubusercontent.com/superc839e/sshmanagerapp/main"
set "CORE_BASE=https://raw.githubusercontent.com/superc839e/sshmanager/main"
set "APP=%LOCALAPPDATA%\sshmanagerapp"
set "BIN=%LOCALAPPDATA%\Microsoft\WindowsApps"
if not exist "%APP%" mkdir "%APP%"

where py >nul 2>nul
if errorlevel 1 (set "PY=python") else (set "PY=py -3")

%PY% -m venv "%APP%\venv"
if errorlevel 1 (echo No se encontro Python. Instalalo desde python.org y marca Add python.exe to PATH. & pause & exit /b 1)
set "VPY=%APP%\venv\Scripts\python.exe"
set "VPYW=%APP%\venv\Scripts\pythonw.exe"

if exist "%~dp0sshmanagerapp.py" (
  copy /Y "%~dp0sshmanagerapp.py" "%APP%\sshmanagerapp.py" >nul
) else (
  echo Descargando sshmanagerapp.py desde GitHub...
  curl.exe -fsSL --retry 3 --retry-delay 2 -o "%APP%\sshmanagerapp.py" "%BASE%/sshmanagerapp.py"
  if errorlevel 1 (echo No pude descargar desde GitHub. Revisa tu conexion. & pause & exit /b 1)
)

rem La app se conecta con sshmanager: usa su nucleo si esta instalado; si no, lo descarga.
if not exist "%LOCALAPPDATA%\sshmanager\sshmanager_core.py" (
  if not exist "%APP%\core" mkdir "%APP%\core"
  echo Descargando el nucleo de sshmanager...
  curl.exe -fsSL --retry 3 --retry-delay 2 -o "%APP%\core\sshmanager_core.py" "%CORE_BASE%/sshmanager_core.py"
  if errorlevel 1 (echo No pude descargar el nucleo. Revisa tu conexion. & pause & exit /b 1)
)

rem Dependencias con correccion automatica de errores comunes
"%VPY%" "%APP%\sshmanagerapp.py" --install-deps
if errorlevel 1 (echo Fallo la instalacion de dependencias. Prueba: sshmanagerapp --doctor & pause & exit /b 1)

rem Comando: sin argumentos o con --connect abre la ventana sin consola; con otras opciones muestra el texto.
> "%BIN%\sshmanagerapp.bat" echo @echo off
>> "%BIN%\sshmanagerapp.bat" echo setlocal
>> "%BIN%\sshmanagerapp.bat" echo set PYTHONUTF8=1
>> "%BIN%\sshmanagerapp.bat" echo if "%%~1"=="" (start "" "%VPYW%" "%APP%\sshmanagerapp.py" ^& exit /b 0)
>> "%BIN%\sshmanagerapp.bat" echo if /i "%%~1"=="--connect" (start "" "%VPYW%" "%APP%\sshmanagerapp.py" %%* ^& exit /b 0)
>> "%BIN%\sshmanagerapp.bat" echo "%VPY%" "%APP%\sshmanagerapp.py" %%*

rem Acceso en el menu Inicio (si falla, no pasa nada)
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:APPDATA+'\Microsoft\Windows\Start Menu\Programs\SSH Manager App.lnk'); $s.TargetPath='%VPYW%'; $s.Arguments='\"%APP%\sshmanagerapp.py\"'; $s.WorkingDirectory='%APP%'; $s.Save()" >nul 2>nul

echo.
echo Listo. Abre SSH Manager App desde el menu Inicio o escribe: sshmanagerapp
pause
