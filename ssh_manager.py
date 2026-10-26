#!/usr/bin/env python3
"""
SSH Manager - SSH/SFTP client with a terminal interface (Windows & Linux).
Cliente SSH/SFTP con interfaz de terminal (Windows y Linux).

Dependencies are installed automatically on first run.
Las dependencias se instalan solas la primera vez.
Help / Ayuda:  sshmanager -h
"""
from __future__ import annotations

import os
import posixpath
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

__version__ = "1.3.0"
REPO_URL = "https://github.com/superc839e/sshmanager"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _fetch_core() -> None:
    """Si falta sshmanager_core.py junto al programa, lo descarga de GitHub."""
    import urllib.request

    es = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").lower().startswith("es")
    print("Descargando sshmanager_core.py ..." if es else "Downloading sshmanager_core.py ...")
    url = "https://raw.githubusercontent.com/superc839e/sshmanager/main/sshmanager_core.py"
    last = None
    for i in range(3):
        try:
            data = urllib.request.urlopen(url, timeout=10).read()
            (HERE / "sshmanager_core.py").write_bytes(data)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    print(f"ERROR: {last}")
    sys.exit(1)


try:
    import sshmanager_core as core
except ImportError:
    _fetch_core()
    import sshmanager_core as core

from sshmanager_core import (  # noqa: E402
    CHARS_MODES,
    LANG_NAMES,
    LANGS,
    CONFIG,
    QUEUE_FILE,
    SETTINGS_FILE,
    Connection,
    LinkServer,
    NetworkError,
    RemoteCommand,
    UpdateError,
    delete_local,
    delete_remote,
    detect_ascii,
    find_server,
    gl,
    human,
    link_alive,
    link_notify,
    list_local,
    list_remote,
    load_queue,
    load_servers,
    mkdir_checked,
    parent_local,
    parent_remote,
    run_queue,
    save_queue,
    save_servers,
    tr,
)

PROJECT = core.Project("sshmanager", "superc839e/sshmanager", ["ssh_manager.py", "sshmanager_core.py"], "ssh_manager.py", HERE)
REQS = [("textual", "textual>=0.80"), ("paramiko", "paramiko>=3.0")]
VENV_DIR = core.install_paths()[0] / "venv"

# ───────────────────────── Línea de comandos ──────────────────────────────

MANUAL_ES = """\
SSH Manager v{ver} - cliente SSH/SFTP sin comandos

USO
  sshmanager                    Abre la aplicación
  sshmanager --connect NOMBRE   Abre y conecta directo a un servidor guardado
  sshmanager -h [es|en]         Muestra este manual (en el idioma elegido)
  sshmanager -v                 Muestra la versión
  sshmanager -u                 Actualiza desde GitHub (terminal y núcleo)
  sshmanager -d                 Desinstala la aplicación
  sshmanager -l [es|en]         Muestra o cambia el idioma
  sshmanager --chars [auto|unicode|ascii]
                                Muestra o cambia los caracteres de la interfaz
  sshmanager --gui [NOMBRE]     Abre la app gráfica (opcional: en un servidor)
  sshmanager --doctor           Diagnostica problemas comunes (Python, pip, red...)
  sshmanager --repair           Repara las dependencias (limpia caché y reinstala)

DEPENDENCIAS AUTOMÁTICAS
  La primera vez instala solo lo que falta (textual y paramiko). Corrige solo
  los errores comunes: Python protegido por el sistema (usa un entorno propio),
  red inestable (reintenta), certificados, descargas dañadas, pip viejo o
  ausente. Si no puede, explica qué hacer. Prueba --doctor y --repair.

APP GRÁFICA (github.com/superc839e/sshmanagerapp)
  Usa los mismos servidores, fila y ajustes que esta terminal. Con la tecla g
  abres la app gráfica, y ella puede abrir esta terminal. Si ambas están
  abiertas, se avisan al instante los cambios de servidores y de la fila.

IDIOMA Y CARACTERES
  También se cambian dentro de la app con la tecla s (Ajustes).
  Si en Windows ves símbolos raros o bordes torcidos, usa: sshmanager --chars ascii

AL ABRIR
  Busca actualizaciones en GitHub con una pantalla de carga. Si no hay
  internet lo marca como error de red y sigue. Esc salta la búsqueda.

LISTA DE SERVIDORES
  Enter conectar   n nuevo   e editar   x borrar
  u buscar actualizaciones   s ajustes   g app gráfica   q salir

EXPLORACIÓN (PC a la izquierda, servidor a la derecha)
  Tab cambiar de panel      Enter abrir carpeta     Backspace subir
  t transferir ya           a añadir a la fila      f ver la fila
  c consola                 n nueva carpeta         x borrar
  r refrescar               h mostrar/ocultar ocultos
  g abrir este servidor en la app gráfica           Esc desconectar

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
  Servidores   {cfg}
  Fila         {queue}
  Ajustes      {settings}

Proyecto: {repo}
"""

