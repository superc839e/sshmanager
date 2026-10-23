#!/usr/bin/env python3
"""
SSH Manager — cliente SSH/SFTP con interfaz de terminal.
Funciona igual en Windows y Linux. Sin comandos: todo con teclado o mouse.

Dependencias:  pip install textual paramiko
Más información:  sshmanager -h
"""
from __future__ import annotations

import codecs
import json
import os
import posixpath
import re
import shlex
import shutil
import socket
import stat
import string
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import paramiko
from rich.markup import escape
from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, RichLog, Static

__version__ = "1.1.0"
REPO_URL = "https://github.com/superc839e/sshmanager"
UPDATE_URL = os.environ.get(
    "SSHMANAGER_UPDATE_URL",
    "https://raw.githubusercontent.com/superc839e/sshmanager/main/ssh_manager.py",
)

# ───────────────────────── Configuración guardada ─────────────────────────


def config_file() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "sshmanager" / "servers.json"


CONFIG = config_file()
QUEUE_FILE = CONFIG.with_name("queue.json")


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
    return [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]


class Stopped(Exception):
    """La transferencia se detuvo a pedido del usuario."""


class Connection:
    """Conexión SSH + SFTP."""

    def __init__(self, srv: dict, password: str | None = None):
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


# ───────────────────── Actualizaciones (GitHub) ───────────────────────────


class NetworkError(Exception):
    """No se pudo llegar a GitHub."""


class UpdateError(Exception):
    """El archivo remoto no es válido."""


def vtuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def fetch_update(timeout: float = 6.0):
    """Descarga ssh_manager.py de GitHub. Devuelve (versión_remota, código)."""
    req = urllib.request.Request(
        UPDATE_URL,
        headers={"User-Agent": f"sshmanager/{__version__}", "Cache-Control": "no-cache"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(3_000_000)
    except urllib.error.HTTPError as e:
        hint = " (no se encontró el archivo en GitHub)" if e.code == 404 else ""
        raise NetworkError(f"GitHub respondió {e.code}{hint}")
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
        raise NetworkError(str(getattr(e, "reason", e)) or "sin conexión")
    try:
        src = data.decode("utf-8")
    except UnicodeDecodeError:
        raise UpdateError("El archivo descargado no es válido")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M)
    if not m:
        raise UpdateError("El archivo descargado no parece ser SSH Manager")
    return m.group(1), src


def apply_update(src: str) -> None:
    """Reemplaza este archivo por la versión nueva (deja una copia .bak)."""
    compile(src, "ssh_manager.py", "exec")  # valida que sea Python correcto
    target = Path(__file__).resolve()
    tmp = target.with_name(target.name + ".new")
    tmp.write_text(src, encoding="utf-8")
    try:
        shutil.copy2(target, target.with_name(target.name + ".bak"))
    except OSError:
        pass
    os.replace(tmp, target)


# ───────────────────────── Línea de comandos ──────────────────────────────

MANUAL = f"""\
SSH Manager v{__version__} — cliente SSH/SFTP sin comandos

USO
  sshmanager          Abre la aplicación
  sshmanager -h       Muestra este manual
  sshmanager -v       Muestra la versión
  sshmanager -u       Actualiza desde GitHub
  sshmanager -d       Desinstala la aplicación

AL ABRIR
  Busca actualizaciones en GitHub con una pantalla de carga. Si no hay
  internet lo marca como error de red y sigue. Esc salta la búsqueda.

LISTA DE SERVIDORES
  Enter conectar   n nuevo   e editar   x borrar
  u buscar actualizaciones   q salir

EXPLORACIÓN (PC a la izquierda, servidor a la derecha)
  Tab cambiar de panel      Enter abrir carpeta     Backspace subir
  t transferir ya           a añadir a la fila      f ver la fila
  c consola                 n nueva carpeta         x borrar
  r refrescar               h mostrar/ocultar ocultos
  Esc desconectar

FILA DE TRANSFERENCIAS
  Cada elemento recuerda su origen y su destino, aunque cambies de carpeta.
  Si cierras la app, lo pendiente se guarda para la próxima vez.
  s iniciar/detener   x quitar   r reintentar fallidos
  l limpiar terminados   Esc volver

CONSOLA
  Muestra lo que hace la app (conexiones, transferencias, errores) y permite
  escribir comandos para ejecutarlos en el servidor, en la carpeta abierta.
  No admite programas interactivos (nano, top...). F4 cancela. Esc vuelve.

ARCHIVOS
  Servidores   {CONFIG}
  Fila         {QUEUE_FILE}

Proyecto: {REPO_URL}
"""


def yes_no(question: str) -> bool:
    try:
        return input(f"{question} [s/N] ").strip().lower() in ("s", "si", "sí", "y", "yes")
    except EOFError:
        return False


def cli_update() -> int:
    print(f"SSH Manager v{__version__} — buscando actualizaciones en GitHub…")
    try:
        remote, src = fetch_update()
    except NetworkError as e:
        print(f"✖ Error de red: {e}")
        return 1
    except UpdateError as e:
        print(f"✖ {e}")
        return 1
    if vtuple(remote) <= vtuple(__version__):
        print(f"✔ Ya tienes la última versión (v{__version__}).")
        return 0
    print(f"Nueva versión disponible: v{remote}. Instalando…")
    try:
        apply_update(src)
    except Exception as e:
        print(f"✖ No se pudo actualizar: {e}")
        return 1
    print(f"✔ Actualizado a v{remote}.")
    return 0


def cli_uninstall() -> int:
    app_dir, launcher = install_paths()
    cfg_dir = CONFIG.parent
    has_app = (app_dir / "ssh_manager.py").exists()
    has_launcher = launcher.exists()
    if not (has_app or has_launcher):
        print("No encontré una instalación hecha con el instalador. No se borró nada.")
        return 1
    print("Se eliminará:")
    if has_app:
        print(f"  • {app_dir}")
    if has_launcher:
        print(f"  • {launcher}  (el comando sshmanager)")
    if not yes_no("¿Desinstalar SSH Manager?"):
        print("Cancelado.")
        return 0
    wipe = cfg_dir.exists() and yes_no(f"¿Borrar también tus servidores guardados y la fila? ({cfg_dir})")
    if os.name == "nt":
        # Windows no deja borrar el python que está corriendo: lo borra un proceso aparte.
        parts = ["ping -n 3 127.0.0.1 >nul"]
        if has_app:
            parts.append(f'rmdir /s /q "{app_dir}"')
        if has_launcher:
            parts.append(f'del /f /q "{launcher}"')
        subprocess.Popen(
            'cmd /c "' + " & ".join(parts) + '"',
            creationflags=0x08000000 | 0x00000008,
            close_fds=True,
        )
    else:
        if has_launcher:
            launcher.unlink()
        if has_app:
            shutil.rmtree(app_dir)
    if wipe and cfg_dir.name == "sshmanager":
        shutil.rmtree(cfg_dir, ignore_errors=True)
    print("✔ SSH Manager desinstalado." + (" Se conservaron tus servidores." if not wipe and cfg_dir.exists() else ""))
    return 0


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


# ───────────────────────────── Ventanas modales ───────────────────────────


class Confirm(ModalScreen):
    BINDINGS = [("escape", "no", "No")]

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label(self.text, markup=False)
            with Horizontal(classes="buttons"):
                yield Button("Sí", variant="error", id="yes")
                yield Button("No", id="no")

    def on_mount(self):
        self.query_one("#no").focus()

    def on_button_pressed(self, event):
        self.dismiss(event.button.id == "yes")

    def action_no(self):
        self.dismiss(False)


class Ask(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, text: str, password: bool = False):
        super().__init__()
        self.text = text
        self.password = password

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label(self.text, markup=False)
            yield Input(password=self.password, id="answer")
            with Horizontal(classes="buttons"):
                yield Button("Aceptar", variant="primary", id="ok")
                yield Button("Cancelar", id="cancel")

    def on_input_submitted(self, event):
        self.dismiss(event.value)

    def on_button_pressed(self, event):
        self.dismiss(self.query_one("#answer", Input).value if event.button.id == "ok" else None)

    def action_cancel(self):
        self.dismiss(None)


class ServerForm(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancelar")]

    def __init__(self, srv: dict | None = None):
        super().__init__()
        self.srv = srv or {}

    def compose(self):
        s = self.srv
        with VerticalScroll(classes="dialog"):
            yield Label("Servidor", classes="ptitle")
            yield Label("Nombre (ej. Mi VPS)")
            yield Input(s.get("name", ""), id="name")
            yield Label("Host o IP")
            yield Input(s.get("host", ""), id="host")
            yield Label("Puerto")
            yield Input(str(s.get("port", 22)), id="port", type="integer")
            yield Label("Usuario")
            yield Input(s.get("user", ""), id="user")
            yield Label("Contraseña (opcional)")
            yield Input(s.get("password", ""), id="password", password=True)
            yield Label("Archivo de llave privada (opcional)")
            yield Input(s.get("key", ""), id="key")
            with Horizontal(classes="buttons"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", id="cancel")

    def _save(self):
        v = {k: self.query_one(f"#{k}", Input).value.strip() for k in ("name", "host", "port", "user", "key")}
        v["password"] = self.query_one("#password", Input).value
        if not (v["name"] and v["host"] and v["user"]):
            self.notify("Nombre, host y usuario son obligatorios", severity="error")
            return
        v["port"] = int(v["port"] or 22)
        self.dismiss(v)

    def on_input_submitted(self, event):
        self._save()

    def on_button_pressed(self, event):
        if event.button.id == "save":
            self._save()
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


# ─────────────────────────── Pantalla de carga ────────────────────────────

_BANNER = r"""
 ____ ____  _   _
/ ___/ ___|| | | |
\___ \___ \| |_| |
 ___) |__) |  _  |
|____/____/|_| |_|
M  A  N  A  G  E  R
"""
_lines = _BANNER.strip("\n").split("\n")
_w = max(len(x) for x in _lines)
BANNER = "\n".join(x.center(_w) for x in _lines)
BAR_W = 28


class SplashScreen(Screen):
    """Pantalla de carga ASCII: busca actualizaciones en GitHub."""

    BINDINGS = [Binding("escape,enter,space", "skip", "Saltar", show=False)]

    def __init__(self, manual: bool = False):
        super().__init__()
        self.manual = manual
        self.frame = 0
        self.entered = False
        self.updating = False

    def compose(self):
        with Vertical(id="splash"):
            yield Static(BANNER, id="banner", markup=False)
            yield Label(f"v{__version__}", id="ver")
            yield Label("", id="bar", markup=False)
            yield Label("Buscando actualizaciones…", id="msg", markup=False)
            yield Label("Esc: saltar", id="skiphint")

    def on_mount(self):
        self.anim = self.set_interval(0.07, self._tick)
        self.run_worker(self._check, thread=True, group="update")

    # ---- animación ----
    def _tick(self):
        n = BAR_W - 5
        p = self.frame % (2 * n)
        pos = p if p <= n else 2 * n - p
        self.frame += 1
        self._set_bar("[" + " " * pos + "<=>" + " " * (n - pos) + "]")

    def _set_bar(self, text: str, cls: str = ""):
        bar = self.query_one("#bar", Label)
        bar.update(Text(text))
        bar.set_class(cls == "err", "err")
        bar.set_class(cls == "ok", "ok")

    def _msg(self, text: str, cls: str = ""):
        m = self.query_one("#msg", Label)
        m.update(Text(text))
        m.set_class(cls == "err", "err")
        m.set_class(cls == "ok", "ok")

    def _stop_bar(self, ok: bool):
        self.anim.stop()
        self._set_bar("[" + ("█" if ok else "x") * (BAR_W - 2) + "]", "ok" if ok else "err")

    # ---- búsqueda ----
    def _check(self):
        try:
            remote, src = fetch_update()
            self.app.call_from_thread(self._result, remote, src, None)
        except (NetworkError, UpdateError) as e:
            self.app.call_from_thread(self._result, None, None, e)
        except Exception as e:
            self.app.call_from_thread(self._result, None, None, NetworkError(repr(e)))

    def _result(self, remote, src, err):
        app = self.app
        if err is not None:
            kind = "Error de red" if isinstance(err, NetworkError) else "Error"
            app.update_status = f"⚠ No se pudo buscar actualizaciones: {err}"
            app.say(app.update_status, "red")
            if self.entered:
                return
            self._stop_bar(False)
            self._msg(f"✖ {kind}: {err}", "err")
            self.set_timer(2.5, self._enter)
            return
        if vtuple(remote) > vtuple(__version__):
            app.update_status = f"⬆ Hay una versión nueva: v{remote}"
            app.say(f"Versión nueva disponible: v{remote} (tienes v{__version__})", "yellow")
            if self.entered:
                return
            self._stop_bar(True)
            self._msg(f"Versión {remote} disponible (tienes {__version__})", "ok")
            app.push_screen(
                Confirm(f"Hay una versión nueva ({remote}). Tienes la {__version__}.\n¿Actualizar ahora?"),
                lambda yes: self._apply(remote, src) if yes else self._enter(),
            )
            return
        app.update_status = ""
        app.say(f"Búsqueda de actualizaciones: ya tienes la última versión (v{__version__})")
        if self.entered:
            return
        self._stop_bar(True)
        self._msg(f"✔ Estás en la última versión ({__version__})", "ok")
        self.set_timer(0.9, self._enter)

    def _apply(self, remote: str, src: str):
        self.updating = True
        self._msg("Instalando actualización…")

        def job():
            try:
                apply_update(src)
                self.app.call_from_thread(self._applied, remote, None)
            except Exception as e:
                self.app.call_from_thread(self._applied, remote, e)

        self.run_worker(job, thread=True, group="update")

    def _applied(self, remote: str, err):
        self.updating = False
        if err is not None:
            self.app.say(f"No se pudo actualizar: {err}", "red")
            self._msg(f"✖ No se pudo actualizar: {err}", "err")
            self.set_timer(2.5, self._enter)
            return
        self.app.say(f"Actualizado a v{remote}", "green")
        self._msg(f"✔ Actualizado a v{remote}. Reiniciando…", "ok")
        self.set_timer(
            1.5,
            lambda: self.app.exit(message=f"✔ SSH Manager actualizado a v{remote}. Vuelve a ejecutar: sshmanager"),
        )

    # ---- salida ----
    def action_skip(self):
        if not self.updating:
            self._enter()

    def _enter(self):
        if self.entered:
            return
        self.entered = True
        self.anim.stop()
        if self.manual:
            self.app.pop_screen()
        else:
            self.app.switch_screen(ServersScreen())


# ─────────────────────────── Panel de archivos ────────────────────────────


class Panel(Vertical):
    """Un panel de archivos: 'local' (este equipo) o 'remote' (servidor)."""

    def __init__(self, kind: str, conn: Connection):
        super().__init__(id=f"panel-{kind}")
        self.kind = kind
        self.conn = conn
        self.path = ""
        self.items: list = []  # (nombre, es_carpeta, tamaño)
        self.entries: dict = {}  # nombre -> es_carpeta
        self.show_hidden = False

    def compose(self):
        yield Label("Este equipo" if self.kind == "local" else "Servidor", classes="ptitle")
        yield Label("", id=f"path-{self.kind}", classes="ppath", markup=False)
        yield DataTable(id=self.kind, cursor_type="row", zebra_stripes=True)

    # ---- listado ----
    def _list(self, path: str) -> list:
        out = []
        if self.kind == "local":
            if path == "":
                return [(d, True, 0) for d in local_drives()]
            with os.scandir(path) as it:
                for e in it:
                    try:
                        d = e.is_dir()
                        s = 0 if d else e.stat().st_size
                    except OSError:
                        d, s = False, 0
                    out.append((e.name, d, s))
        else:
            sftp = self.conn.sftp
            for a in sftp.listdir_attr(path):
                m = a.st_mode or 0
                d = stat.S_ISDIR(m)
                if stat.S_ISLNK(m):
                    try:
                        d = stat.S_ISDIR(sftp.stat(posixpath.join(path, a.filename)).st_mode)
                    except Exception:
                        pass
                out.append((a.filename, d, 0 if d else (a.st_size or 0)))
        out.sort(key=lambda x: (not x[1], x[0].lower()))
        return out

    def parent_path(self):
        if self.kind == "local":
            if self.path == "":
                return None
            p = Path(self.path)
            if p.parent == p:
                return "" if os.name == "nt" else None
            return str(p.parent)
        if self.path == "/":
            return None
        return posixpath.dirname(self.path.rstrip("/")) or "/"

    def go(self, path, select=None):
        def job():
            try:
                p = path
                if p is None:
                    p = self.conn.sftp.normalize(".")
                items = self._list(p)
            except Exception as e:
                self.app.call_from_thread(self.app.report, str(e), "error", "No se pudo abrir")
                return
            self.app.call_from_thread(self._fill, p, items, select)

        self.run_worker(job, thread=True, group="load", exclusive=True)

    def reload(self):
        sel = None
        try:
            t = self.query_one(DataTable)
            if t.row_count:
                sel = t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value
        except Exception:
            pass
        self.go(self.path, select=sel)

    def _fill(self, path, items, select):
        self.path = path
        self.items = items
        self.entries = {n: d for n, d, _ in items}
        self.query_one(f"#path-{self.kind}", Label).update(Text(path or "Unidades"))
        self.render_table(select)

    def render_table(self, select=None):
        t = self.query_one(DataTable)
        if not t.columns:
            t.add_column("Nombre")
            t.add_column("Tamaño")
        t.clear()
        if self.parent_path() is not None:
            t.add_row(Text("▸ .."), Text(""), key="..")
        for n, d, s in self.items:
            if n.startswith(".") and not self.show_hidden:
                continue
            if d:
                t.add_row(Text("▸ " + n, style="bold cyan"), Text(""), key=n)
            else:
                t.add_row(Text("  " + n), Text(human(s), justify="right"), key=n)
        if select is not None:
            try:
                t.move_cursor(row=t.get_row_index(select))
            except Exception:
                pass

    # ---- navegación ----
    def open(self, name: str):
        if name == "..":
            par = self.parent_path()
            if par is None:
                return
            if self.kind == "local":
                sel = os.path.basename(self.path.rstrip("\\/")) or self.path
            else:
                sel = posixpath.basename(self.path.rstrip("/"))
            self.go(par, select=sel)
            return
        if self.entries.get(name):
            if self.kind == "local":
                self.go(os.path.join(self.path, name))
            else:
                self.go(posixpath.join(self.path, name))

    # ---- operaciones ----
    def _op(self, fn, okmsg: str):
        def job():
            try:
                fn()
                self.app.call_from_thread(self.app.say, okmsg)
            except Exception as e:
                self.app.call_from_thread(self.app.report, str(e), "error", "Error")
            self.app.call_from_thread(self.reload)

        self.run_worker(job, thread=True, group="ops")

    def mkdir(self, name: str):
        def fn():
            if "/" in name or "\\" in name:
                raise ValueError("Nombre de carpeta inválido")
            if self.kind == "local":
                os.makedirs(os.path.join(self.path, name), exist_ok=True)
            else:
                self.conn.sftp.mkdir(posixpath.join(self.path, name))

        where = "PC" if self.kind == "local" else "Servidor"
        self._op(fn, f"Carpeta creada en {where}: {name}")

    def delete(self, name: str):
        def fn():
            if self.kind == "local":
                p = os.path.join(self.path, name)
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            else:
                sftp = self.conn.sftp
                p = posixpath.join(self.path, name)
                if stat.S_ISDIR(sftp.lstat(p).st_mode or 0):
                    remote_rmtree(sftp, p)
                else:
                    sftp.remove(p)

        where = "PC" if self.kind == "local" else "Servidor"
        self._op(fn, f"Borrado en {where}: {name}")


# ───────────────────────────── Pantalla: consola ──────────────────────────

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class ConsoleScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Volver"),
        Binding("f4", "cancel", "Cancelar comando"),
        Binding("ctrl+l", "clear", "Limpiar"),
    ]

    def __init__(self, browser: "BrowserScreen"):
        super().__init__()
        self.browser = browser
        self.chan = None
        self.running = False
        self.cancelled = False

    def compose(self):
        yield Header()
        yield Label(
            "Consola — eventos de la app y comandos en el servidor (sin programas interactivos como nano o top)",
            id="hint",
            markup=False,
        )
        yield RichLog(id="log", wrap=True, highlight=False, markup=False, max_lines=2000)
        yield Input(placeholder="Comando para ejecutar en el servidor y Enter…", id="cmd")
        yield Footer()

    def on_mount(self):
        for line in self.app.console_buffer:
            self.show(line)
        self.query_one("#cmd", Input).focus()

    def show(self, line):
        ts, text, style = line
        self.query_one(RichLog).write(Text(f"{ts}  {text}", style=style))

    def action_clear(self):
        self.query_one(RichLog).clear()
        self.app.console_buffer.clear()

    def action_back(self):
        self.browser.panel("remote").reload()  # por si el comando cambió archivos
        self.app.pop_screen()

    def action_cancel(self):
        if self.running and self.chan is not None:
            self.cancelled = True
            try:
                self.chan.close()
            except Exception:
                pass

    def on_input_submitted(self, event):
        cmd = event.value.strip()
        event.input.value = ""
        if not cmd:
            return
        if self.running:
            self.notify("Ya hay un comando en ejecución (F4 para cancelar)", severity="warning")
            return
        cwd = self.browser.panel("remote").path
        self.running = True
        self.cancelled = False
        self.app.say(f"$ {cmd}", "bold green")
        self.run_worker(lambda: self._exec(cmd, cwd), thread=True, group="cmd")

    def _emit(self, lines, style=""):
        if lines:
            self.app.call_from_thread(self.app.say_many, lines, style)

    def _exec(self, cmd: str, cwd: str):
        code = None
        try:
            # En servidores Windows (rutas tipo /C:/...) no se usa 'cd'.
            if not cwd or re.match(r"^/[A-Za-z]:", cwd):
                full = cmd
            else:
                full = f"cd {shlex.quote(cwd)} && {cmd}"
            chan = self.browser.conn.client.get_transport().open_session()
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
                    self._emit(lines)
                elif chan.exit_status_ready() or chan.closed:
                    if chan.recv_ready():
                        continue
                    break
                else:
                    time.sleep(0.05)
            if pend:
                self._emit([pend])
            if chan.exit_status_ready():
                code = chan.recv_exit_status()
            chan.close()
        except Exception as e:
            self._emit([f"Error: {e}"], "red")
        if self.cancelled:
            self._emit(["(comando cancelado)"], "yellow")
        elif code is not None:
            self._emit([f"[código de salida: {code}]"], "dim" if code == 0 else "red")
        self.app.call_from_thread(self._finished)

    def _finished(self):
        self.running = False
        self.chan = None


# ───────────────────────────── Pantalla: fila ─────────────────────────────

STATUS_STYLE = {
    "pendiente": ("… pendiente", "yellow"),
    "en curso": ("▶ en curso", "bold cyan"),
    "listo": ("✔ listo", "green"),
    "error": ("✖ error", "bold red"),
}


class QueueScreen(Screen):
    BINDINGS = [
        Binding("s", "toggle", "Iniciar/Detener"),
        Binding("x,delete", "remove", "Quitar"),
        Binding("r", "retry", "Reintentar fallidos"),
        Binding("l", "clear", "Limpiar terminados"),
        Binding("escape,q", "back", "Volver"),
    ]

    def __init__(self, browser: "BrowserScreen"):
        super().__init__()
        self.browser = browser

    def compose(self):
        yield Header()
        yield Label("Fila de transferencias — cada elemento recuerda de dónde viene y a dónde va", id="hint", markup=False)
        yield DataTable(id="qtable", cursor_type="row", zebra_stripes=True)
        yield Label("", id="status", markup=False)
        yield Footer()

    def on_mount(self):
        t = self.query_one(DataTable)
        for c in ("Estado", "Tipo", "Nombre", "Origen", "Destino", "Avance"):
            t.add_column(c)
        self.refresh_rows()
        t.focus()

    def selected_id(self):
        t = self.query_one(DataTable)
        if t.row_count == 0:
            return None
        return int(t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value)

    def refresh_rows(self):
        t = self.query_one(DataTable)
        sel = self.selected_id()
        t.clear()
        q = self.browser.queue
        for it in q:
            label, style = STATUS_STYLE[it["status"]]
            up = it["up"]
            if it["status"] == "error":
                prog = it["error"][:60]
            elif it["status"] in ("en curso", "listo") and it["total"]:
                prog = f'{min(it["done"] / it["total"], 1):.0%}'
            else:
                prog = ""
            t.add_row(
                Text(label, style=style),
                Text("↑ Subir" if up else "↓ Bajar"),
                Text(("▸ " if it["is_dir"] else "") + it["name"]),
                Text(("PC: " if up else "Servidor: ") + it["src"]),
                Text(("Servidor: " if up else "PC: ") + it["dst"]),
                Text(prog),
                key=str(it["id"]),
            )
        if sel is not None:
            try:
                t.move_cursor(row=t.get_row_index(str(sel)))
            except Exception:
                pass
        n = lambda s: sum(1 for i in q if i["status"] == s)
        if q:
            summary = f'{n("pendiente")} pendiente(s) · {n("en curso")} en curso · {n("listo")} listo(s) · {n("error")} con error'
        else:
            summary = "La fila está vacía. En la exploración usa 'a' para añadir lo seleccionado."
        self.query_one("#status", Label).update(Text(summary))

    def _item(self):
        i = self.selected_id()
        return next((it for it in self.browser.queue if it["id"] == i), None)

    def action_toggle(self):
        self.browser.toggle_queue()

    def action_remove(self):
        it = self._item()
        if it is None:
            return
        if it["status"] == "en curso":
            self.notify("Detén la fila antes de quitar un elemento en curso", severity="warning")
            return
        self.browser.queue.remove(it)
        self.browser.queue_changed()

    def action_retry(self):
        n = 0
        for it in self.browser.queue:
            if it["status"] == "error":
                it["status"], it["error"] = "pendiente", ""
                n += 1
        self.browser.queue_changed()
        self.notify(f"{n} elemento(s) vuelven a pendiente" if n else "No hay elementos con error")

    def action_clear(self):
        self.browser.queue[:] = [i for i in self.browser.queue if i["status"] != "listo"]
        self.browser.queue_changed()

    def action_back(self):
        self.app.pop_screen()


# ───────────────────────── Pantalla de exploración ────────────────────────


class BrowserScreen(Screen):
    BINDINGS = [
        Binding("tab", "swap", "Cambiar panel"),
        Binding("t,f5", "transfer", "Transferir ya"),
        Binding("a", "enqueue", "A la fila"),
        Binding("f", "show_queue", "Ver fila"),
        Binding("c", "console", "Consola"),
        Binding("n", "mkdir", "Nueva carpeta"),
        Binding("x,delete", "delete", "Borrar"),
        Binding("r", "refresh", "Refrescar"),
        Binding("h", "hidden", "Ocultos"),
        Binding("backspace", "up", "Subir", show=False),
        Binding("escape,q", "disconnect", "Desconectar"),
    ]

    def __init__(self, conn: Connection, title: str, srv: dict):
        super().__init__()
        self.conn = conn
        self.srv_title = title
        self.qkey = f'{srv["user"]}@{srv["host"]}:{srv.get("port", 22)}'
        self.queue: list = load_queue(self.qkey)
        self.next_id = max((i["id"] for i in self.queue), default=0) + 1
        self.stop = threading.Event()
        self.busy = False

    def compose(self):
        yield Header()
        with Horizontal(id="panels"):
            yield Panel("local", self.conn)
            yield Panel("remote", self.conn)
        yield Label("", id="status", markup=False)
        yield Footer()

    def on_mount(self):
        self.app.sub_title = self.srv_title
        self.set_status(self.idle_status())
        if self.queue:
            msg = f"Se restauró la fila de este servidor: {len(self.queue)} elemento(s) pendiente(s) (f para verla)"
            self.app.say(msg)
            self.notify(msg)
        self.call_after_refresh(self._start)

    def _start(self):
        self.panel("local").go(str(Path.home()))
        self.panel("remote").go(None)
        self.query_one("#local").focus()

    # ---- ayudas ----
    def panel(self, kind: str) -> Panel:
        return self.query_one(f"#panel-{kind}", Panel)

    def active(self) -> Panel:
        f = self.focused
        return self.panel("remote" if f is not None and f.id == "remote" else "local")

    def other(self) -> Panel:
        return self.panel("local" if self.active().kind == "remote" else "remote")

    def selected(self, panel: Panel):
        t = panel.query_one(DataTable)
        if t.row_count == 0:
            return None
        key = t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value
        return None if key == ".." else key

    def set_status(self, text: str):
        self.query_one("#status", Label).update(Text(text))

    def idle_status(self) -> str:
        n = sum(1 for i in self.queue if i["status"] in ("pendiente", "error"))
        base = "Tab: cambiar panel · Enter: abrir · t: transferir ya · a: a la fila · c: consola"
        return base + (f" · Fila: {n} pendiente(s) (f)" if n else "")

    def _ui(self, fn, *args):
        self.app.call_from_thread(fn, *args)

    # ---- navegación y acciones simples ----
    def on_data_table_row_selected(self, event):
        self.panel(event.data_table.id).open(event.row_key.value)

    def action_swap(self):
        self.query_one(f"#{self.other().kind}").focus()

    def action_up(self):
        self.active().open("..")

    def action_refresh(self):
        self.panel("local").reload()
        self.panel("remote").reload()

    def action_hidden(self):
        for k in ("local", "remote"):
            p = self.panel(k)
            p.show_hidden = not p.show_hidden
            p.render_table()

    def action_mkdir(self):
        p = self.active()
        if p.path == "":
            self.notify("Entra primero a una unidad", severity="warning")
            return
        self.app.push_screen(
            Ask("Nombre de la nueva carpeta:"),
            lambda v: p.mkdir(v.strip()) if v and v.strip() else None,
        )

    def action_delete(self):
        p = self.active()
        name = self.selected(p)
        if name is None:
            return
        donde = "este equipo" if p.kind == "local" else "el servidor"
        extra = " y todo su contenido" if p.entries.get(name) else ""
        self.app.push_screen(
            Confirm(f"¿Borrar '{name}'{extra} de {donde}? No se puede deshacer."),
            lambda ok: p.delete(name) if ok else None,
        )

    def action_console(self):
        self.app.push_screen(ConsoleScreen(self))

    def action_show_queue(self):
        self.app.push_screen(QueueScreen(self))

    def action_disconnect(self):
        if self.busy:
            self.notify("Espera a que termine la fila (o detenla desde 'f')", severity="warning")
            return
        pend = sum(1 for i in self.queue if i["status"] in ("pendiente", "error"))
        self.conn.close()
        self.app.say(f"Desconectado de {self.srv_title}")
        if pend:
            self.app.notify(f"La fila quedó guardada: {pend} elemento(s) pendiente(s)")
        self.app.sub_title = ""
        self.app.pop_screen()

    # ---- fila de transferencias ----
    def describe(self, it: dict) -> str:
        up = it["up"]
        a, b = ("PC", "Servidor") if up else ("Servidor", "PC")
        return f'{"↑" if up else "↓"} {it["name"]}  ({a}: {it["src"]} → {b}: {it["dst"]})'

    def queue_save(self):
        save_queue(self.qkey, self.queue)

    def queue_refresh(self):
        for scr in list(self.app.screen_stack):
            if isinstance(scr, QueueScreen):
                try:
                    scr.refresh_rows()
                except NoMatches:
                    pass
        if not self.busy:
            try:
                self.set_status(self.idle_status())
            except NoMatches:
                pass

    def queue_changed(self):
        self.queue_save()
        self.queue_refresh()

    def _validate(self):
        src, dst = self.active(), self.other()
        name = self.selected(src)
        if name is None:
            self.notify("Selecciona un archivo o carpeta primero", severity="warning")
            return None
        if src.path == "" or dst.path == "":
            self.notify("Entra a una carpeta (no a la lista de unidades)", severity="warning")
            return None
        item = {
            "id": 0,
            "up": src.kind == "local",
            "name": name,
            "is_dir": bool(src.entries.get(name)),
            "src": src.path,
            "dst": dst.path,
            "status": "pendiente",
            "error": "",
            "done": 0,
            "total": 0,
        }
        return item, name in dst.entries

    def _add(self, item: dict, quiet: bool = False):
        item["id"] = self.next_id
        self.next_id += 1
        self.queue.append(item)
        self.queue_changed()
        self.app.say(f"Fila: añadido {self.describe(item)}")
        if not quiet:
            self.notify(f"Añadido a la fila: {item['name']}")

    def action_enqueue(self):
        v = self._validate()
        if v is None:
            return
        item, exists = v
        sig = lambda i: (i["up"], i["name"], i["src"], i["dst"])
        if any(sig(i) == sig(item) and i["status"] in ("pendiente", "error") for i in self.queue):
            self.notify("Ya está en la fila con el mismo origen y destino", severity="warning")
            return
        if exists:
            self.app.push_screen(
                Confirm(f"'{item['name']}' ya existe en el destino y se sobrescribirá al ejecutar la fila. ¿Añadir igual?"),
                lambda ok: self._add(item) if ok else None,
            )
        else:
            self._add(item)

    def action_transfer(self):
        v = self._validate()
        if v is None:
            return
        item, exists = v
        if exists:
            self.app.push_screen(
                Confirm(f"'{item['name']}' ya existe en el destino. ¿Sobrescribir?"),
                lambda ok: self._now(item) if ok else None,
            )
        else:
            self._now(item)

    def _now(self, item: dict):
        self._add(item, quiet=True)
        if self.busy:
            self.notify("Hay una transferencia en curso: quedó en la fila", severity="warning")
            return
        self.run_items([item["id"]])

    def toggle_queue(self):
        if self.busy:
            self.stop.set()
            self.notify("Deteniendo la fila…")
            return
        ids = [i["id"] for i in self.queue if i["status"] == "pendiente"]
        if not ids:
            self.notify("La fila no tiene elementos pendientes", severity="warning")
            return
        self.run_items(ids)

    def run_items(self, ids: list):
        if self.busy:
            return
        self.busy = True
        self.stop.clear()
        self.set_status("Iniciando…")
        self.run_worker(lambda: self._run(ids), thread=True, group="transfer")

    # ---- ejecución (hilo aparte) ----
    def _run(self, ids: list):
        ok = err = 0
        try:
            sftp = self.conn.client.open_sftp()  # canal propio, no choca con la navegación
        except Exception as e:
            self._ui(self._queue_done, 0, 0, f"No se pudo abrir un canal SFTP: {e}")
            return
        try:
            for i in ids:
                if self.stop.is_set():
                    break
                it = next((x for x in self.queue if x["id"] == i), None)
                if it is None or it["status"] != "pendiente":
                    continue
                self._ui(self._item_update, it, "en curso")
                try:
                    self._transfer(sftp, it)
                    self._ui(self._item_update, it, "listo")
                    ok += 1
                except Stopped:
                    self._ui(self._item_update, it, "pendiente")
                    break
                except Exception as e:
                    it["error"] = str(e) or type(e).__name__
                    self._ui(self._item_update, it, "error")
                    err += 1
        finally:
            try:
                sftp.close()
            except Exception:
                pass
        self._ui(self._queue_done, ok, err, None)

    def _transfer(self, sftp, it: dict):
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
                if self.stop.is_set():
                    raise Stopped()
                it["done"] = base + sent
                now = time.monotonic()
                if now - last[0] > 0.1:
                    last[0] = now
                    self._ui(self._tick, it, label)

            if self.stop.is_set():
                raise Stopped()
            if up:
                sftp.put(s, d, callback=cb)
            else:
                sftp.get(s, d, callback=cb)
            done += size
            it["done"] = done
            self._ui(self._tick, it, label)
        it["done"] = denom
        it["total"] = denom

    # ---- actualizaciones de interfaz (hilo principal) ----
    def _tick(self, it: dict, label: str):
        frac = min(it["done"] / (it["total"] or 1), 1.0)
        n = int(frac * 20)
        bar = "█" * n + "░" * (20 - n)
        arrow = "↑" if it["up"] else "↓"
        self.set_status(f"{arrow} {label}  {bar} {frac:4.0%}  {human(it['done'])} / {human(it['total'])}")
        for scr in list(self.app.screen_stack):
            if isinstance(scr, QueueScreen):
                try:
                    scr.refresh_rows()
                except NoMatches:
                    pass

    def _item_update(self, it: dict, status: str):
        it["status"] = status
        d = self.describe(it)
        if status == "en curso":
            it["error"] = ""
            self.app.say(f"▶ {d}")
        elif status == "listo":
            self.app.say(f"✔ {d}", "green")
        elif status == "error":
            self.app.say(f"✖ {d}: {it['error']}", "red")
            self.notify(escape(it["error"]), title=f"Error: {it['name']}", severity="error")
        elif status == "pendiente":
            self.app.say(f"⏸ Detenido: {d}", "yellow")
        self.queue_changed()

    def _queue_done(self, ok: int, err: int, msg):
        self.busy = False
        stopped = self.stop.is_set()
        if msg is None:
            msg = f"Fila terminada: {ok} lista(s), {err} con error"
            if stopped:
                msg = f"Fila detenida: {ok} lista(s), {err} con error"
        self.app.report(msg, "error" if err or msg.startswith("No se pudo") else "information")
        self.set_status(("✖ " if err else "✔ ") + msg)
        self.panel("local").reload()
        self.panel("remote").reload()
        self.queue_refresh()


# ─────────────────────── Pantalla de servidores guardados ─────────────────


class ServersScreen(Screen):
    BINDINGS = [
        Binding("n", "new", "Nuevo"),
        Binding("e", "edit", "Editar"),
        Binding("x,delete", "remove", "Borrar"),
        Binding("u", "update", "Actualizaciones"),
        Binding("q", "app.quit", "Salir"),
    ]

    def __init__(self):
        super().__init__()
        self.servers: list = []
        self.connecting = False

    def compose(self):
        yield Header()
        yield Label("", id="hint", markup=False)
        yield Label("", id="net", markup=False)
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self):
        t = self.query_one(DataTable)
        t.add_column("Nombre")
        t.add_column("Servidor")
        t.add_column("Usuario")
        self.reload()
        self.refresh_net()
        t.focus()

    def on_screen_resume(self):
        self.refresh_net()

    def refresh_net(self):
        try:
            lab = self.query_one("#net", Label)
        except NoMatches:
            return
        s = self.app.update_status
        if s.startswith("⚠"):
            s += "  (u: reintentar)"
        elif s.startswith("⬆"):
            s += "  (u: actualizar)"
        lab.update(Text(s))
        lab.set_class(s.startswith("⚠"), "warn")
        lab.set_class(s.startswith("⬆"), "newv")

    def reload(self):
        self.servers = load_servers()
        t = self.query_one(DataTable)
        t.clear()
        for i, s in enumerate(self.servers):
            t.add_row(
                Text(s["name"], style="bold"),
                Text(f'{s["host"]}:{s.get("port", 22)}'),
                Text(s["user"]),
                key=str(i),
            )
        hint = self.query_one("#hint", Label)
        if self.servers:
            hint.update(Text("Servidores guardados — Enter: conectar · n: nuevo · e: editar · x: borrar"))
        else:
            hint.update(Text("No hay servidores guardados. Pulsa n para añadir el primero."))

    def current(self):
        t = self.query_one(DataTable)
        if t.row_count == 0:
            return None
        return int(t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value)

    def action_update(self):
        self.app.push_screen(SplashScreen(manual=True))

    def action_new(self):
        def done(v):
            if v:
                self.servers.append(v)
                save_servers(self.servers)
                self.reload()

        self.app.push_screen(ServerForm(), done)

    def action_edit(self):
        i = self.current()
        if i is None:
            return

        def done(v):
            if v:
                self.servers[i] = v
                save_servers(self.servers)
                self.reload()

        self.app.push_screen(ServerForm(self.servers[i]), done)

    def action_remove(self):
        i = self.current()
        if i is None:
            return

        def done(ok):
            if ok:
                del self.servers[i]
                save_servers(self.servers)
                self.reload()

        self.app.push_screen(Confirm(f"¿Borrar el servidor '{self.servers[i]['name']}' de la lista?"), done)

    # ---- conexión ----
    def on_data_table_row_selected(self, event):
        self.connect(self.servers[int(event.row_key.value)])

    def connect(self, srv: dict, password: str | None = None):
        if self.connecting:
            return
        self.connecting = True
        self.notify(f"Conectando a {srv['name']}…")

        def job():
            try:
                conn = Connection(srv, password)
            except paramiko.AuthenticationException:
                self.app.call_from_thread(self._need_password, srv)
                return
            except paramiko.SSHException as e:
                if "No authentication methods" in str(e):
                    self.app.call_from_thread(self._need_password, srv)
                else:
                    self.app.call_from_thread(self._failed, srv, str(e))
                return
            except Exception as e:
                self.app.call_from_thread(self._failed, srv, str(e) or type(e).__name__)
                return
            self.app.call_from_thread(self._connected, conn, srv)

        self.run_worker(job, thread=True, group="connect")

    def _failed(self, srv: dict, msg: str):
        self.connecting = False
        self.app.report(f"{srv['name']}: {msg}", "error", "No se pudo conectar")

    def _connected(self, conn: Connection, srv: dict):
        self.connecting = False
        self.app.say(f"Conectado a {srv['name']} ({srv['user']}@{srv['host']}:{srv.get('port', 22)})", "green")
        self.app.push_screen(BrowserScreen(conn, srv["name"], srv))

    def _need_password(self, srv: dict):
        self.connecting = False

        def done(pw):
            if pw:
                self.connect(srv, pw)

        self.app.push_screen(Ask(f"Contraseña para {srv['user']}@{srv['host']}:", password=True), done)


# ─────────────────────────────── Aplicación ───────────────────────────────


class SSHManager(App):
    TITLE = f"SSH Manager v{__version__}"
    CSS = """
    Panel { width: 1fr; height: 1fr; border: round $primary-darken-1; }
    Panel:focus-within { border: round $accent; }
    Panel DataTable { height: 1fr; }
    .ptitle { text-style: bold; padding: 0 1; }
    .ppath { color: $text-muted; padding: 0 1; }
    #status, #hint, #net { height: 1; padding: 0 1; color: $text-muted; }
    #net.warn { color: $error; }
    #net.newv { color: $warning; }
    ConsoleScreen #hint { color: $text-muted; }
    #log { height: 1fr; border: round $primary-darken-1; }
    #cmd { dock: bottom; }
    SplashScreen { align: center middle; }
    #splash { width: 60; height: auto; }
    #splash Static, #splash Label { width: 100%; text-align: center; }
    #banner { color: $accent; text-style: bold; margin-bottom: 1; }
    #bar { margin-top: 1; }
    #bar.ok, #msg.ok { color: $success; }
    #bar.err, #msg.err { color: $error; }
    #skiphint { color: $text-muted; margin-top: 1; }
    ModalScreen { align: center middle; }
    .dialog {
        width: 60; max-width: 95%; height: auto; max-height: 90%;
        border: thick $primary; background: $surface; padding: 1 2;
    }
    .dialog Input { margin-bottom: 1; }
    .buttons { height: auto; align-horizontal: right; }
    .buttons Button { margin-left: 2; }
    """

    def __init__(self):
        super().__init__()
        self.console_buffer: list = []  # (hora, texto, estilo)
        self.update_status = ""

    def on_mount(self):
        self.say(f"SSH Manager v{__version__} iniciado")
        self.push_screen(SplashScreen())

    # ---- consola de eventos ----
    def say(self, text: str, style: str = ""):
        line = (time.strftime("%H:%M:%S"), text, style)
        self.console_buffer.append(line)
        del self.console_buffer[:-1000]
        for scr in list(self.screen_stack):
            if isinstance(scr, ConsoleScreen):
                try:
                    scr.show(line)
                except NoMatches:
                    pass

    def say_many(self, lines: list, style: str = ""):
        for ln in lines:
            self.say(ln, style)

    def report(self, msg: str, severity: str = "information", title: str | None = None):
        """Aviso en pantalla + registro en la consola."""
        self.notify(escape(msg), title=title, severity=severity)
        prefix = f"{title}: " if title else ""
        self.say(prefix + msg, {"error": "red", "warning": "yellow"}.get(severity, ""))


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = sys.argv[1:]
    if args:
        a = args[0]
        if a in ("-h", "--help"):
            print(MANUAL)
            return
        if a in ("-v", "--version"):
            print(f"SSH Manager v{__version__}")
            return
        if a in ("-u", "--update"):
            sys.exit(cli_update())
        if a in ("-d", "--delete", "--uninstall"):
            sys.exit(cli_uninstall())
        print(f"Opción desconocida: {a}\n\nUsa: sshmanager -h")
        sys.exit(2)
    SSHManager().run()


if __name__ == "__main__":
    main()
