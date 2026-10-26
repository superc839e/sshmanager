#!/usr/bin/env python3
"""
sshmanager_core - núcleo compartido por sshmanager (terminal) y sshmanagerapp (GUI).
Settings, traducciones, conexión SSH/SFTP, fila de transferencias, descargas robustas,
instalación automática de dependencias y enlace entre ambas apps.
Solo usa la biblioteca estándar de Python (paramiko se importa al conectar).
"""
from __future__ import annotations

import atexit
import codecs
import hmac
import importlib.util
import json
import os
import posixpath
import re
import secrets
import shlex
import shutil
import socket
import ssl
import stat
import string
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

__version__ = "1.3.0"
CORE_API = 1  # versión de la interfaz que usa la app gráfica

# ───────────────────────── Rutas y ajustes guardados ──────────────────────


def config_file() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "sshmanager" / "servers.json"


CONFIG = config_file()
QUEUE_FILE = CONFIG.with_name("queue.json")
SETTINGS_FILE = CONFIG.with_name("settings.json")

LANGS = ("es", "en")
LANG_NAMES = {"es": "Español", "en": "English"}
CHARS_MODES = ("auto", "unicode", "ascii")


def load_settings() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data: dict) -> None:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def detect_ascii(mode: str) -> bool:
    """¿Usar solo caracteres ASCII? 'auto' lo decide según la terminal."""
    if mode == "ascii":
        return True
    if mode == "unicode":
        return False
    if os.name == "nt":
        # Windows Terminal, VS Code y ConEmu manejan bien Unicode; la consola clásica no.
        modern = os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") or os.environ.get("ConEmuPID")
        return not modern
    return os.environ.get("TERM") == "linux"  # consola de texto pura (TTY)


_S = load_settings()
LANG = os.environ.get("SSHMANAGER_LANG") or _S.get("lang") or "es"
if LANG not in LANGS:
    LANG = "es"
CHARS = _S.get("chars") if _S.get("chars") in CHARS_MODES else "auto"
ASCII = detect_ascii(CHARS)




def apply_settings(lang: str, chars: str) -> None:
    global LANG, CHARS, ASCII
    LANG, CHARS = lang, chars
    ASCII = detect_ascii(chars)
    data = load_settings()
    data.update({"lang": lang, "chars": chars})
    save_settings(data)


# ───────────────────────────── Traducciones ───────────────────────────────

