# SSHManager

Una TUI para gestionar archivos de servidores SSH sin 50 líneas de comandos. Funciona en Windows y Linux.

*A TUI to manage files on SSH servers without 50 lines of commands. Works on Windows and Linux.*

<img width="1495" height="807" alt="SSH_Manager_2026-10-20T13_28_49_906642 (1)" src="https://github.com/user-attachments/assets/ae421428-8393-43cb-8e5d-82290db8220b" />
<img width="278" height="150" alt="SSH_Manager_2026-10-20T13_29_10_065455" src="https://github.com/user-attachments/assets/021e642f-b9ac-43ed-a5ba-de2ecec58b7b" />

Esta es una aplicación que he creado para hacer que gestionar archivos en la terminal sea simple, lo hice principalmente para que mi mamá entienda un poco más como funcionan los servidores, así que no está muy pulido y es casi todo hecho con IA.
Si cualquiera quiere copiar el proyecto y hacerlo mejor, bienvenido sea

This is an app that i made to make managing files in the terminal simple, I did it mainly so that my mom understands a little more how the servers work, so it is not very polished and it's vibecoded.
If anyone wants to copy the project and make it better, welcome

> ¿Prefieres ventanas y ratón? / *Prefer windows and a mouse?* Mira / see **[SSH Manager App](https://github.com/superc839e/sshmanagerapp)**, la versión gráfica que se enlaza con esta.

## Instalar / Install

**Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/superc839e/sshmanager/main/instalar_linux.sh | bash
```
**Windows** (CMD o PowerShell)
```bat
curl.exe -L -o instalar_windows.bat https://raw.githubusercontent.com/superc839e/sshmanager/main/instalar_windows.bat
.\instalar_windows.bat
```
Las dependencias (textual, paramiko) se descargan solas y los errores comunes de descarga se corrigen automáticamente. Reinstalar es el mismo comando.

*Dependencies (textual, paramiko) are downloaded automatically and common download errors are fixed on their own. Reinstalling is the same command.*

## Uso / Usage

| Comando | Qué hace |
|---|---|
| `sshmanager` | Abre la app |
| `sshmanager --connect NOMBRE` | Abre y conecta a un servidor guardado |
| `sshmanager --gui [NOMBRE]` | Abre la app gráfica |
| `sshmanager -u` | Actualiza desde GitHub |
| `sshmanager -d` | Desinstala |
| `sshmanager -l es\|en` | Cambia el idioma |
| `sshmanager --chars auto\|unicode\|ascii` | Cambia los caracteres (útil en Windows) |
| `sshmanager --doctor` / `--repair` | Diagnostica / repara problemas comunes |
| `sshmanager -h [es\|en]` | Manual |

## Qué hace / Features

- Servidores guardados con nombre / *Saved servers with names*
- Dos paneles (tu PC y el servidor) para navegar carpetas / *Two panels (your PC and the server) to browse folders*
- Fila de transferencias que recuerda de dónde viene cada archivo y a dónde va / *Transfer queue that remembers where each file comes from and where it goes*
- Consola para ejecutar comandos en el servidor / *Console to run commands on the server*
- Español e inglés, y busca actualizaciones al abrir / *Spanish and English, and checks for updates on startup*

## Conexión con la app gráfica / Link with the graphical app

La terminal y [SSH Manager App](https://github.com/superc839e/sshmanagerapp) comparten **servidores, fila de transferencias e idioma**. Si ambas están abiertas se avisan al instante de los cambios; pulsa `g` para abrir la app gráfica.

*The terminal and [SSH Manager App](https://github.com/superc839e/sshmanagerapp) share **servers, transfer queue and language**. When both are open they notify each other instantly; press `g` to open the graphical app.*

## Instalación manual / Manual install

**Español:** descarga `ssh_manager.py`, `sshmanager_core.py` y el instalador de tu sistema (`instalar_windows.bat` o `instalar_linux.sh`) y ponlos **juntos en una misma carpeta**. Abre una terminal en esa carpeta y ejecuta:

- Windows: `instalar_windows.bat`
- Linux: `chmod +x instalar_linux.sh` y luego `./instalar_linux.sh`

Si aparece un error, no cierres la terminal: copia el mensaje completo y prueba `sshmanager --doctor`.

**English:** download `ssh_manager.py`, `sshmanager_core.py` and the installer for your system (`instalar_windows.bat` or `instalar_linux.sh`) and put them **together in the same folder**. Open a terminal in that folder and run:

- Windows: `instalar_windows.bat`
- Linux: `chmod +x instalar_linux.sh` and then `./instalar_linux.sh`

If an error appears, do not close the terminal: copy the whole message and try `sshmanager --doctor`.

## Archivos / Files

`ssh_manager.py` (la app / the app), `sshmanager_core.py` (núcleo compartido con la app gráfica / core shared with the graphical app), `instalar_linux.sh`, `instalar_windows.bat`.
