# SSHManager
A TUI created to manage files from SSH servers without 50 lines of code

<img width="278" height="150" alt="SSH_Manager_2026-10-20T13_29_10_065455" src="https://github.com/user-attachments/assets/3dc43387-5849-4866-809e-54ba84fe83dc" />
<img width="278" height="150" alt="SSH_Manager_2026-10-20T13_28_49_906642" src="https://github.com/user-attachments/assets/357bb044-0368-4f6b-a471-7f2636ed69fc" />

Esta es una aplicación que he creado para hacer que gestionar archivos en la terminal sea simple, lo hice principalmente para que mi mamá entienda un poco más como funcionan los servidores, así que no está muy pulido y es casi todo hecho con IA.
Si cualquiera quiere copiar el proyecto y hacerlo mejor, bienvenido sea


This is an app that i made to make managing files in the terminal simple, I did it mainly so that my mom understands a little more how the servers work, so it is not very polished and it's vibecoded.
If anyone wants to copy the project and make it better, welcome

## Descarga / Download

## Español

### 1. Descarga los archivos
Primero, descarga los archivos que correspondan a tu sistema operativo:
Windows: `instalar_windows.bat` y `sshmanager.py`
Linux: `instalar_linux.sh` y `sshmanager.py`

### 2. Pon los archivos en una misma carpeta
Crea una carpeta nueva, por ejemplo:
`SSHManager`
Mueve dentro de esa carpeta los dos archivos que descargaste.
La carpeta debería quedar así:

`SSHManager/`

`├── instalar_windows.bat   ← Windows`

`└── sshmanager.py`

o, en Linux:

`SSHManager/`

`├── instalar_linux.sh      ← Linux`

`└── sshmanager.py`

### 3. Si utilizas Windows
Abre la carpeta donde están los archivos.
Haz clic en un espacio vacío de la carpeta con el botón derecho del ratón.
Selecciona "Abrir en Terminal" o "Abrir en Terminal de Windows".
Se abrirá una ventana de terminal directamente en esa carpeta.
Espera a que termine el proceso y sigue las instrucciones que aparezcan en pantalla.

### 4. Si utilizas Linux
Abre la carpeta.
Puedes abrir una terminal de varias formas, dependiendo de tu distribución:

Opción 1 — desde la carpeta:
Haz clic con el botón derecho dentro de la carpeta y busca una opción como "Abrir en Terminal", "Open in Terminal" o similar.

Opción 2 — desde una terminal:
Abre tu aplicación Terminal y utiliza cd para entrar en la carpeta. Por ejemplo, si la carpeta está dentro de `Descargas`:
`cd ~/Descargas/SSHManager`
Puedes comprobar que estás en la carpeta correcta ejecutando:
`ls`
Deberías ver:
`instalar_linux.sh`
`sshmanager.py`
Después, dale permisos de ejecución al instalador:
`chmod +x instalar_linux.sh`
Y ejecútalo con:
`./instalar_linux.sh`
Sigue las instrucciones que aparezcan en la terminal hasta que finalice la instalación.

### 5. Importante
No ejecutes el instalador desde una carpeta diferente. Los archivos `sshmanager.py` y el instalador correspondiente deben estar juntos en la misma carpeta antes de comenzar.
Si durante la instalación aparece un mensaje de error, no cierres la terminal. Copia el mensaje completo y guárdalo, ya que será necesario para saber qué ocurrió.

## English

### 1. Download the files

First, download the files corresponding to your operating system:

Windows: `instalar_windows.bat` and `sshmanager.py`

Linux: `instalar_linux.sh` and `sshmanager.py`

### 2. Put the files in the same folder

Create a new folder, for example:

`SSHManager`

Move the two downloaded files into that folder.

The folder should look like this:

`SSHManager/`

`├── instalar_windows.bat   ← Windows`

`└── sshmanager.py`

or, on Linux:

`SSHManager/`

`├── instalar_linux.sh      ← Linux`

`└── sshmanager.py`

### 3. If you are using Windows

Open the folder containing the files.

Right-click an empty space inside the folder.

Select "Open in Terminal" or "Open in Windows Terminal".

A terminal window will open directly in that folder.

Run the installer by typing:

`instalar_windows.bat`

Press Enter.

Wait for the process to finish and follow the instructions displayed on the screen.

### 4. If you are using Linux

Open the folder.

You can open a terminal in several ways, depending on your distribution:

Option 1 — From the folder:

Right-click inside the folder and look for an option such as "Open in Terminal" or a similar option.

Option 2 — From a terminal:

Open your Terminal application and use `cd` to navigate to the folder. For example, if the folder is inside `Downloads`:

`cd ~/Downloads/SSHManager`

You can check that you are in the correct folder by running:

`ls`

You should see:

`instalar_linux.sh`

`sshmanager.py`

Next, grant execution permissions to the installer:

`chmod +x instalar_linux.sh`

Then run it with:

`./instalar_linux.sh`

Follow the instructions displayed in the terminal until the installation is complete.

### 5. Important

Do not run the installer from a different folder. The `sshmanager.py` file and the corresponding installer must be in the same folder before you begin.

If an error message appears during installation, do not close the terminal. Copy the entire error message and save it, as it will be needed to determine what went wrong.