TR = {
    # botones y comunes
    "yes": ("Sí", "Yes"),
    "no": ("No", "No"),
    "accept": ("Aceptar", "OK"),
    "cancel": ("Cancelar", "Cancel"),
    "save": ("Guardar", "Save"),
    "apply": ("Aplicar", "Apply"),
    "back": ("Volver", "Back"),
    "drives": ("Unidades", "Drives"),
    "pc": ("PC", "PC"),
    "server": ("Servidor", "Server"),
    "this_pc": ("Este equipo", "This computer"),
    "col_name": ("Nombre", "Name"),
    "col_size": ("Tamaño", "Size"),
    "col_user": ("Usuario", "User"),
    # formulario de servidor
    "form_title": ("Servidor", "Server"),
    "f_name": ("Nombre (ej. Mi VPS)", "Name (e.g. My VPS)"),
    "f_host": ("Host o IP", "Host or IP"),
    "f_port": ("Puerto", "Port"),
    "f_user": ("Usuario", "User"),
    "f_pass": ("Contraseña (opcional)", "Password (optional)"),
    "f_key": ("Archivo de llave privada (opcional)", "Private key file (optional)"),
    "form_required": ("Nombre, host y usuario son obligatorios", "Name, host and user are required"),
    # ajustes
    "settings": ("Ajustes", "Settings"),
    "lang_label": ("Idioma", "Language"),
    "chars_label": ("Caracteres", "Characters"),
    "chars_auto": ("Automático", "Auto"),
    "chars_unicode": ("Unicode", "Unicode"),
    "chars_ascii": ("Solo ASCII (compatible)", "ASCII only (compatible)"),
    "settings_hint": (
        "Si ves símbolos raros o bordes torcidos, elige Solo ASCII.",
        "If you see odd symbols or crooked borders, choose ASCII only.",
    ),
    # pantalla de carga
    "splash_check": ("Buscando actualizaciones...", "Checking for updates..."),
    "skip_hint": ("Esc: saltar", "Esc: skip"),
    "net_error": ("Error de red", "Network error"),
    "error": ("Error", "Error"),
    "new_avail": ("Versión {v} disponible (tienes {cur})", "Version {v} available (you have {cur})"),
    "installing": ("Instalando actualización...", "Installing update..."),
    "updated_restart": ("OK  Actualizado a v{v}. Reiniciando...", "OK  Updated to v{v}. Restarting..."),
    "exit_msg": (
        "SSH Manager actualizado a v{v}. Vuelve a ejecutar: sshmanager",
        "SSH Manager updated to v{v}. Run it again: sshmanager",
    ),
    "latest": ("OK  Estás en la última versión ({v})", "OK  You are on the latest version ({v})"),
    "update_fail": ("No se pudo actualizar: {e}", "Could not update: {e}"),
    "confirm_update": (
        "Hay una versión nueva ({v}). Tienes la {cur}.\n¿Actualizar ahora?",
        "A new version ({v}) is available. You have {cur}.\nUpdate now?",
    ),
    "log_started": ("SSH Manager v{v} iniciado", "SSH Manager v{v} started"),
    "log_latest": (
        "Búsqueda de actualizaciones: ya tienes la última versión (v{v})",
        "Update check: you already have the latest version (v{v})",
    ),
    "log_new": (
        "Versión nueva disponible: v{v} (tienes v{cur})",
        "New version available: v{v} (you have v{cur})",
    ),
    "log_net": ("No se pudo buscar actualizaciones: {e}", "Could not check for updates: {e}"),
    "st_net": ("! No se pudo buscar actualizaciones: {e}", "! Could not check for updates: {e}"),
    "st_net_retry": ("  (u: reintentar)", "  (u: retry)"),
    "st_new": ("^ Hay una versión nueva: v{v}", "^ New version available: v{v}"),
    "st_new_do": ("  (u: actualizar)", "  (u: update)"),
    "http_reply": ("GitHub respondió {code}", "GitHub replied {code}"),
    "http_404": (" (no se encontró el archivo en GitHub)", " (file not found on GitHub)"),
    "no_conn": ("sin conexión", "no connection"),
    "bad_file": ("El archivo descargado no es válido", "The downloaded file is not valid"),
    "not_ssh": ("El archivo descargado no parece ser SSH Manager", "The downloaded file does not look like SSH Manager"),
    # lista de servidores
    "servers_title": ("Servidores guardados", "Saved servers"),
    "servers_empty": (
        "No hay servidores guardados. Pulsa n para añadir el primero.",
        "No saved servers. Press n to add the first one.",
    ),
    "col_server": ("Servidor", "Server"),
    "confirm_rm_server": ("¿Borrar el servidor '{name}' de la lista?", "Remove server '{name}' from the list?"),
    "connecting": ("Conectando a {name}...", "Connecting to {name}..."),
    "connect_fail": ("No se pudo conectar", "Could not connect"),
    "log_connected": ("Conectado a {name} ({addr})", "Connected to {name} ({addr})"),
    "ask_pass": ("Contraseña para {user}@{host}:", "Password for {user}@{host}:"),
    # barras de teclas
    "k_connect": ("Conectar", "Connect"),
    "k_new": ("Nuevo", "New"),
    "k_edit": ("Editar", "Edit"),
    "k_delete": ("Borrar", "Delete"),
    "k_update": ("Actualizar", "Update"),
    "k_settings": ("Ajustes", "Settings"),
    "k_quit": ("Salir", "Quit"),
    "k_panel": ("Panel", "Panel"),
    "k_open": ("Abrir", "Open"),
    "k_transfer": ("Transferir", "Transfer"),
    "k_addq": ("A la fila", "Queue it"),
    "k_queue": ("Ver fila", "View queue"),
    "queue_name": ("Fila", "Queue"),
    "k_console": ("Consola", "Console"),
    "k_mkdir": ("Carpeta nueva", "New folder"),
    "k_refresh": ("Refrescar", "Refresh"),
    "k_hidden": ("Ocultos", "Hidden"),
    "k_disconnect": ("Desconectar", "Disconnect"),
    "k_startstop": ("Iniciar/Detener", "Start/Stop"),
    "k_remove": ("Quitar", "Remove"),
    "k_retry": ("Reintentar", "Retry"),
    "k_clear_done": ("Limpiar listos", "Clear done"),
    "k_cancel_cmd": ("Cancelar comando", "Cancel command"),
    "k_clear": ("Limpiar", "Clear"),
    # exploración
    "ready": ("Listo", "Ready"),
    "queue_n": ("Fila: {n} pendiente(s)", "Queue: {n} pending"),
    "select_first": ("Selecciona un archivo o carpeta primero", "Select a file or folder first"),
    "open_folder": ("Entra a una carpeta (no a la lista de unidades)", "Open a folder first (not the drives list)"),
    "open_drive": ("Entra primero a una unidad", "Open a drive first"),
    "mkdir_prompt": ("Nombre de la nueva carpeta:", "New folder name:"),
    "bad_dirname": ("Nombre de carpeta inválido", "Invalid folder name"),
    "confirm_delete": (
        "¿Borrar '{name}'{extra} de {where}? No se puede deshacer.",
        "Delete '{name}'{extra} from {where}? This cannot be undone.",
    ),
    "extra_contents": (" y todo su contenido", " and all its contents"),
    "where_local": ("este equipo", "this computer"),
    "where_remote": ("el servidor", "the server"),
    "could_not_open": ("No se pudo abrir", "Could not open"),
    "log_mkdir": ("Carpeta creada en {where}: {name}", "Folder created on {where}: {name}"),
    "log_deleted": ("Borrado en {where}: {name}", "Deleted on {where}: {name}"),
    "busy_leave": (
        "Espera a que termine la fila (o detenla desde 'f')",
        "Wait for the queue to finish (or stop it from 'f')",
    ),
    "log_disconnected": ("Desconectado de {name}", "Disconnected from {name}"),
    "queue_saved": ("La fila quedó guardada: {n} elemento(s) pendiente(s)", "Queue saved: {n} pending item(s)"),
    "queue_restored": (
        "Se restauró la fila de este servidor: {n} elemento(s) pendiente(s) (f para verla)",
        "Restored this server's queue: {n} pending item(s) (f to view)",
    ),
    # fila
    "queue_title": (
        "Fila de transferencias: cada elemento recuerda de dónde viene y a dónde va",
        "Transfer queue: each item remembers where it comes from and where it goes",
    ),
    "col_status": ("Estado", "Status"),
    "col_type": ("Tipo", "Type"),
    "col_from": ("Origen", "From"),
    "col_to": ("Destino", "To"),
    "col_progress": ("Avance", "Progress"),
    "s_pending": ("pendiente", "pending"),
    "s_running": ("en curso", "running"),
    "s_done": ("listo", "done"),
    "s_error": ("error", "error"),
    "t_up": ("Subir", "Upload"),
    "t_down": ("Bajar", "Download"),
    "queue_summary": (
        "{p} pendiente(s) | {r} en curso | {d} listo(s) | {e} con error",
        "{p} pending | {r} running | {d} done | {e} failed",
    ),
    "queue_empty": (
        "La fila está vacía. En la exploración usa 'a' para añadir lo seleccionado.",
        "The queue is empty. In the browser press 'a' to add the selected item.",
    ),
    "rm_running": (
        "Detén la fila antes de quitar un elemento en curso",
        "Stop the queue before removing a running item",
    ),
    "retry_n": ("{n} elemento(s) vuelven a pendiente", "{n} item(s) set back to pending"),
    "retry_none": ("No hay elementos con error", "No failed items"),
    "already_queued": (
        "Ya está en la fila con el mismo origen y destino",
        "Already in the queue with the same source and destination",
    ),
    "overwrite_queue": (
        "'{name}' ya existe en el destino y se sobrescribirá al ejecutar la fila. ¿Añadir igual?",
        "'{name}' already exists at the destination and will be overwritten when the queue runs. Add anyway?",
    ),
    "overwrite": (
        "'{name}' ya existe en el destino. ¿Sobrescribir?",
        "'{name}' already exists at the destination. Overwrite?",
    ),
    "added_notify": ("Añadido a la fila: {name}", "Added to queue: {name}"),
    "log_added": ("Fila: añadido {desc}", "Queue: added {desc}"),
    "queued_busy": (
        "Hay una transferencia en curso: quedó en la fila",
        "A transfer is running: it was added to the queue",
    ),
    "stopping": ("Deteniendo la fila...", "Stopping the queue..."),
    "nothing_pending": ("La fila no tiene elementos pendientes", "The queue has no pending items"),
    "starting": ("Iniciando...", "Starting..."),
    "sftp_fail": ("No se pudo abrir un canal SFTP: {e}", "Could not open an SFTP channel: {e}"),
    "log_item_start": ("Transfiriendo: {d}", "Transferring: {d}"),
    "log_item_ok": ("OK: {d}", "OK: {d}"),
    "log_item_err": ("ERROR: {d}: {e}", "ERROR: {d}: {e}"),
    "log_item_stop": ("Detenido: {d}", "Stopped: {d}"),
    "err_title": ("Error: {name}", "Error: {name}"),
    "queue_finished": (
        "Fila terminada: {ok} lista(s), {err} con error",
        "Queue finished: {ok} done, {err} failed",
    ),
    "queue_stopped": (
        "Fila detenida: {ok} lista(s), {err} con error",
        "Queue stopped: {ok} done, {err} failed",
    ),
    # consola
    "console_title": (
        "Consola: actividad de la app y comandos en el servidor (sin programas interactivos como nano o top)",
        "Console: app activity and commands on the server (no interactive programs like nano or top)",
    ),
    "console_placeholder": (
        "Comando para ejecutar en el servidor y Enter...",
        "Command to run on the server, then Enter...",
    ),
    "cmd_running": ("Ya hay un comando en ejecución (F4 para cancelar)", "A command is already running (F4 to cancel)"),
    "cmd_cancelled": ("(comando cancelado)", "(command cancelled)"),
    "cmd_exit": ("[código de salida: {c}]", "[exit code: {c}]"),
    # línea de comandos
    "cli_checking": (
        "SSH Manager v{cur} - buscando actualizaciones en GitHub...",
        "SSH Manager v{cur} - checking GitHub for updates...",
    ),
    "cli_net_err": ("ERROR de red: {e}", "Network ERROR: {e}"),
    "cli_latest": ("OK  Ya tienes la última versión (v{cur}).", "OK  You already have the latest version (v{cur})."),
    "cli_new": ("Nueva versión disponible: v{v}. Instalando...", "New version available: v{v}. Installing..."),
    "cli_updated": ("OK  Actualizado a v{v}.", "OK  Updated to v{v}."),
    "cli_update_fail": ("ERROR No se pudo actualizar: {e}", "ERROR Could not update: {e}"),
    "cli_unknown": ("Opción desconocida: {a}\n\nUsa: sshmanager -h", "Unknown option: {a}\n\nUse: sshmanager -h"),
    "cli_no_install": (
        "No encontré una instalación hecha con el instalador. No se borró nada.",
        "I did not find an installation made with the installer. Nothing was deleted.",
    ),
    "cli_will_remove": ("Se eliminará:", "This will be removed:"),
    "cli_cmd_note": ("(el comando sshmanager)", "(the sshmanager command)"),
    "cli_ask_uninstall": ("¿Desinstalar SSH Manager?", "Uninstall SSH Manager?"),
    "cli_cancelled": ("Cancelado.", "Cancelled."),
    "cli_ask_wipe": (
        "¿Borrar también tus servidores guardados y la fila? ({d})",
        "Also delete your saved servers and queue? ({d})",
    ),
    "cli_win_wait": ("Desinstalando... termina en unos segundos.", "Uninstalling... finishing in a few seconds."),
    "cli_uninstalled": ("OK  SSH Manager desinstalado.", "OK  SSH Manager uninstalled."),
    "cli_kept": (" Se conservaron tus servidores.", " Your servers were kept."),
    "yn": ("[s/N]", "[y/N]"),
    "yes_words": (("s", "si", "sí", "y", "yes"), ("y", "yes", "s", "si", "sí")),
    "cli_lang_now": (
        "Idioma actual: {l} (cambia con: sshmanager -l en)",
        "Current language: {l} (change with: sshmanager -l es)",
    ),
    "cli_lang_set": ("OK  Idioma: {l}", "OK  Language: {l}"),
    "cli_lang_bad": ("Idioma no válido. Usa: es | en", "Invalid language. Use: es | en"),
    "cli_chars_now": (
        "Caracteres: {m} (opciones: auto | unicode | ascii)",
        "Characters: {m} (options: auto | unicode | ascii)",
    ),
    "cli_chars_set": ("OK  Caracteres: {m}", "OK  Characters: {m}"),
    "cli_chars_bad": ("Valor no válido. Usa: auto | unicode | ascii", "Invalid value. Use: auto | unicode | ascii"),
}