MANUAL_EN = """\
SSH Manager v{ver} - SSH/SFTP client, no commands needed

USAGE
  sshmanager                    Open the application
  sshmanager --connect NAME     Open and connect straight to a saved server
  sshmanager -h [es|en]         Show this manual (in the chosen language)
  sshmanager -v                 Show the version
  sshmanager -u                 Update from GitHub (terminal and core)
  sshmanager -d                 Uninstall the application
  sshmanager -l [es|en]         Show or change the language
  sshmanager --chars [auto|unicode|ascii]
                                Show or change the interface characters
  sshmanager --gui [NAME]       Open the graphical app (optionally on a server)
  sshmanager --doctor           Diagnose common problems (Python, pip, network...)
  sshmanager --repair           Repair dependencies (clear cache and reinstall)

AUTOMATIC DEPENDENCIES
  On first run it installs only what is missing (textual and paramiko). It
  fixes the common errors by itself: system-protected Python (uses a private
  environment), unstable network (retries), certificates, corrupted
  downloads, old or missing pip. If it cannot, it explains what to do.
  Try --doctor and --repair.

GRAPHICAL APP (github.com/superc839e/sshmanagerapp)
  Uses the same servers, queue and settings as this terminal. Press g to open
  the graphical app, and it can open this terminal. If both are open they
  notify each other instantly about changes to servers and the queue.

LANGUAGE AND CHARACTERS
  They can also be changed inside the app with the s key (Settings).
  If you see odd symbols or crooked borders on Windows, run: sshmanager --chars ascii

ON STARTUP
  Checks GitHub for updates with a loading screen. If there is no internet
  it flags a network error and carries on. Esc skips the check.

SERVER LIST
  Enter connect   n new   e edit   x delete
  u check for updates   s settings   g graphical app   q quit

BROWSER (PC on the left, server on the right)
  Tab switch panel          Enter open folder       Backspace go up
  t transfer now            a add to queue          f view queue
  c console                 n new folder            x delete
  r refresh                 h show/hide hidden files
  g open this server in the graphical app           Esc disconnect

TRANSFER QUEUE
  Every item remembers its source and destination, even if you change folders.
  If you close the app, pending items are saved for next time.
  s start/stop   x remove   r retry failed
  l clear finished   Esc back

CONSOLE
  Shows what the app does (connections, transfers, errors) and lets you type
  commands to run on the server, in the folder you have open.
  No interactive programs (nano, top...). F4 cancels. Esc goes back.

FILES
  Servers    {cfg}
  Queue      {queue}
  Settings   {settings}

Project: {repo}
"""


def manual(lang: str | None = None) -> str:
    text = MANUAL_ES if (lang or core.LANG) == "es" else MANUAL_EN
    return text.format(ver=__version__, cfg=CONFIG, queue=QUEUE_FILE, settings=SETTINGS_FILE, repo=REPO_URL)


def yes_no(question: str) -> bool:
    try:
        ans = input(f"{question} {tr('yn')} ").strip().lower()
    except EOFError:
        return False
    return ans in tr("yes_words")


def cli_update() -> int:
    print(tr("cli_checking", cur=__version__))
    try:
        remote, src = core.fetch_update(PROJECT, __version__)
    except NetworkError as e:
        print(tr("cli_net_err", e=e))
        return 1
    except UpdateError as e:
        print(f"ERROR {e}")
        return 1
    if src is None:
        print(tr("cli_latest", cur=__version__))
        return 0
    print(tr("cli_new", v=remote))
    try:
        core.apply_update(PROJECT, src)
    except Exception as e:  # noqa: BLE001
        print(tr("cli_update_fail", e=e))
        return 1
    print(tr("cli_updated", v=remote))
    return 0


def cli_uninstall() -> int:
    app_dir, launcher = core.install_paths()
    cfg_dir = CONFIG.parent
    has_app = (app_dir / "ssh_manager.py").exists()
    has_launcher = launcher.exists()
    if not (has_app or has_launcher):
        print(tr("cli_no_install"))
        return 1
    print(tr("cli_will_remove"))
    if has_app:
        print(f"  - {app_dir}")
    if has_launcher:
        print(f"  - {launcher}  {tr('cli_cmd_note')}")
    if not yes_no(tr("cli_ask_uninstall")):
        print(tr("cli_cancelled"))
        return 0
    wipe = cfg_dir.exists() and yes_no(tr("cli_ask_wipe", d=cfg_dir))
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
        print(tr("cli_win_wait"))
    else:
        if has_launcher:
            launcher.unlink()
        if has_app:
            shutil.rmtree(app_dir)
    if wipe and cfg_dir.name == "sshmanager":
        shutil.rmtree(cfg_dir, ignore_errors=True)
    print(tr("cli_uninstalled") + (tr("cli_kept") if not wipe and cfg_dir.exists() else ""))
    return 0


def cli_lang(value: str | None) -> int:
    if value is None:
        print(tr("cli_lang_now", l=core.LANG))
        return 0
    if value not in LANGS:
        print(tr("cli_lang_bad"))
        return 2
    core.apply_settings(value, core.CHARS)
    print(tr("cli_lang_set", l=LANG_NAMES[value]))
    return 0


def cli_chars(value: str | None) -> int:
    if value is None:
        print(tr("cli_chars_now", m=core.CHARS))
        return 0
    if value not in CHARS_MODES:
        print(tr("cli_chars_bad"))
        return 2
    core.apply_settings(core.LANG, value)
    print(tr("cli_chars_set", m=value))
    return 0


def cli_gui(name: str | None) -> int:
    print(tr("cli_gui"))
    ok, msg = core.launch_gui(name)
    print(msg)
    return 0 if ok else 1


def early_cli(args: list):
    """Comandos que no necesitan la interfaz ni las dependencias. Devuelve el código de salida o None."""
    if not args:
        return None
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    a = args[0]
    arg = args[1] if len(args) > 1 else None
    if a in ("-h", "--help"):
        print(manual(arg if arg in LANGS else None))
        return 0
    if a in ("-v", "--version"):
        print(f"SSH Manager v{__version__}")
        return 0
    if a in ("-u", "--update"):
        return cli_update()
    if a in ("-d", "--delete", "--uninstall"):
        return cli_uninstall()
    if a in ("-l", "--lang"):
        return cli_lang(arg)
    if a == "--chars":
        return cli_chars(arg)
    if a == "--gui":
        return cli_gui(arg)
    if a == "--doctor":
        return core.doctor("SSH Manager", REQS, "gui")
    if a == "--repair":
        return core.repair_dependencies(REQS, VENV_DIR)
    if a == "--install-deps":
        already = not core.modules_missing(REQS)
        core.ensure_dependencies(REQS, str(Path(__file__).resolve()), [], VENV_DIR)
        if already:
            print(tr("deps_ok"))
        return 0
    if a == "--connect":
        return None  # lo maneja la interfaz
    print(tr("cli_unknown", a=a))
    return 2


