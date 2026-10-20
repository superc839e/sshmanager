#!/usr/bin/env python3
"""
SSH Manager — cliente SSH/SFTP con interfaz de terminal.
Funciona igual en Windows y Linux. Sin comandos: todo con teclado o mouse.

Dependencias:  pip install textual paramiko
"""
import json
import os
import posixpath
import shutil
import stat
import string
import time
from pathlib import Path

import paramiko
from rich.markup import escape
from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label

# ───────────────────────── Configuración guardada ─────────────────────────


def config_file() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "sshmanager"
    d.mkdir(parents=True, exist_ok=True)
    return d / "servers.json"


CONFIG = config_file()


def load_servers() -> list:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_servers(servers: list) -> None:
    CONFIG.write_text(json.dumps(servers, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(CONFIG, 0o600)  # solo tu usuario puede leerlo (Linux)
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
                self.app.call_from_thread(
                    self.app.notify, escape(str(e)), title="No se pudo abrir", severity="error"
                )
                return
            self.app.call_from_thread(self._fill, p, items, select)

        self.run_worker(job, thread=True, group="load", exclusive=True)

    def reload(self):
        self.go(self.path)

    def _fill(self, path, items, select):
        self.path = path
        self.items = items
        self.entries = {n: d for n, d, _ in items}
        self.query_one(f"#path-{self.kind}", Label).update(path or "Unidades")
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
    def _op(self, fn):
        def job():
            try:
                fn()
            except Exception as e:
                self.app.call_from_thread(self.app.notify, escape(str(e)), title="Error", severity="error")
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

        self._op(fn)

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

        self._op(fn)


# ───────────────────────── Pantalla de exploración ────────────────────────


class BrowserScreen(Screen):
    BINDINGS = [
        Binding("tab", "swap", "Cambiar panel"),
        Binding("t,f5", "transfer", "Transferir"),
        Binding("n", "mkdir", "Nueva carpeta"),
        Binding("x,delete", "delete", "Borrar"),
        Binding("r", "refresh", "Refrescar"),
        Binding("h", "hidden", "Ocultos"),
        Binding("backspace", "up", "Subir", show=False),
        Binding("escape,q", "disconnect", "Desconectar"),
    ]

    def __init__(self, conn: Connection, title: str):
        super().__init__()
        self.conn = conn
        self.srv_title = title
        self.busy = False

    def compose(self):
        yield Header()
        with Horizontal(id="panels"):
            yield Panel("local", self.conn)
            yield Panel("remote", self.conn)
        yield Label("Tab: cambiar de panel · Enter: abrir carpeta · t: transferir al otro panel", id="status", markup=False)
        yield Footer()

    def on_mount(self):
        self.app.sub_title = self.srv_title
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
        self.query_one("#status", Label).update(text)

    # ---- acciones ----
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

    def action_disconnect(self):
        if self.busy:
            self.notify("Espera a que termine la transferencia", severity="warning")
            return
        self.conn.close()
        self.app.sub_title = ""
        self.app.pop_screen()

    # ---- transferencia ----
    def action_transfer(self):
        if self.busy:
            self.notify("Ya hay una transferencia en curso", severity="warning")
            return
        src, dst = self.active(), self.other()
        name = self.selected(src)
        if name is None:
            self.notify("Selecciona un archivo o carpeta primero", severity="warning")
            return
        if src.path == "" or dst.path == "":
            self.notify("Entra a una carpeta (no a la lista de unidades)", severity="warning")
            return
        if name in dst.entries:
            self.app.push_screen(
                Confirm(f"'{name}' ya existe en el destino. ¿Sobrescribir?"),
                lambda ok: self._begin(src, dst, name) if ok else None,
            )
        else:
            self._begin(src, dst, name)

    def _begin(self, src: Panel, dst: Panel, name: str):
        up = src.kind == "local"
        is_dir = bool(src.entries.get(name))
        sp, dp = src.path, dst.path
        self.busy = True
        self.set_status(f"Preparando {name}…")
        self.run_worker(lambda: self._job(up, name, is_dir, sp, dp, dst), thread=True, group="transfer")

    def _ui(self, fn, *args):
        self.app.call_from_thread(fn, *args)

    def _progress(self, up: bool, done: int, total: int, name: str):
        frac = min(done / total, 1.0)
        n = int(frac * 20)
        bar = "█" * n + "░" * (20 - n)
        arrow = "↑" if up else "↓"
        self.set_status(f"{arrow} {name}  {bar} {frac:4.0%}  {human(done)} / {human(total)}")

    def _finish(self, msg: str, dst: Panel, error: bool = False):
        self.busy = False
        self.set_status(msg)
        self.notify(escape(msg), severity="error" if error else "information")
        dst.reload()

    def _job(self, up: bool, name: str, is_dir: bool, sp: str, dp: str, dst: Panel):
        sftp = self.conn.sftp
        try:
            if up:
                dirs, files = plan_upload(os.path.join(sp, name), dp)
                for d in dirs:
                    remote_mkdir(sftp, d)
            else:
                dirs, files = plan_download(sftp, posixpath.join(sp, name), dp, is_dir)
                for d in dirs:
                    os.makedirs(d, exist_ok=True)
            total = sum(f[2] for f in files)
            denom = total or 1
            done = 0
            last = [0.0]
            for s, d, size in files:
                label = os.path.basename(s)
                self._ui(self._progress, up, done, denom, label)

                def cb(sent, _total, base=done, label=label):
                    now = time.monotonic()
                    if now - last[0] > 0.1:
                        last[0] = now
                        self._ui(self._progress, up, base + sent, denom, label)

                if up:
                    sftp.put(s, d, callback=cb)
                else:
                    sftp.get(s, d, callback=cb)
                done += size
            self._ui(self._progress, up, denom, denom, name)
            self._ui(self._finish, f"✔ {name} transferido ({len(files)} archivo(s), {human(total)})", dst)
        except Exception as e:
            self._ui(self._finish, f"✖ Error: {e}", dst, True)


# ─────────────────────── Pantalla de servidores guardados ─────────────────


class ServersScreen(Screen):
    BINDINGS = [
        Binding("n", "new", "Nuevo"),
        Binding("e", "edit", "Editar"),
        Binding("x,delete", "remove", "Borrar"),
        Binding("q", "app.quit", "Salir"),
    ]

    def __init__(self):
        super().__init__()
        self.servers: list = []
        self.connecting = False

    def compose(self):
        yield Header()
        yield Label("Servidores guardados — Enter: conectar · n: nuevo · e: editar · x: borrar", id="hint")
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self):
        t = self.query_one(DataTable)
        t.add_column("Nombre")
        t.add_column("Servidor")
        t.add_column("Usuario")
        self.reload()
        t.focus()

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
            hint.update("Servidores guardados — Enter: conectar · n: nuevo · e: editar · x: borrar")
        else:
            hint.update("No hay servidores guardados. Pulsa n para añadir el primero.")

    def current(self):
        t = self.query_one(DataTable)
        if t.row_count == 0:
            return None
        return int(t.coordinate_to_cell_key(t.cursor_coordinate).row_key.value)

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
                    self.app.call_from_thread(self._failed, str(e))
                return
            except Exception as e:
                self.app.call_from_thread(self._failed, str(e) or type(e).__name__)
                return
            self.app.call_from_thread(self._connected, conn, srv["name"])

        self.run_worker(job, thread=True, group="connect")

    def _failed(self, msg: str):
        self.connecting = False
        self.notify(escape(msg), title="No se pudo conectar", severity="error")

    def _connected(self, conn: Connection, name: str):
        self.connecting = False
        self.app.push_screen(BrowserScreen(conn, name))

    def _need_password(self, srv: dict):
        self.connecting = False

        def done(pw):
            if pw:
                self.connect(srv, pw)

        self.app.push_screen(Ask(f"Contraseña para {srv['user']}@{srv['host']}:", password=True), done)


# ─────────────────────────────── Aplicación ───────────────────────────────


class SSHManager(App):
    TITLE = "SSH Manager"
    CSS = """
    Panel { width: 1fr; height: 1fr; border: round $primary-darken-1; }
    Panel:focus-within { border: round $accent; }
    Panel DataTable { height: 1fr; }
    .ptitle { text-style: bold; padding: 0 1; }
    .ppath { color: $text-muted; padding: 0 1; }
    #status, #hint { height: 1; padding: 0 1; color: $text-muted; }
    ModalScreen { align: center middle; }
    .dialog {
        width: 60; max-width: 95%; height: auto; max-height: 90%;
        border: thick $primary; background: $surface; padding: 1 2;
    }
    .dialog Input { margin-bottom: 1; }
    .buttons { height: auto; align-horizontal: right; }
    .buttons Button { margin-left: 2; }
    """

    def on_mount(self):
        self.push_screen(ServersScreen())


def main():
    SSHManager().run()


if __name__ == "__main__":
    main()