def tr(key: str, lang: str | None = None, **kw) -> str:
    pair = TR[key][0 if (lang or LANG) == "es" else 1]
    return pair.format(**kw) if kw and isinstance(pair, str) else pair


UNI = {"dir": "▸ ", "up": "↑", "down": "↓", "arrow": "→", "full": "█", "empty": "░"}
ASC = {"dir": "> ", "up": "^", "down": "v", "arrow": "->", "full": "#", "empty": "-"}


def gl(name: str) -> str:
    """Símbolo según el modo de caracteres (Unicode o ASCII)."""
    return (ASC if ASCII else UNI)[name]


# ───────────────────────── Datos guardados ────────────────────────────────


def install_paths():
    """Rutas que crea el instalador: (carpeta de la app, comando 'sshmanager')."""
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local / "sshmanager", local / "Microsoft" / "WindowsApps" / "sshmanager.bat"
    return Path.home() / ".local/share/sshmanager", Path.home() / ".local/bin/sshmanager"


def load_servers() -> list:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_servers(servers: list) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(servers, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(CONFIG, 0o600)  # solo tu usuario puede leerlo (Linux)
    except OSError:
        pass


def load_queue(key: str) -> list:
    """Fila pendiente guardada para un servidor (user@host:puerto)."""
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for it in data.get(key, []):
        try:
            out.append(
                {
                    "id": int(it["id"]),
                    "up": bool(it["up"]),
                    "name": str(it["name"]),
                    "is_dir": bool(it.get("is_dir")),
                    "src": str(it["src"]),
                    "dst": str(it["dst"]),
                    "status": "error" if it.get("status") == "error" else "pendiente",
                    "error": str(it.get("error", "")),
                    "done": 0,
                    "total": 0,
                }
            )
        except (KeyError, TypeError, ValueError):
            pass
    return out


def save_queue(key: str, items: list) -> None:
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    keep = []
    for it in items:
        if it["status"] in ("pendiente", "en curso", "error"):
            row = {k: it[k] for k in ("id", "up", "name", "is_dir", "src", "dst", "error")}
            row["status"] = "error" if it["status"] == "error" else "pendiente"
            keep.append(row)
    if keep:
        data[key] = keep
    else:
        data.pop(key, None)
    try:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        QUEUE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# ───────────────────────────── Utilidades ─────────────────────────────────


def human(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""


def local_drives() -> list:
    """Unidades de Windows sin tocar disqueteras/CD vacíos."""
    try:
        import ctypes

        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return [f"{c}:\\" for i, c in enumerate(string.ascii_uppercase) if mask & (1 << i)]
    except Exception:
        return [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]


class Stopped(Exception):
    """La transferencia se detuvo a pedido del usuario."""


class Connection:
    """Conexión SSH + SFTP."""

    def __init__(self, srv: dict, password: str | None = None):
        import paramiko  # solo hace falta al conectar

        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            srv["host"],
            port=int(srv.get("port") or 22),
            username=srv["user"],
            password=password or srv.get("password") or None,
            key_filename=srv.get("key") or None,
            timeout=10,
            banner_timeout=15,
            auth_timeout=15,
        )
        self.sftp = self.client.open_sftp()

    def close(self) -> None:
        try:
            self.sftp.close()
            self.client.close()
        except Exception:
            pass


# ───────────────────── Planificación de transferencias ────────────────────


def plan_upload(local: str, remote_dir: str):
    """Devuelve (carpetas_remotas_a_crear, [(local, remoto, tamaño)])."""
    dirs, files = [], []
    name = os.path.basename(local.rstrip("\\/"))
    target = posixpath.join(remote_dir, name)
    if os.path.isdir(local):
        dirs.append(target)
        for root, ds, fs in os.walk(local):
            rel = os.path.relpath(root, local)
            rroot = target if rel == "." else posixpath.join(target, *rel.split(os.sep))
            for d in ds:
                dirs.append(posixpath.join(rroot, d))
            for f in fs:
                lp = os.path.join(root, f)
                files.append((lp, posixpath.join(rroot, f), os.path.getsize(lp)))
    else:
        files.append((local, target, os.path.getsize(local)))
    return dirs, files


def plan_download(sftp, remote: str, local_dir: str, is_dir: bool):
    """Devuelve (carpetas_locales_a_crear, [(remoto, local, tamaño)])."""
    dirs, files = [], []
    name = posixpath.basename(remote.rstrip("/"))
    target = os.path.join(local_dir, name)
    if is_dir:
        stack = [(remote, target)]
        while stack:
            r, l = stack.pop()
            dirs.append(l)
            for a in sftp.listdir_attr(r):
                rp = posixpath.join(r, a.filename)
                lp = os.path.join(l, a.filename)
                if stat.S_ISDIR(a.st_mode or 0):
                    stack.append((rp, lp))
                else:
                    files.append((rp, lp, a.st_size or 0))
    else:
        files.append((remote, target, sftp.stat(remote).st_size or 0))
    return dirs, files


def remote_mkdir(sftp, path: str) -> None:
    try:
        sftp.mkdir(path)
    except IOError:
        pass  # ya existe


def remote_rmtree(sftp, path: str) -> None:
    for a in sftp.listdir_attr(path):
        p = posixpath.join(path, a.filename)
        if stat.S_ISDIR(a.st_mode or 0):
            remote_rmtree(sftp, p)
        else:
            sftp.remove(p)
    sftp.rmdir(path)




# ───────────────────── Textos nuevos del núcleo (v1.3) ────────────────────

TR.update(
    {
        # descargas
        "http_403": (" (acceso denegado)", " (access denied)"),
        "ssl_err": (
            "certificado no válido: revisa la fecha y hora del equipo y que ningún antivirus o proxy intercepte HTTPS",
            "invalid certificate: check your computer's date and time and that no antivirus or proxy intercepts HTTPS",
        ),
        "timeout": ("tiempo de espera agotado", "timed out"),
        "update_incomplete": ("Actualización incompleta: {e}", "Incomplete update: {e}"),
        # dependencias
        "deps_installing": (
            "Instalando dependencias: {pkgs} (solo la primera vez)...",
            "Installing dependencies: {pkgs} (first run only)...",
        ),
        "deps_ok": ("OK  Dependencias instaladas.", "OK  Dependencies installed."),
        "deps_venv": (
            "El Python del sistema está protegido: uso un entorno propio en {d}",
            "The system Python is protected: using a private environment at {d}",
        ),
        "deps_retry_net": (
            "Conexión inestable, reintento ({n}/{m})...",
            "Unstable connection, retrying ({n}/{m})...",
        ),
        "deps_fix_ssl": (
            "Error de certificado: reintento con el almacén de certificados del sistema...",
            "Certificate error: retrying with the system certificate store...",
        ),
        "deps_ask_insecure": (
            "¿Reintentar confiando en pypi.org sin verificar el certificado? (menos seguro)",
            "Retry trusting pypi.org without verifying the certificate? (less secure)",
        ),
        "deps_fix_cache": ("Descarga dañada: reintento sin caché...", "Corrupted download: retrying without cache..."),
        "deps_fix_pip": ("Actualizo pip y reintento...", "Upgrading pip and retrying..."),
        "deps_fix_nopip": ("Falta pip: lo instalo con ensurepip...", "pip is missing: installing it with ensurepip..."),
        "deps_fail": (
            "ERROR No se pudieron instalar las dependencias ({kind}).",
            "ERROR Could not install the dependencies ({kind}).",
        ),
        "deps_last": ("Último error de pip:", "Last pip error:"),
        "hint_network": (
            "Revisa tu conexión a internet. Si usas proxy, define HTTPS_PROXY (ej: set HTTPS_PROXY=http://host:puerto) y vuelve a intentar.",
            "Check your internet connection. If you use a proxy, set HTTPS_PROXY (e.g. set HTTPS_PROXY=http://host:port) and try again.",
        ),
        "hint_ssl": (
            "Revisa que la fecha y hora del equipo sean correctas y que ningún antivirus o proxy intercepte HTTPS.",
            "Make sure your computer's date and time are correct and that no antivirus or proxy intercepts HTTPS.",
        ),
        "hint_space": (
            "No hay espacio en disco. Libera espacio y vuelve a intentar.",
            "No disk space left. Free some space and try again.",
        ),
        "hint_build": (
            "Falta un compilador o librerías de desarrollo. En Debian/Ubuntu: sudo apt install build-essential python3-dev libffi-dev. En Windows usa Python 3.10-3.13 de python.org (trae todo precompilado).",
            "A compiler or development libraries are missing. On Debian/Ubuntu: sudo apt install build-essential python3-dev libffi-dev. On Windows use Python 3.10-3.13 from python.org (everything is precompiled).",
        ),
        "hint_venv": (
            "Falta el módulo venv. En Debian/Ubuntu: sudo apt install python3-venv. En Fedora: sudo dnf install python3. En Arch/CachyOS ya viene incluido.",
            "The venv module is missing. On Debian/Ubuntu: sudo apt install python3-venv. On Fedora: sudo dnf install python3. Arch/CachyOS already include it.",
        ),
        "hint_python_old": (
            "Tu Python es demasiado antiguo (se necesita 3.9 o superior). Instala uno más nuevo desde python.org.",
            "Your Python is too old (3.9 or newer is required). Install a newer one from python.org.",
        ),
        "hint_permission": (
            "No hay permisos para instalar. Ejecuta de nuevo sin sudo ni administrador: la app usa su propio entorno.",
            "No permission to install. Run again without sudo or administrator: the app uses its own environment.",
        ),
        "hint_managed": (
            "Tu Python está protegido por el sistema. Instala 'python3-venv' (Debian/Ubuntu) y vuelve a ejecutar.",
            "Your Python is protected by the system. Install 'python3-venv' (Debian/Ubuntu) and run again.",
        ),
        "hint_unknown": (
            "Prueba 'sshmanager --doctor' para ver un diagnóstico y luego 'sshmanager --repair'.",
            "Try 'sshmanager --doctor' for a diagnosis, then 'sshmanager --repair'.",
        ),
        "repair_start": (
            "Reparando: limpio la caché de pip y reinstalo las dependencias...",
            "Repairing: clearing pip's cache and reinstalling dependencies...",
        ),
        "repair_done": ("OK  Reparación terminada.", "OK  Repair finished."),
        "doctor_title": ("Diagnóstico de {app}", "{app} diagnostics"),
        "d_python": ("Python {v} (se necesita 3.9 o superior)", "Python {v} (3.9 or newer required)"),
        "d_env": ("Entorno: {e}", "Environment: {e}"),
        "d_env_venv": ("entorno virtual", "virtual environment"),
        "d_env_system": ("Python del sistema", "system Python"),
        "d_pip": ("pip disponible", "pip available"),
        "d_module": ("Módulo {m}", "Module {m}"),
        "d_net": ("Conexión a {h}", "Connection to {h}"),
        "d_config": ("Carpeta de ajustes escribible: {d}", "Settings folder writable: {d}"),
        "d_link": ("Enlace con la app {k}: {s}", "Link with the {k} app: {s}"),
        "d_link_on": ("conectada", "connected"),
        "d_link_off": ("no está abierta", "not open"),
        "d_core": ("Núcleo sshmanager v{v}", "sshmanager core v{v}"),
        # enlace TUI <-> GUI
        "k_gui": ("App gráfica", "GUI app"),
        "gui_missing": (
            "La app gráfica no está instalada. Instálala con: {cmd}",
            "The graphical app is not installed. Install it with: {cmd}",
        ),
        "gui_opening": ("Abriendo la app gráfica...", "Opening the graphical app..."),
        "gui_sent": (
            "Se pidió a la app gráfica abrir '{name}'",
            "Asked the graphical app to open '{name}'",
        ),
        "gui_fail": ("No se pudo abrir la app gráfica: {e}", "Could not open the graphical app: {e}"),
        "tui_missing": (
            "sshmanager (terminal) no está instalado. Instálalo con: {cmd}",
            "sshmanager (terminal) is not installed. Install it with: {cmd}",
        ),
        "tui_sent": (
            "Se pidió a la terminal abrir '{name}'",
            "Asked the terminal app to open '{name}'",
        ),
        "tui_opening": ("Abriendo la terminal...", "Opening the terminal..."),
        "tui_fail": ("No se pudo abrir la terminal: {e}", "Could not open the terminal: {e}"),
        "no_terminal": ("No encontré un programa de terminal para abrir", "I could not find a terminal program to open"),
        "link_open": ("La otra app pidió abrir '{name}'", "The other app asked to open '{name}'"),
        "server_unknown": ("No existe el servidor '{name}'", "There is no server named '{name}'"),
        "link_servers": (
            "Servidores actualizados desde la otra app",
            "Servers updated from the other app",
        ),
        "link_queue": ("Fila actualizada desde la otra app", "Queue updated from the other app"),
        "cli_gui": ("Abriendo la app gráfica...", "Opening the graphical app..."),
        "cli_core_old": (
            "La app gráfica necesita sshmanager 1.3 o superior. Actualiza con: sshmanager -u",
            "The graphical app needs sshmanager 1.3 or newer. Update with: sshmanager -u",
        ),
    }
)

# ───────────────────── Listado y operaciones de archivos ──────────────────


def list_local(path: str) -> list:
    """Archivos de una carpeta del equipo: (nombre, es_carpeta, tamaño, oculto, fecha)."""
    out = []
    if path == "":
        return [(d, True, 0, False, 0) for d in local_drives()]
    with os.scandir(path) as it:
        for e in it:
            try:
                st = e.stat()
                d = e.is_dir()
                s = 0 if d else st.st_size
                attrs = getattr(st, "st_file_attributes", 0)  # Windows: oculto=2, sistema=4
                hidden = e.name.startswith(".") or bool(attrs & 0x6)
                mtime = st.st_mtime
            except OSError:
                d, s, hidden, mtime = False, 0, True, 0  # sin acceso: se oculta por defecto
            out.append((e.name, d, s, hidden, mtime))
    out.sort(key=lambda x: (not x[1], x[0].lower()))
    return out


def list_remote(sftp, path: str) -> list:
    """Archivos de una carpeta del servidor: (nombre, es_carpeta, tamaño, oculto, fecha)."""
    out = []
    for a in sftp.listdir_attr(path):
        m = a.st_mode or 0
        d = stat.S_ISDIR(m)
        if stat.S_ISLNK(m):
            try:
                d = stat.S_ISDIR(sftp.stat(posixpath.join(path, a.filename)).st_mode)
            except Exception:
                pass
        out.append((a.filename, d, 0 if d else (a.st_size or 0), a.filename.startswith("."), a.st_mtime or 0))
    out.sort(key=lambda x: (not x[1], x[0].lower()))
    return out


def parent_local(path: str):
    """Carpeta superior en el equipo (None si ya es la raíz; '' = lista de unidades en Windows)."""
    if path == "":
        return None
    p = Path(path)
    if p.parent == p:
        return "" if os.name == "nt" else None
    return str(p.parent)


def parent_remote(path: str):
    if path == "/":
        return None
    return posixpath.dirname(path.rstrip("/")) or "/"


def delete_local(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def delete_remote(sftp, path: str) -> None:
    if stat.S_ISDIR(sftp.lstat(path).st_mode or 0):
        remote_rmtree(sftp, path)
    else:
        sftp.remove(path)


def mkdir_checked(name: str) -> None:
    if not name or "/" in name or "\\" in name:
        raise ValueError(tr("bad_dirname"))


# ───────────────────── Motor de transferencias (fila) ─────────────────────


def transfer_item(sftp, it: dict, stop: threading.Event, tick) -> None:
    """Transfiere un elemento de la fila. tick(item, archivo) informa el avance (se llama desde el hilo)."""
    up, name, sp, dp = it["up"], it["name"], it["src"], it["dst"]
    if up:
        dirs, files = plan_upload(os.path.join(sp, name), dp)
        for d in dirs:
            remote_mkdir(sftp, d)
    else:
        dirs, files = plan_download(sftp, posixpath.join(sp, name), dp, it["is_dir"])
        for d in dirs:
            os.makedirs(d, exist_ok=True)
    total = sum(f[2] for f in files)
    denom = total or 1
    it["total"], it["done"] = denom, 0
    done = 0
    last = [0.0]
    for s, d, size in files:
        label = os.path.basename(s)

        def cb(sent, _total, base=done, label=label):
            if stop.is_set():
                raise Stopped()
            it["done"] = base + sent
            now = time.monotonic()
            if now - last[0] > 0.1:
                last[0] = now
                tick(it, label)

        if stop.is_set():
            raise Stopped()
        if up:
            sftp.put(s, d, callback=cb)
        else:
            sftp.get(s, d, callback=cb)
        done += size
        it["done"] = done
        tick(it, label)
    it["done"] = denom
    it["total"] = denom


def run_queue(conn, queue: list, ids: list, stop: threading.Event, hooks) -> None:
    """Ejecuta elementos de la fila, uno tras otro. Bloquea: llamar desde un hilo.

    hooks.item_update(item, estado) · hooks.tick(item, archivo) · hooks.done(ok, errores, mensaje)
    """
    ok = err = 0
    try:
        sftp = conn.client.open_sftp()  # canal propio: no choca con la navegación
    except Exception as e:
        hooks.done(0, 0, tr("sftp_fail", e=e))
        return
    try:
        for i in ids:
            if stop.is_set():
                break
            it = next((x for x in queue if x["id"] == i), None)
            if it is None or it["status"] != "pendiente":
                continue
            hooks.item_update(it, "en curso")
            try:
                transfer_item(sftp, it, stop, hooks.tick)
                hooks.item_update(it, "listo")
                ok += 1
            except Stopped:
                hooks.item_update(it, "pendiente")
                break
            except Exception as e:
                it["error"] = str(e) or type(e).__name__
                hooks.item_update(it, "error")
                err += 1
    finally:
        try:
            sftp.close()
        except Exception:
            pass
    hooks.done(ok, err, None)


ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class RemoteCommand:
    """Ejecuta un comando en el servidor y entrega la salida por líneas."""

    def __init__(self, conn, cmd: str, cwd: str):
        self.conn, self.cmd, self.cwd = conn, cmd, cwd
        self.chan = None
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        try:
            if self.chan is not None:
                self.chan.close()
        except Exception:
            pass

    def run(self, emit) -> None:
        """Bloquea hasta terminar. emit(lista_de_líneas, estilo)."""
        code = None
        try:
            # En servidores Windows (rutas tipo /C:/...) no se usa 'cd'.
            if not self.cwd or re.match(r"^/[A-Za-z]:", self.cwd):
                full = self.cmd
            else:
                full = f"cd {shlex.quote(self.cwd)} && {self.cmd}"
            chan = self.conn.client.get_transport().open_session()
            self.chan = chan
            chan.set_combine_stderr(True)
            chan.exec_command(full)
            chan.shutdown_write()  # el comando no queda esperando teclado
            dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
            pend = ""
            while True:
                if chan.recv_ready():
                    data = chan.recv(8192)
                    if not data:
                        break
                    pend += dec.decode(data)
                    pend = ANSI.sub("", pend).replace("\r\n", "\n").replace("\r", "\n")
                    *lines, pend = pend.split("\n")
                    if lines:
                        emit(lines, "")
                elif chan.exit_status_ready() or chan.closed:
                    if chan.recv_ready():
                        continue
                    break
                else:
                    time.sleep(0.05)
            if pend:
                emit([pend], "")
            if chan.exit_status_ready():
                code = chan.recv_exit_status()
            chan.close()
        except Exception as e:
            emit([f"{tr('error')}: {e}"], "red")
        if self.cancelled:
            emit([tr("cmd_cancelled")], "yellow")
        elif code is not None:
            emit([tr("cmd_exit", c=code)], "dim" if code == 0 else "red")


# ─────────────── Descargas robustas y actualizaciones (GitHub) ────────────


class NetworkError(Exception):
    """No se pudo llegar a GitHub."""


class UpdateError(Exception):
    """El archivo remoto no es válido."""


RETRY_DELAY = float(os.environ.get("SSHMANAGER_RETRY_DELAY", "1.5"))


def vkey(v: str) -> tuple:
    """Orden de versiones: 1.3.0-beta.2 < 1.3.0 < 1.3.1"""
    base, _, pre = v.strip().lstrip("v").partition("-")
    nums = tuple(int(x) for x in re.findall(r"\d+", base))
    nums += (0,) * (3 - len(nums))
    pre_n = re.findall(r"\d+", pre)
    return (nums, 0 if pre else 1, int(pre_n[0]) if pre_n else 0)


def parse_version(src: str):
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M)
    return m.group(1) if m else None


def fetch_text(url: str, timeout: float = 8.0, attempts: int = 3) -> str:
    """Descarga un texto. Reintenta con pausa si la red falla o GitHub responde 5xx/429."""
    last = ""
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": f"sshmanager/{__version__}", "Cache-Control": "no-cache"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read(5_000_000)
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise UpdateError(tr("bad_file"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < attempts - 1:
                time.sleep(RETRY_DELAY * (i + 1))
                continue
            hint = tr("http_404") if e.code == 404 else (tr("http_403") if e.code == 403 else "")
            raise NetworkError(tr("http_reply", code=e.code) + hint)
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, ssl.SSLError):
                raise NetworkError(tr("ssl_err"))
            last = str(reason)
        except ssl.SSLError:
            raise NetworkError(tr("ssl_err"))
        except (socket.timeout, TimeoutError):
            last = tr("timeout")
        except OSError as e:
            last = str(e)
        if i < attempts - 1:
            time.sleep(RETRY_DELAY * (i + 1))
    raise NetworkError(last or tr("no_conn"))


class Project:
    """Un programa que se actualiza desde GitHub (varios archivos, uno principal con __version__)."""

    def __init__(self, name: str, repo: str, files: list, main_file: str, target_dir: Path):
        self.name, self.repo = name, repo
        self.files, self.main_file, self.target_dir = files, main_file, Path(target_dir)

    def base(self) -> str:
        return os.environ.get(f"{self.name.upper()}_UPDATE_BASE") or f"https://raw.githubusercontent.com/{self.repo}/main"


def fetch_update(project: Project, current: str):
    """Devuelve (versión_remota, archivos) y archivos=None si ya estás al día."""
    base = project.base().rstrip("/")
    main_src = fetch_text(f"{base}/{project.main_file}")
    remote = parse_version(main_src)
    if not remote:
        raise UpdateError(tr("not_ssh"))
    if vkey(remote) <= vkey(current):
        return remote, None
    sources = {project.main_file: main_src}
    for f in project.files:
        if f not in sources:
            sources[f] = fetch_text(f"{base}/{f}")
    for f, src in sources.items():
        try:
            compile(src, f, "exec")  # valida que sea Python correcto
        except SyntaxError as e:
            raise UpdateError(tr("update_incomplete", e=f"{f}: {e}"))
    return remote, sources


def apply_update(project: Project, sources: dict) -> None:
    """Reemplaza los archivos (deja copia .bak de cada uno). Primero escribe todo, luego reemplaza."""
    d = project.target_dir
    tmps = {}
    for f, src in sources.items():
        tmp = d / (f + ".new")
        tmp.write_text(src, encoding="utf-8")
        tmps[f] = tmp
    for f, tmp in tmps.items():
        target = d / f
        if target.exists():
            try:
                shutil.copy2(target, d / (f + ".bak"))
            except OSError:
                pass
        os.replace(tmp, target)


# ───────────── Dependencias automáticas y corrección de errores ───────────

PIP_RULES = [
    ("managed", ("externally-managed-environment", "externally managed")),
    ("nopip", ("no module named pip", "no module named 'pip'")),
    ("badflag", ("no such option", "invalid choice", "unrecognized arguments")),
    ("ssl", ("certificate_verify_failed", "ssl: ", "sslerror", "ssl error", "certificate verify", "tlsv1 alert", "suitable tls ca certificate")),
    ("space", ("no space left on device", "errno 28", "not enough space")),
    ("permission", ("permission denied", "errno 13", "access is denied", "winerror 5", "permissionerror")),
    (
        "cache",
        (
            "do not match the hashes",
            "hash mismatch",
            "badzipfile",
            "bad zipfile",
            "invalid wheel",
            "checksum",
            "could not unpack",
            "unexpected end of",
            "eoferror",
            "corrupt",
        ),
    ),
    ("python_old", ("requires a different python", "requires-python", "requires python")),
    (
        "build",
        (
            "failed building wheel",
            "microsoft visual c++",
            "command 'gcc' failed",
            "legacy-install-failure",
            "could not build wheels",
            "error: subprocess-exited-with-error",
        ),
    ),
    (
        "network",
        (
            "connection",
            "timed out",
            "temporary failure in name resolution",
            "max retries exceeded",
            "proxyerror",
            "network is unreachable",
            "name or service not known",
            "read timed out",
            "remote end closed",
            "failed to establish",
        ),
    ),
    ("oldpip", ("could not find a version that satisfies", "no matching distribution found")),
]


def classify_pip_error(text: str) -> str:
    """Reconoce el tipo de error de pip a partir de su salida."""
    t = (text or "").lower()
    for kind, needles in PIP_RULES:
        if any(n in t for n in needles):
            return kind
    return "unknown"


def _ask_yes_no(question: str) -> bool:
    try:
        return input(f"{question} {tr('yn')} ").strip().lower() in tr("yes_words")
    except (EOFError, OSError):
        return False


def pip_install_robust(python: str, specs: list, say=print, ask=None, force: bool = False):
    """pip install con corrección automática de errores comunes. Devuelve (ok, tipo_de_error, salida)."""
    base = [python, "-m", "pip", "install", "--disable-pip-version-check", "--retries", "3", "--timeout", "30"]
    if force:
        base.append("--force-reinstall")
    groups: list = []  # opciones extra que se van añadiendo según el error
    tried: set = set()
    net = 0
    kind, last = "unknown", ""
    for _ in range(14):
        extra = [x for g in groups for x in g]
        try:
            res = subprocess.run(base + extra + list(specs), capture_output=True, text=True, timeout=1500)
            out, rc = (res.stdout or "") + (res.stderr or ""), res.returncode
        except subprocess.TimeoutExpired:
            out, rc = "timed out", 1
        except OSError as e:
            out, rc = str(e), 1
        if rc == 0:
            return True, "", out
        last, kind = out, classify_pip_error(out)
        if kind in ("managed", "permission", "space", "python_old"):
            return False, kind, last
        if kind == "badflag":  # una opción que añadimos no existe en este pip: la quitamos
            if groups:
                groups.pop()
                continue
            break
        if kind == "nopip" and "nopip" not in tried:
            tried.add("nopip")
            say(tr("deps_fix_nopip"))
            try:
                subprocess.run([python, "-m", "ensurepip", "--upgrade"], capture_output=True, text=True, timeout=300)
            except (OSError, subprocess.TimeoutExpired):
                pass
            continue
        if kind == "ssl":
            if "truststore" not in tried:
                tried.add("truststore")
                say(tr("deps_fix_ssl"))
                groups.append(["--use-feature=truststore"])
                continue
            if "insecure" not in tried and ask and ask(tr("deps_ask_insecure")):
                tried.add("insecure")
                groups.append(
                    ["--trusted-host", "pypi.org", "--trusted-host", "files.pythonhosted.org", "--trusted-host", "pypi.python.org"]
                )
                continue
            break
        if kind == "network" and net < 3:
            net += 1
            say(tr("deps_retry_net", n=net, m=3))
            time.sleep(RETRY_DELAY * (net + 1))
            continue
        if kind == "cache" and "cache" not in tried:
            tried.add("cache")
            say(tr("deps_fix_cache"))
            groups.append(["--no-cache-dir"])
            continue
        if kind in ("oldpip", "build") and "pip" not in tried:
            tried.add("pip")
            say(tr("deps_fix_pip"))
            try:
                subprocess.run(
                    [python, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "pip"],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            if kind == "build":
                groups.append(["--only-binary=:all:"])
            continue
        break
    return False, kind, last


def venv_python(venv_dir: Path) -> Path:
    return Path(venv_dir) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def modules_missing(reqs: list) -> list:
    return [(m, spec) for m, spec in reqs if importlib.util.find_spec(m) is None]


def _env_has(python: Path, reqs: list) -> bool:
    code = ";".join(f"import {m}" for m, _ in reqs)
    try:
        return subprocess.run([str(python), "-c", code], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _reexec(python: Path, script: str, argv: list):
    """Vuelve a ejecutar el programa con el Python del entorno propio."""
    os.environ["SSHMANAGER_BOOTSTRAPPED"] = "1"
    if os.name == "nt":
        sys.exit(subprocess.call([str(python), script, *argv]))
    os.execv(str(python), [str(python), script, *argv])


def _make_private_env(venv_dir: Path, specs: list, say, ask):
    py = venv_python(venv_dir)
    if not py.exists():
        base_py = getattr(sys, "_base_executable", None) or sys.executable
        try:
            res = subprocess.run([base_py, "-m", "venv", str(venv_dir)], capture_output=True, text=True, timeout=600)
            out, rc = (res.stdout or "") + (res.stderr or ""), res.returncode
        except (OSError, subprocess.TimeoutExpired) as e:
            out, rc = str(e), 1
        if rc != 0:
            shutil.rmtree(venv_dir, ignore_errors=True)
            low = out.lower()
            kind = "venv" if ("ensurepip" in low or "python3-venv" in low or "no module named venv" in low) else classify_pip_error(out)
            return False, kind, out
    return pip_install_robust(str(py), specs, say, ask)


def dependency_failure(kind: str, log: str, say=print):
    say(tr("deps_fail", kind=kind))
    key = "hint_" + kind
    say(tr(key) if key in TR else tr("hint_unknown"))
    tail = [ln for ln in (log or "").strip().splitlines() if ln.strip()][-5:]
    if tail:
        say(tr("deps_last"))
        for ln in tail:
            say("  " + ln[:200])
    sys.exit(1)


def ensure_dependencies(reqs: list, script: str, argv: list, venv_dir: Path, say=print) -> None:
    """Instala lo que falte (con corrección de errores). Si el Python está protegido usa un entorno propio."""
    missing = modules_missing(reqs)
    if not missing:
        return
    if sys.version_info < (3, 9):
        dependency_failure("python_old", "", say)
    interactive = sys.stdin is not None and sys.stdin.isatty()
    ask = _ask_yes_no if interactive else None
    specs = [spec for _, spec in reqs]
    in_private = os.environ.get("SSHMANAGER_BOOTSTRAPPED") == "1"
    vpy = venv_python(venv_dir)
    # 1) ¿ya existe el entorno propio con todo instalado? Se usa directamente (sin mensajes).
    if vpy.exists() and not in_private and _env_has(vpy, reqs):
        _reexec(vpy, script, argv)
    say(tr("deps_installing", pkgs=", ".join(spec for _, spec in missing)))
    # 2) instalar en el Python actual (entorno virtual o Python sin protección)
    ok, kind, log = pip_install_robust(sys.executable, [s for _, s in missing], say, ask)
    if ok:
        importlib.invalidate_caches()
        if not modules_missing(reqs):
            say(tr("deps_ok"))
            return
        kind, log = "unknown", "installed but not importable"
    # 3) Python protegido (PEP 668) o sin permisos: entorno propio
    if kind in ("managed", "permission", "unknown") and not in_private:
        say(tr("deps_venv", d=venv_dir))
        ok, kind, log = _make_private_env(Path(venv_dir), specs, say, ask)
        if ok:
            say(tr("deps_ok"))
            _reexec(vpy, script, argv)
    dependency_failure(kind, log, say)


def repair_dependencies(reqs: list, venv_dir: Path, say=print) -> int:
    """Limpia la caché de pip y reinstala las dependencias (no borra nada tuyo)."""
    say(tr("repair_start"))
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    py = sys.executable
    if not in_venv and venv_python(venv_dir).exists():
        py = str(venv_python(venv_dir))
    try:
        subprocess.run([py, "-m", "pip", "cache", "purge"], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        pass
    ok, kind, log = pip_install_robust(py, [s for _, s in reqs], say, _ask_yes_no if sys.stdin and sys.stdin.isatty() else None, force=True)
    if not ok and kind in ("managed", "permission"):
        ok, kind, log = _make_private_env(Path(venv_dir), [s for _, s in reqs], say, None)
    if not ok:
        dependency_failure(kind, log, say)
    say(tr("repair_done"))
    return 0


def doctor(app: str, reqs: list, other_kind: str, say=print) -> int:
    """Diagnóstico rápido de los problemas más comunes."""
    bad = 0

    def line(good: bool, text: str):
        nonlocal bad
        bad += 0 if good else 1
        say(f"  [{'OK' if good else 'FAIL'}] {text}")

    say(tr("doctor_title", app=app))
    line(sys.version_info >= (3, 9), tr("d_python", v=sys.version.split()[0]))
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    line(True, tr("d_env", e=tr("d_env_venv") if in_venv else tr("d_env_system")))
    line(importlib.util.find_spec("pip") is not None, tr("d_pip"))
    for m, _ in reqs:
        line(importlib.util.find_spec(m) is not None, tr("d_module", m=m))
    line(True, tr("d_core", v=__version__))
    for host, url in (("pypi.org", "https://pypi.org/simple/pip/"), ("raw.githubusercontent.com", "https://raw.githubusercontent.com/")):
        try:
            urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=6)
            good = True
        except urllib.error.HTTPError:
            good = True  # el servidor respondió: hay conexión
        except Exception:
            good = False
        line(good, tr("d_net", h=host))
    try:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        probe = CONFIG.parent / ".write_test"
        probe.write_text("x")
        probe.unlink()
        writable = True
    except OSError:
        writable = False
    line(writable, tr("d_config", d=CONFIG.parent))
    on = link_alive(other_kind)
    say(f"  [--] {tr('d_link', k=other_kind.upper(), s=tr('d_link_on') if on else tr('d_link_off'))}")
    return 1 if bad else 0


# ─────────────────────── Enlace entre la terminal y la GUI ────────────────

LINK_DIR = CONFIG.parent / "link"


def link_entries(kind: str) -> list:
    out = []
    try:
        files = sorted(LINK_DIR.glob(f"{kind}-*.json"))
    except OSError:
        return out
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["_path"] = str(p)
            out.append(data)
        except (OSError, ValueError):
            pass
    return out


class LinkServer:
    """Pequeño servidor local (solo 127.0.0.1, con clave) para que la terminal y la GUI se hablen."""

    def __init__(self, kind: str, handler, version: str = ""):
        self.kind, self.handler, self.version = kind, handler, version
        self.token = secrets.token_hex(16)
        self.sock = None
        self.path = None
        self.port = 0
        self.running = False

    def start(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 0))
            s.listen(8)
        except OSError:
            return False
        self.sock, self.port, self.running = s, s.getsockname()[1], True
        try:
            LINK_DIR.mkdir(parents=True, exist_ok=True)
            self.path = LINK_DIR / f"{self.kind}-{os.getpid()}.json"
            self.path.write_text(
                json.dumps(
                    {"kind": self.kind, "pid": os.getpid(), "port": self.port, "token": self.token, "version": self.version}
                ),
                encoding="utf-8",
            )
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except OSError:
            self.stop()
            return False
        threading.Thread(target=self._loop, daemon=True).start()
        atexit.register(self.stop)
        return True

    def _loop(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                break
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        try:
            conn.settimeout(3)
            data = b""
            while b"\n" not in data and len(data) < 65536:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            msg = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
            if not hmac.compare_digest(str(msg.get("token", "")), self.token):
                reply = {"ok": False, "error": "token"}
            elif msg.get("cmd") == "ping":
                reply = {"ok": True, "kind": self.kind, "version": self.version}
            else:
                reply = self.handler(msg) or {"ok": True}
        except Exception as e:
            reply = {"ok": False, "error": str(e)}
        try:
            conn.sendall((json.dumps(reply) + "\n").encode("utf-8"))
        except OSError:
            pass
        finally:
            conn.close()

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        try:
            if self.path:
                self.path.unlink()
        except OSError:
            pass


def link_send(kind: str, msg: dict, all_instances: bool = False, timeout: float = 1.5):
    """Manda un mensaje a la otra app. Devuelve su respuesta (o None si no está abierta)."""
    replies = []
    for e in link_entries(kind):
        try:
            with socket.create_connection(("127.0.0.1", int(e["port"])), timeout=timeout) as c:
                c.settimeout(timeout)
                c.sendall((json.dumps({**msg, "token": e["token"]}) + "\n").encode("utf-8"))
                data = b""
                while b"\n" not in data:
                    chunk = c.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            reply = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
            if reply.get("ok"):
                if not all_instances:
                    return reply
                replies.append(reply)
        except ConnectionRefusedError:
            try:
                Path(e["_path"]).unlink()  # quedó de una app que ya se cerró
            except OSError:
                pass
        except (OSError, ValueError, KeyError):
            pass
    return replies if all_instances else None


def link_alive(kind: str) -> bool:
    return link_send(kind, {"cmd": "ping"}) is not None


def link_notify(kind: str, msg: dict) -> None:
    """Avisa a la otra app sin bloquear la interfaz."""
    threading.Thread(target=lambda: link_send(kind, msg, all_instances=True), daemon=True).start()


GUI_INSTALL_HINT = "curl -fsSL https://raw.githubusercontent.com/superc839e/sshmanagerapp/main/instalar_linux.sh | bash"
TUI_INSTALL_HINT = "curl -fsSL https://raw.githubusercontent.com/superc839e/sshmanager/main/instalar_linux.sh | bash"


def gui_install_paths():
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local / "sshmanagerapp", local / "Microsoft" / "WindowsApps" / "sshmanagerapp.bat"
    return Path.home() / ".local/share/sshmanagerapp", Path.home() / ".local/bin/sshmanagerapp"


def _command_or_launcher(name: str, launcher: Path):
    found = shutil.which(name)
    if found:
        return [found]
    return [str(launcher)] if launcher.exists() else None


def find_gui_command():
    return _command_or_launcher("sshmanagerapp", gui_install_paths()[1])


def find_tui_command():
    return _command_or_launcher("sshmanager", install_paths()[1])


def _detached(args: list) -> None:
    if os.name == "nt":
        subprocess.Popen(args, creationflags=0x00000008 | 0x00000200, close_fds=True)  # DETACHED | NEW_GROUP
    else:
        subprocess.Popen(
            args, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


def launch_gui(server: str | None = None):
    """Abre la app gráfica (o le pide que abra un servidor si ya está abierta). Devuelve (ok, mensaje)."""
    if server:
        if link_send("gui", {"cmd": "open_server", "name": server}):
            return True, tr("gui_sent", name=server)
    elif link_alive("gui"):
        link_send("gui", {"cmd": "show"})
        return True, tr("gui_opening")
    cmd = find_gui_command()
    if not cmd:
        return False, tr("gui_missing", cmd=GUI_INSTALL_HINT)
    try:
        _detached(cmd + (["--connect", server] if server else []))
    except OSError as e:
        return False, tr("gui_fail", e=e)
    return True, tr("gui_opening")


def terminal_wrapper(args: list):
    """Comando para ejecutar `args` dentro de una ventana de terminal nueva."""
    if os.name == "nt":
        wt = shutil.which("wt")
        return [wt] + args if wt else ["cmd", "/c", "start", "", "cmd", "/k"] + args
    for name in (os.environ.get("TERMINAL"), "x-terminal-emulator", "kitty", "alacritty", "wezterm", "konsole",
                 "gnome-terminal", "xfce4-terminal", "tilix", "foot", "xterm"):
        exe = shutil.which(name) if name else None
        if not exe:
            continue
        base = Path(exe).name
        if base in ("gnome-terminal", "tilix"):
            return [exe, "--"] + args
        if base == "wezterm":
            return [exe, "start", "--"] + args
        if base in ("kitty", "foot"):
            return [exe] + args
        if base == "xfce4-terminal":
            return [exe, "-x"] + args
        return [exe, "-e"] + args
    return None


def launch_tui(server: str | None = None):
    """Abre sshmanager (terminal) en una ventana nueva, o le pide que abra el servidor. (ok, mensaje)"""
    if server and link_send("tui", {"cmd": "open_server", "name": server}):
        return True, tr("tui_sent", name=server)
    cmd = find_tui_command()
    if not cmd:
        return False, tr("tui_missing", cmd=TUI_INSTALL_HINT)
    args = cmd + (["--connect", server] if server else [])
    wrapped = terminal_wrapper(args)
    if not wrapped:
        return False, tr("no_terminal")
    try:
        _detached(wrapped)
    except OSError as e:
        return False, tr("tui_fail", e=e)
    return True, tr("tui_opening")


def find_server(name: str):
    """Servidor guardado por nombre (sin distinguir mayúsculas)."""
    for s in load_servers():
        if s.get("name", "").lower() == name.lower():
            return s
    return None


def server_key(srv: dict) -> str:
    return f'{srv["user"]}@{srv["host"]}:{srv.get("port", 22)}'