if __name__ == "__main__":
    _args = sys.argv[1:]
    _code = early_cli(_args)
    if _code is not None:
        sys.exit(_code)
    # Instala lo que falte (con corrección de errores) antes de cargar la interfaz
    core.ensure_dependencies(REQS, str(Path(__file__).resolve()), _args, VENV_DIR)

# ───────────────────────── Interfaz (necesita textual y paramiko) ─────────

import paramiko  # noqa: E402
from rich.markup import escape  # noqa: E402
from rich.text import Text  # noqa: E402
from textual.app import App  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Horizontal, Vertical, VerticalScroll  # noqa: E402
from textual.css.query import NoMatches  # noqa: E402
from textual.screen import ModalScreen, Screen  # noqa: E402
from textual.scrollbar import ScrollBar, ScrollBarRender  # noqa: E402
from textual.widgets import Button, DataTable, Input, Label, RichLog, Static  # noqa: E402


class SimpleScrollBarRender(ScrollBarRender):
    """Barras de desplazamiento solo con bloque lleno y espacio (existen en toda fuente de Windows)."""

    VERTICAL_BARS = ["█"] * 7 + [" "]
    HORIZONTAL_BARS = ["█"] * 7 + [" "]


def update_scrollbars() -> None:
    simple = os.name == "nt" or core.ASCII
    ScrollBar.renderer = SimpleScrollBarRender if simple else ScrollBarRender


update_scrollbars()


# ───────────────────────────── Widgets propios ────────────────────────────


class TitleBar(Static):
    """Barra de título (reemplaza al Header de Textual, que usa símbolos que fallan en Windows)."""

    def __init__(self, sub: str = ""):
        self.sub = sub
        self._online = False
        super().__init__(self._build())

    def _build(self) -> Text:
        t = Text(" SSH Manager", style="bold")
        t.append(f" v{__version__}")
        if self.sub:
            t.append("  |  " + self.sub)
        if self._online:
            t.append("  GUI ", style="bold black on green")
        return t

    def on_mount(self):
        self.set_link(getattr(self.app, "gui_online", False))

    def set_link(self, online: bool):
        if online != self._online:
            self._online = online
            self.update(self._build())


class KeyBar(Static):
    """Barra de atajos (reemplaza al Footer). Reparte los atajos en líneas sin partir ninguno."""

    def __init__(self, items):
        super().__init__("")
        self.items = items
        self._width = -1

    def on_mount(self):
        self._layout()

    def on_resize(self, event):
        self._layout()

    def _layout(self):
        width = max(self.size.width - 2, 20)
        if width == self._width:
            return
        self._width = width
        lines, cur = [], Text()
        for key, desc in self.items:
            chunk = Text()
            chunk.append(f" {key} ", style="bold reverse")
            chunk.append(f" {desc}  ")
            if cur.cell_len and cur.cell_len + chunk.cell_len > width:
                lines.append(cur)
                cur = Text()
            cur.append_text(chunk)
        lines.append(cur)
        self.update(Text("\n").join(lines))


def B(keys: str, action: str) -> Binding:
    return Binding(keys, action, "", show=False)


# ───────────────────────────── Ventanas modales ───────────────────────────


class Confirm(ModalScreen):
    BINDINGS = [B("escape", "no")]

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label(self.text, markup=False)
            with Horizontal(classes="buttons"):
                yield Button(tr("yes"), variant="error", id="yes")
                yield Button(tr("no"), id="no")

    def on_mount(self):
        self.query_one("#no").focus()

    def on_button_pressed(self, event):
        self.dismiss(event.button.id == "yes")

    def action_no(self):
        self.dismiss(False)


class Ask(ModalScreen):
    BINDINGS = [B("escape", "cancel")]

    def __init__(self, text: str, password: bool = False):
        super().__init__()
        self.text = text
        self.password = password

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label(self.text, markup=False)
            yield Input(password=self.password, id="answer")
            with Horizontal(classes="buttons"):
                yield Button(tr("accept"), variant="primary", id="ok")
                yield Button(tr("cancel"), id="cancel")

    def on_input_submitted(self, event):
        self.dismiss(event.value)

    def on_button_pressed(self, event):
        self.dismiss(self.query_one("#answer", Input).value if event.button.id == "ok" else None)

    def action_cancel(self):
        self.dismiss(None)


