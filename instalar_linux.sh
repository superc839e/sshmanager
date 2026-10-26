#!/usr/bin/env bash
# Instala (o reinstala) SSH Manager App (interfaz gráfica) y crea el comando "sshmanagerapp"
# y la entrada en el menú de aplicaciones.
#   curl -fsSL https://raw.githubusercontent.com/superc839e/sshmanagerapp/main/instalar_linux.sh | bash
set -e
BASE="${SSHMANAGERAPP_RAW_BASE:-https://raw.githubusercontent.com/superc839e/sshmanagerapp/main}"
CORE_BASE="${SSHMANAGER_RAW_BASE:-https://raw.githubusercontent.com/superc839e/sshmanager/main}"
APP="$HOME/.local/share/sshmanagerapp"
BIN="$HOME/.local/bin"
DESK="$HOME/.local/share/applications"
mkdir -p "$APP" "$BIN" "$DESK"

python3 -m venv "$APP/venv" || {
  echo "Falta el módulo venv. En Debian/Ubuntu: sudo apt install python3-venv"
  exit 1
}

fetch() {  # fetch URL DESTINO: descarga con 3 intentos
  "$APP/venv/bin/python" - "$1" "$2" <<'PY'
import sys, time, urllib.request as u
for i in range(3):
    try:
        u.urlretrieve(sys.argv[1], sys.argv[2]); break
    except Exception:
        if i == 2: raise
        time.sleep(2)
PY
}

SRC="${BASH_SOURCE[0]:-}"
if [ -n "$SRC" ] && [ -f "$(dirname "$SRC")/sshmanagerapp.py" ]; then
  cp "$(dirname "$SRC")/sshmanagerapp.py" "$APP/sshmanagerapp.py"
else
  echo "Descargando sshmanagerapp.py desde GitHub…"
  fetch "$BASE/sshmanagerapp.py" "$APP/sshmanagerapp.py" || { echo "No pude descargar. Revisa tu conexión."; exit 1; }
fi

# La app se conecta con sshmanager: usa su núcleo si está instalado; si no, lo descarga.
if [ ! -f "$HOME/.local/share/sshmanager/sshmanager_core.py" ]; then
  mkdir -p "$APP/core"
  echo "Descargando el núcleo de sshmanager…"
  fetch "$CORE_BASE/sshmanager_core.py" "$APP/core/sshmanager_core.py" || { echo "No pude descargar el núcleo."; exit 1; }
fi

# Dependencias (PySide6, paramiko) con corrección automática de errores comunes
"$APP/venv/bin/python" "$APP/sshmanagerapp.py" --install-deps || {
  echo "No se pudieron instalar las dependencias. Prueba: $BIN/sshmanagerapp --doctor"
}
# Avisa si falta alguna librería del sistema para abrir ventanas (y dice el comando exacto)
"$APP/venv/bin/python" "$APP/sshmanagerapp.py" --check-system || true

cat > "$BIN/sshmanagerapp" <<LAUNCHER
#!/usr/bin/env bash
exec "$APP/venv/bin/python" "$APP/sshmanagerapp.py" "\$@"
LAUNCHER
chmod +x "$BIN/sshmanagerapp"

cat > "$APP/sshmanagerapp.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3b82f6"/><stop offset="1" stop-color="#1e40af"/></linearGradient></defs><rect x="8" y="8" width="240" height="240" rx="52" fill="url(#g)"/><text x="128" y="165" font-family="monospace" font-weight="bold" font-size="120" text-anchor="middle" fill="#fff">&gt;_</text></svg>
SVG
cat > "$DESK/sshmanagerapp.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=SSH Manager App
Comment=Servidores SSH y transferencia de archivos
Exec=$BIN/sshmanagerapp
Icon=$APP/sshmanagerapp.svg
Terminal=false
Categories=Network;Utility;
DESKTOP
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DESK" >/dev/null 2>&1 || true

echo "Listo. Abre «SSH Manager App» desde el menú de aplicaciones o escribe: sshmanagerapp"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "Aviso: añade $BIN a tu PATH (export PATH=\"\$HOME/.local/bin:\$PATH\")" ;;
esac