class SettingsScreen(ModalScreen):
    """Idioma y tipo de caracteres. Devuelve (idioma, caracteres) o None."""

    BINDINGS = [B("escape", "cancel")]

    def __init__(self):
        super().__init__()
        self.lang = core.LANG
        self.chars = core.CHARS

    def _chars_label(self) -> str:
        label = tr("chars_" + self.chars, self.lang)
        if self.chars == "auto":
            label += " (" + ("ASCII" if detect_ascii("auto") else "Unicode") + ")"
        return label

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label("", id="s_title", classes="ptitle", markup=False)
            yield Button("", id="s_lang")
            yield Button("", id="s_chars")
            yield Label("", id="s_hint", markup=False)
            with Horizontal(classes="buttons"):
                yield Button("", variant="primary", id="s_apply")
                yield Button("", id="s_cancel")

    def on_mount(self):
        self._refresh()

    def _refresh(self):
        L = self.lang
        self.query_one("#s_title", Label).update(Text(tr("settings", L)))
        self.query_one("#s_lang", Button).label = f"{tr('lang_label', L)}: {LANG_NAMES[L]}"
        self.query_one("#s_chars", Button).label = f"{tr('chars_label', L)}: {self._chars_label()}"
        self.query_one("#s_hint", Label).update(Text(tr("settings_hint", L)))
        self.query_one("#s_apply", Button).label = tr("apply", L)
        self.query_one("#s_cancel", Button).label = tr("cancel", L)

    def on_button_pressed(self, event):
        bid = event.button.id
        if bid == "s_lang":
            self.lang = LANGS[(LANGS.index(self.lang) + 1) % len(LANGS)]
            self._refresh()
        elif bid == "s_chars":
            self.chars = CHARS_MODES[(CHARS_MODES.index(self.chars) + 1) % len(CHARS_MODES)]
            self._refresh()
        elif bid == "s_apply":
            self.dismiss((self.lang, self.chars))
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class ServerForm(ModalScreen):
    BINDINGS = [B("escape", "cancel")]

    def __init__(self, srv: dict | None = None):
        super().__init__()
        self.srv = srv or {}

    def compose(self):
        s = self.srv
        with VerticalScroll(classes="dialog"):
            yield Label(tr("form_title"), classes="ptitle", markup=False)
            yield Label(tr("f_name"), markup=False)
            yield Input(s.get("name", ""), id="name")
            yield Label(tr("f_host"), markup=False)
            yield Input(s.get("host", ""), id="host")
            yield Label(tr("f_port"), markup=False)
            yield Input(str(s.get("port", 22)), id="port", type="integer")
            yield Label(tr("f_user"), markup=False)
            yield Input(s.get("user", ""), id="user")
            yield Label(tr("f_pass"), markup=False)
            yield Input(s.get("password", ""), id="password", password=True)
            yield Label(tr("f_key"), markup=False)
            yield Input(s.get("key", ""), id="key")
            with Horizontal(classes="buttons"):
                yield Button(tr("save"), variant="primary", id="save")
                yield Button(tr("cancel"), id="cancel")

    def _save(self):
        v = {k: self.query_one(f"#{k}", Input).value.strip() for k in ("name", "host", "port", "user", "key")}
        v["password"] = self.query_one("#password", Input).value
        if not (v["name"] and v["host"] and v["user"]):
            self.notify(tr("form_required"), severity="error")
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

    BINDINGS = [B("escape,enter,space", "skip")]

    def __init__(self, manual: bool = False):
        super().__init__()
        self.manual = manual
        self.frame = 0
        self.entered = False
        self.updating = False

    def compose(self):
        with Vertical(id="splash"):
            yield Static(BANNER, id="banner", markup=False)
            yield Label(f"v{__version__}", id="ver", markup=False)
            yield Label("", id="bar", markup=False)
            yield Label(tr("splash_check"), id="msg", markup=False)
            yield Label(tr("skip_hint"), id="skiphint", markup=False)

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
        self._set_bar("[" + (gl("full") if ok else "x") * (BAR_W - 2) + "]", "ok" if ok else "err")

    # ---- búsqueda ----
    def _check(self):
        try:
            remote, src = core.fetch_update(PROJECT, __version__)
            self.app.call_from_thread(self._result, remote, src, None)
        except (NetworkError, UpdateError) as e:
            self.app.call_from_thread(self._result, None, None, e)
        except Exception as e:
            self.app.call_from_thread(self._result, None, None, NetworkError(repr(e)))

    def _result(self, remote, src, err):
        app = self.app
        if err is not None:
            kind = tr("net_error") if isinstance(err, NetworkError) else tr("error")
            app.update_status = ("net", str(err))
            app.say(tr("log_net", e=err), "red")
            if self.entered:
                return
            self._stop_bar(False)
            self._msg(f"{kind}: {err}", "err")
            self.set_timer(2.5, self._enter)
            return
        if src is not None:
            app.update_status = ("new", remote)
            app.say(tr("log_new", v=remote, cur=__version__), "yellow")
            if self.entered:
                return
            self._stop_bar(True)
            self._msg(tr("new_avail", v=remote, cur=__version__), "ok")
            app.push_screen(
                Confirm(tr("confirm_update", v=remote, cur=__version__)),
                lambda yes: self._apply(remote, src) if yes else self._enter(),
            )
            return
        app.update_status = None
        app.say(tr("log_latest", v=__version__))
        if self.entered:
            return
        self._stop_bar(True)
        self._msg(tr("latest", v=__version__), "ok")
        self.set_timer(0.9, self._enter)

    def _apply(self, remote: str, src: str):
        self.updating = True
        self._msg(tr("installing"))

        def job():
            try:
                core.apply_update(PROJECT, src)
                self.app.call_from_thread(self._applied, remote, None)
            except Exception as e:
                self.app.call_from_thread(self._applied, remote, e)

        self.run_worker(job, thread=True, group="update")

    def _applied(self, remote: str, err):
        self.updating = False
        if err is not None:
            self.app.say(tr("update_fail", e=err), "red")
            self._msg(tr("update_fail", e=err), "err")
            self.set_timer(2.5, self._enter)
            return
        self.app.say(f"OK v{remote}", "green")
        self._msg(tr("updated_restart", v=remote), "ok")
        self.set_timer(1.5, lambda: self.app.exit(message=tr("exit_msg", v=remote)))

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
        self.items: list = []  # (nombre, es_carpeta, tamaño, oculto, fecha)
        self.entries: dict = {}  # nombre -> es_carpeta
        self.show_hidden = False

    def compose(self):
        yield Label(tr("this_pc") if self.kind == "local" else tr("server"), classes="ptitle", markup=False)
        yield Label("", id=f"path-{self.kind}", classes="ppath", markup=False)
        yield DataTable(id=self.kind, cursor_type="row", zebra_stripes=True)

    # ---- listado ----
    def _list(self, path: str) -> list:
        return list_local(path) if self.kind == "local" else list_remote(self.conn.sftp, path)

    def parent_path(self):
        return parent_local(self.path) if self.kind == "local" else parent_remote(self.path)

    def go(self, path, select=None):
        def job():
            try:
                p = path
                if p is None:
                    p = self.conn.sftp.normalize(".")
                items = self._list(p)
            except Exception as e:
                self.app.call_from_thread(self.app.report, str(e), "error", tr("could_not_open"))
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
        self.entries = {it[0]: it[1] for it in items}
        self.query_one(f"#path-{self.kind}", Label).update(Text(path or tr("drives")))
        self.render_table(select)

    def render_table(self, select=None):
        t = self.query_one(DataTable)
        if not t.columns:
            t.add_column(tr("col_name"))
            t.add_column(tr("col_size"))
        t.clear()
        if self.parent_path() is not None:
            t.add_row(Text(gl("dir") + ".."), Text(""), key="..")
        for n, d, s, hidden, _mtime in self.items:
            if hidden and not self.show_hidden:
                continue
            if d:
                t.add_row(Text(gl("dir") + n, style="bold cyan"), Text(""), key=n)
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
    def _where(self) -> str:
        return tr("pc") if self.kind == "local" else tr("server")

    def _op(self, fn, okmsg: str):
        def job():
            try:
                fn()
                self.app.call_from_thread(self.app.say, okmsg)
            except Exception as e:
                self.app.call_from_thread(self.app.report, str(e), "error", tr("error"))
            self.app.call_from_thread(self.reload)

        self.run_worker(job, thread=True, group="ops")

    def mkdir(self, name: str):
        def fn():
            mkdir_checked(name)
            if self.kind == "local":
                os.makedirs(os.path.join(self.path, name), exist_ok=True)
            else:
                self.conn.sftp.mkdir(posixpath.join(self.path, name))

        self._op(fn, tr("log_mkdir", where=self._where(), name=name))

    def delete(self, name: str):
        def fn():
            if self.kind == "local":
                delete_local(os.path.join(self.path, name))
            else:
                delete_remote(self.conn.sftp, posixpath.join(self.path, name))

        self._op(fn, tr("log_deleted", where=self._where(), name=name))


# ───────────────────────────── Pantalla: consola ──────────────────────────


class ConsoleScreen(Screen):
    BINDINGS = [B("escape", "back"), B("f4", "cancel"), B("ctrl+l", "clear")]

    def __init__(self, browser: "BrowserScreen"):
        super().__init__()
        self.browser = browser
        self.cmd = None
        self.running = False

    def compose(self):
        yield TitleBar(tr("k_console"))
        yield Label(tr("console_title"), id="hint", markup=False)
        yield RichLog(id="log", wrap=True, highlight=False, markup=False, max_lines=2000)
        yield Input(placeholder=tr("console_placeholder"), id="cmd")
        yield KeyBar([("F4", tr("k_cancel_cmd")), ("Ctrl+L", tr("k_clear")), ("Esc", tr("back"))])

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
        if self.running and self.cmd is not None:
            self.cmd.cancel()

    def on_input_submitted(self, event):
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if self.running:
            self.notify(tr("cmd_running"), severity="warning")
            return
        self.running = True
        self.cmd = RemoteCommand(self.browser.conn, text, self.browser.panel("remote").path)
        self.app.say(f"$ {text}", "bold green")
        self.run_worker(self._exec, thread=True, group="cmd")

    def _exec(self):
        def emit(lines, style):
            self.app.call_from_thread(self.app.say_many, lines, style)

        self.cmd.run(emit)
        self.app.call_from_thread(self._finished)

    def _finished(self):
        self.running = False


# ───────────────────────────── Pantalla: fila ─────────────────────────────

STATUS_KEY = {"pendiente": "s_pending", "en curso": "s_running", "listo": "s_done", "error": "s_error"}
STATUS_COLOR = {"pendiente": "yellow", "en curso": "bold cyan", "listo": "green", "error": "bold red"}


class QueueScreen(Screen):
    BINDINGS = [
        B("s", "toggle"),
        B("x,delete", "remove"),
        B("r", "retry"),
        B("l", "clear"),
        B("escape,q", "back"),
    ]

    def __init__(self, browser: "BrowserScreen"):
        super().__init__()
        self.browser = browser

    def compose(self):
        yield TitleBar(tr("queue_name"))
        yield Label(tr("queue_title"), id="hint", markup=False)
        yield DataTable(id="qtable", cursor_type="row", zebra_stripes=True)
        yield Label("", id="status", markup=False)
        yield KeyBar(
            [
                ("s", tr("k_startstop")),
                ("x", tr("k_remove")),
                ("r", tr("k_retry")),
                ("l", tr("k_clear_done")),
                ("Esc", tr("back")),
            ]
        )

    def on_mount(self):
        t = self.query_one(DataTable)
        for c in ("col_status", "col_type", "col_name", "col_from", "col_to", "col_progress"):
            t.add_column(tr(c))
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
            up = it["up"]
            if it["status"] == "error":
                prog = it["error"][:60]
            elif it["status"] in ("en curso", "listo") and it["total"]:
                prog = f'{min(it["done"] / it["total"], 1):.0%}'
            else:
                prog = ""
            t.add_row(
                Text(tr(STATUS_KEY[it["status"]]), style=STATUS_COLOR[it["status"]]),
                Text((gl("up") + " " + tr("t_up")) if up else (gl("down") + " " + tr("t_down"))),
                Text((gl("dir") if it["is_dir"] else "") + it["name"]),
                Text((tr("pc") if up else tr("server")) + ": " + it["src"]),
                Text((tr("server") if up else tr("pc")) + ": " + it["dst"]),
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
            summary = tr(
                "queue_summary", p=n("pendiente"), r=n("en curso"), d=n("listo"), e=n("error")
            )
        else:
            summary = tr("queue_empty")
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
            self.notify(tr("rm_running"), severity="warning")
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
        self.notify(tr("retry_n", n=n) if n else tr("retry_none"))

    def action_clear(self):
        self.browser.queue[:] = [i for i in self.browser.queue if i["status"] != "listo"]
        self.browser.queue_changed()

    def action_back(self):
        self.app.pop_screen()


# ───────────────────────── Pantalla de exploración ────────────────────────


class _TuiHooks:
    """Pasa lo que informa el motor de transferencias (hilo aparte) al hilo de la interfaz."""

    def __init__(self, scr):
        self.scr = scr

    def item_update(self, it, status):
        self.scr._ui(self.scr._item_update, it, status)

    def tick(self, it, label):
        self.scr._ui(self.scr._tick, it, label)

    def done(self, ok, err, msg):
        self.scr._ui(self.scr._queue_done, ok, err, msg)


class BrowserScreen(Screen):
    BINDINGS = [
        B("tab", "swap"),
        B("t,f5", "transfer"),
        B("a", "enqueue"),
        B("f", "show_queue"),
        B("c", "console"),
        B("n", "mkdir"),
        B("x,delete", "delete"),
        B("r", "refresh"),
        B("h", "hidden"),
        B("backspace", "up"),
        B("g", "gui"),
        B("escape,q", "disconnect"),
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
        yield TitleBar(self.srv_title)
        with Horizontal(id="panels"):
            yield Panel("local", self.conn)
            yield Panel("remote", self.conn)
        yield Label("", id="status", markup=False)
        yield KeyBar(
            [
                ("Tab", tr("k_panel")),
                ("Enter", tr("k_open")),
                ("t", tr("k_transfer")),
                ("a", tr("k_addq")),
                ("f", tr("k_queue")),
                ("c", tr("k_console")),
                ("n", tr("k_mkdir")),
                ("x", tr("k_delete")),
                ("r", tr("k_refresh")),
                ("h", tr("k_hidden")),
                ("g", tr("k_gui")),
                ("Esc", tr("k_disconnect")),
            ]
        )

    def on_mount(self):
        self.app.current_server = self.srv_title
        self.set_status(self.idle_status())
        if self.queue:
            msg = tr("queue_restored", n=len(self.queue))
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
        return tr("queue_n", n=n) if n else tr("ready")

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
            self.notify(tr("open_drive"), severity="warning")
            return
        self.app.push_screen(
            Ask(tr("mkdir_prompt")),
            lambda v: p.mkdir(v.strip()) if v and v.strip() else None,
        )

    def action_delete(self):
        p = self.active()
        name = self.selected(p)
        if name is None:
            return
        where = tr("where_local") if p.kind == "local" else tr("where_remote")
        extra = tr("extra_contents") if p.entries.get(name) else ""
        self.app.push_screen(
            Confirm(tr("confirm_delete", name=name, extra=extra, where=where)),
            lambda ok: p.delete(name) if ok else None,
        )

    def action_console(self):
        self.app.push_screen(ConsoleScreen(self))

    def action_show_queue(self):
        self.app.push_screen(QueueScreen(self))

    def action_disconnect(self):
        if self.busy:
            self.notify(tr("busy_leave"), severity="warning")
            return
        pend = sum(1 for i in self.queue if i["status"] in ("pendiente", "error"))
        self.conn.close()
        self.app.say(tr("log_disconnected", name=self.srv_title))
        self.app.current_server = None
        if pend:
            self.app.notify(tr("queue_saved", n=pend))
        self.app.pop_screen()

    # ---- fila de transferencias ----
    def describe(self, it: dict) -> str:
        up = it["up"]
        a, b = (tr("pc"), tr("server")) if up else (tr("server"), tr("pc"))
        return f'{gl("up") if up else gl("down")} {it["name"]}  ({a}: {it["src"]} {gl("arrow")} {b}: {it["dst"]})'

    def queue_save(self):
        save_queue(self.qkey, self.queue)
        link_notify("gui", {"cmd": "queue_changed", "key": self.qkey})

    def queue_reload(self):
        """La app gráfica cambió la fila de este servidor: se vuelve a leer del disco."""
        if self.busy:
            return
        fresh = load_queue(self.qkey)
        keep = [i for i in self.queue if i["status"] == "listo"]
        used = {i["id"] for i in keep}
        nid = max(used, default=0) + 1
        for it in fresh:
            if it["id"] in used:
                it["id"], nid = nid, nid + 1
            used.add(it["id"])
        self.queue[:] = keep + fresh
        self.next_id = max(used, default=0) + 1
        self.queue_refresh()
        self.app.say(tr("link_queue"))

    def action_gui(self):
        self.app.open_gui(self.srv_title)

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
            self.notify(tr("select_first"), severity="warning")
            return None
        if src.path == "" or dst.path == "":
            self.notify(tr("open_folder"), severity="warning")
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
        self.app.say(tr("log_added", desc=self.describe(item)))
        if not quiet:
            self.notify(tr("added_notify", name=item["name"]))

    def action_enqueue(self):
        v = self._validate()
        if v is None:
            return
        item, exists = v
        sig = lambda i: (i["up"], i["name"], i["src"], i["dst"])
        if any(sig(i) == sig(item) and i["status"] in ("pendiente", "error") for i in self.queue):
            self.notify(tr("already_queued"), severity="warning")
            return
        if exists:
            self.app.push_screen(
                Confirm(tr("overwrite_queue", name=item["name"])),
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
                Confirm(tr("overwrite", name=item["name"])),
                lambda ok: self._now(item) if ok else None,
            )
        else:
            self._now(item)

    def _now(self, item: dict):
        self._add(item, quiet=True)
        if self.busy:
            self.notify(tr("queued_busy"), severity="warning")
            return
        self.run_items([item["id"]])

    def toggle_queue(self):
        if self.busy:
            self.stop.set()
            self.notify(tr("stopping"))
            return
        ids = [i["id"] for i in self.queue if i["status"] == "pendiente"]
        if not ids:
            self.notify(tr("nothing_pending"), severity="warning")
            return
        self.run_items(ids)

    def run_items(self, ids: list):
        if self.busy:
            return
        self.busy = True
        self.stop.clear()
        self.set_status(tr("starting"))
        self.run_worker(lambda: self._run(ids), thread=True, group="transfer")

    # ---- ejecución (hilo aparte) ----
    def _run(self, ids: list):
        run_queue(self.conn, self.queue, ids, self.stop, _TuiHooks(self))

    # ---- actualizaciones de interfaz (hilo principal) ----
    def _tick(self, it: dict, label: str):
        frac = min(it["done"] / (it["total"] or 1), 1.0)
        n = int(frac * 20)
        bar = gl("full") * n + gl("empty") * (20 - n)
        arrow = gl("up") if it["up"] else gl("down")
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
            self.app.say(tr("log_item_start", d=d))
        elif status == "listo":
            self.app.say(tr("log_item_ok", d=d), "green")
        elif status == "error":
            self.app.say(tr("log_item_err", d=d, e=it["error"]), "red")
            self.notify(escape(it["error"]), title=tr("err_title", name=it["name"]), severity="error")
        elif status == "pendiente":
            self.app.say(tr("log_item_stop", d=d), "yellow")
        self.queue_changed()

    def _queue_done(self, ok: int, err: int, msg):
        self.busy = False
        failed = msg is not None
        if msg is None:
            msg = tr("queue_stopped" if self.stop.is_set() else "queue_finished", ok=ok, err=err)
        self.app.report(msg, "error" if err or failed else "information")
        self.set_status(("ERROR  " if err or failed else "OK  ") + msg)
        self.panel("local").reload()
        self.panel("remote").reload()
        self.queue_refresh()


# ─────────────────────── Pantalla de servidores guardados ─────────────────


class ServersScreen(Screen):
    BINDINGS = [
        B("n", "new"),
        B("e", "edit"),
        B("x,delete", "remove"),
        B("u", "update"),
        B("s", "settings"),
        B("g", "gui"),
        B("q", "app.quit"),
    ]

    def __init__(self):
        super().__init__()
        self.servers: list = []
        self.connecting = False

    def compose(self):
        yield TitleBar()
        yield Label("", id="hint", markup=False)
        yield Label("", id="net", markup=False)
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield KeyBar(
            [
                ("Enter", tr("k_connect")),
                ("n", tr("k_new")),
                ("e", tr("k_edit")),
                ("x", tr("k_delete")),
                ("u", tr("k_update")),
                ("s", tr("k_settings")),
                ("g", tr("k_gui")),
                ("q", tr("k_quit")),
            ]
        )

    def on_mount(self):
        t = self.query_one(DataTable)
        t.add_column(tr("col_name"))
        t.add_column(tr("col_server"))
        t.add_column(tr("col_user"))
        self.reload()
        self.refresh_net()
        t.focus()
        name = getattr(self.app, "auto_connect", None)
        if name:  # sshmanager --connect NOMBRE
            self.app.auto_connect = None
            self.call_after_refresh(lambda: self.connect_by_name(name))

    def connect_by_name(self, name: str):
        srv = next((s for s in self.servers if s.get("name", "").lower() == name.lower()), None)
        if srv is None:
            self.notify(tr("server_unknown", name=name), severity="error")
        else:
            self.connect(srv)

    def action_gui(self):
        self.app.open_gui(None)

    def servers_saved(self):
        save_servers(self.servers)
        link_notify("gui", {"cmd": "servers_changed"})
        self.reload()

    def on_screen_resume(self):
        self.refresh_net()

    def refresh_net(self):
        try:
            lab = self.query_one("#net", Label)
        except NoMatches:
            return
        st = self.app.update_status
        text, kind = "", ""
        if st and st[0] == "net":
            text, kind = tr("st_net", e=st[1]) + tr("st_net_retry"), "warn"
        elif st and st[0] == "new":
            text, kind = tr("st_new", v=st[1]) + tr("st_new_do"), "newv"
        lab.update(Text(text))
        lab.set_class(kind == "warn", "warn")
        lab.set_class(kind == "newv", "newv")

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
        hint.update(Text(tr("servers_title") if self.servers else tr("servers_empty")))

    def current(self):
        t = self.query_one(DataTable)
        if t.row_count == 0:
            return None
        return int(t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value)

    def action_update(self):
        self.app.push_screen(SplashScreen(manual=True))

    def action_settings(self):
        def done(result):
            if result and (result[0] != core.LANG or result[1] != core.CHARS):
                core.apply_settings(*result)
                update_scrollbars()
                self.app.set_class(core.ASCII, "ascii")
                self.app.switch_screen(ServersScreen())  # se vuelve a dibujar con el idioma nuevo

        self.app.push_screen(SettingsScreen(), done)

    def action_new(self):
        def done(v):
            if v:
                self.servers.append(v)
                self.servers_saved()

        self.app.push_screen(ServerForm(), done)

    def action_edit(self):
        i = self.current()
        if i is None:
            return

        def done(v):
            if v:
                self.servers[i] = v
                self.servers_saved()

        self.app.push_screen(ServerForm(self.servers[i]), done)

    def action_remove(self):
        i = self.current()
        if i is None:
            return

        def done(ok):
            if ok:
                del self.servers[i]
                self.servers_saved()

        self.app.push_screen(Confirm(tr("confirm_rm_server", name=self.servers[i]["name"])), done)

    # ---- conexión ----
    def on_data_table_row_selected(self, event):
        self.connect(self.servers[int(event.row_key.value)])

    def connect(self, srv: dict, password: str | None = None):
        if self.connecting:
            return
        self.connecting = True
        self.notify(tr("connecting", name=srv["name"]))

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
        self.app.report(f"{srv['name']}: {msg}", "error", tr("connect_fail"))

    def _connected(self, conn: Connection, srv: dict):
        self.connecting = False
        addr = f"{srv['user']}@{srv['host']}:{srv.get('port', 22)}"
        self.app.say(tr("log_connected", name=srv["name"], addr=addr), "green")
        self.app.push_screen(BrowserScreen(conn, srv["name"], srv))

    def _need_password(self, srv: dict):
        self.connecting = False

        def done(pw):
            if pw:
                self.connect(srv, pw)

        self.app.push_screen(Ask(tr("ask_pass", user=srv["user"], host=srv["host"]), password=True), done)


# ─────────────────────────────── Aplicación ───────────────────────────────


class SSHManager(App):
    TITLE = f"SSH Manager v{__version__}"
    ENABLE_COMMAND_PALETTE = False
    # Solo bordes 'solid' y 'double': existen hasta en las fuentes más básicas de Windows.
    CSS = """
    Screen { background: $surface; }
    TitleBar { height: 1; width: 100%; background: $primary; color: $text; padding: 0 1; }
    KeyBar { height: auto; width: 100%; background: $boost; padding: 0 1; }
    #panels { height: 1fr; }
    Panel { width: 1fr; height: 1fr; border: solid $primary-darken-2; }
    Panel:focus-within { border: solid $accent; }
    Panel DataTable { height: 1fr; }
    .ptitle { text-style: bold; padding: 0 1; width: 100%; }
    .ppath { color: $text-muted; padding: 0 1; width: 100%; }
    #status { height: 1; width: 100%; padding: 0 1; background: $boost; color: $text; }
    #hint { height: 1; width: 100%; padding: 0 1; text-style: bold; }
    #net { height: 1; width: 100%; padding: 0 1; }
    #net.warn { color: $error; }
    #net.newv { color: $warning; }
    #qtable { height: 1fr; }
    #log { height: 1fr; border: solid $primary-darken-2; }
    SSHManager.ascii Panel { border: ascii $primary-darken-2; }
    SSHManager.ascii Panel:focus-within { border: ascii $accent; }
    SSHManager.ascii #log { border: ascii $primary-darken-2; }
    SSHManager.ascii .dialog { border: ascii $primary; }
    SSHManager.ascii Input { border: ascii $primary-darken-2; }
    SSHManager.ascii Input:focus { border: ascii $accent; }
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
        width: 62; max-width: 95%; height: auto; max-height: 90%;
        border: double $primary; background: $surface; padding: 1 2;
    }
    .dialog Label { width: 100%; height: auto; }
    .dialog Input { margin-bottom: 1; }
    .dialog Button { width: 100%; margin-bottom: 1; }
    #s_hint { color: $text-muted; margin-bottom: 1; }
    .buttons { height: auto; align-horizontal: right; }
    .buttons Button { width: auto; min-width: 12; margin-left: 2; margin-bottom: 0; }
    /* Campos y botones con bordes simples: los de Textual usan bloques que fallan en Windows */
    Input { border: solid $primary-darken-2; }
    Input:focus { border: solid $accent; }
    Button, Button.-primary, Button.-error, Button.-success, Button.-warning, Button.-default {
        border: none; height: 1; padding: 0 2; content-align: center middle;
    }
    """

    def __init__(self, auto_connect: str | None = None):
        super().__init__()
        self.console_buffer: list = []  # (hora, texto, estilo)
        self.update_status = None  # None | ("net", error) | ("new", versión)
        self.auto_connect = auto_connect
        self.current_server = None  # servidor conectado ahora
        self.gui_online = False
        self.link = LinkServer("tui", self._link_handler, __version__)

    def on_mount(self):
        self.set_class(core.ASCII, "ascii")
        self.say(tr("log_started", v=__version__))
        self.link.start()
        self.set_interval(3.0, self._poll_link)
        self.push_screen(SplashScreen())

    def on_unmount(self):
        self.link.stop()

    # ---- enlace con la app gráfica ----
    def _poll_link(self):
        self.run_worker(lambda: self.call_from_thread(self._set_link, link_alive("gui")), thread=True, group="link", exclusive=True)

    def _set_link(self, online: bool):
        self.gui_online = online
        for scr in list(self.screen_stack):
            for bar in scr.query(TitleBar):
                bar.set_link(online)

    def open_gui(self, server: str | None):
        def job():
            ok, msg = core.launch_gui(server)
            self.call_from_thread(self.report, msg, "information" if ok else "warning")

        self.run_worker(job, thread=True, group="gui")

    def _link_handler(self, msg: dict):
        """Mensajes de la app gráfica (llegan en otro hilo)."""
        cmd = msg.get("cmd")

        def run(fn):
            try:
                self.call_from_thread(fn)
            except Exception:  # noqa: BLE001  (la app se está cerrando)
                pass

        if cmd == "info":
            return {"ok": True, "kind": "tui", "version": __version__, "server": self.current_server}
        if cmd == "servers_changed":
            run(self._link_servers)
            return {"ok": True}
        if cmd == "queue_changed":
            run(lambda: self._link_queue(msg.get("key")))
            return {"ok": True}
        if cmd == "open_server":
            name = str(msg.get("name", ""))
            if not find_server(name):
                return {"ok": False, "error": "unknown server"}
            run(lambda: self._link_open(name))
            return {"ok": True}
        return {"ok": False, "error": "unknown command"}

    def _link_servers(self):
        for scr in list(self.screen_stack):
            if isinstance(scr, ServersScreen):
                scr.reload()
                self.say(tr("link_servers"))

    def _link_queue(self, key):
        for scr in list(self.screen_stack):
            if isinstance(scr, BrowserScreen) and scr.qkey == key:
                scr.queue_reload()

    def _link_open(self, name: str):
        self.say(tr("link_open", name=name))
        if isinstance(self.screen, ServersScreen):
            self.screen.connect_by_name(name)
        else:
            self.notify(tr("link_open", name=name), severity="warning")

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
    args = sys.argv[1:]
    connect = args[1] if len(args) > 1 and args[0] == "--connect" else None
    SSHManager(auto_connect=connect).run()


if __name__ == "__main__":
    main()
