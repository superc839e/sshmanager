#!/usr/bin/env bash
# Instala (o reinstala) SSH Manager y crea el comando global "sshmanager".
# Funciona desde la carpeta con ssh_manager.py o directo desde GitHub:
#   curl -fsSL https://raw.githubusercontent.com/superc839e/sshmanager/main/instalar_linux.sh | bash
set -e
RAW="https://raw.githubusercontent.com/superc839e/sshmanager/main/ssh_manager.py"
APP="$HOME/.local/share/sshmanager"
BIN="$HOME/.local/bin"
mkdir -p "$APP" "$BIN"

python3 -m venv "$APP/venv" || {
  echo "Falta el módulo venv. En Debian/Ubuntu: sudo apt install python3-venv"
  exit 1
}
"$APP/venv/bin/pip" install --quiet --upgrade textual paramiko

SRC="${BASH_SOURCE[0]:-}"
if [ -n "$SRC" ] && [ -f "$(dirname "$SRC")/ssh_manager.py" ]; then
  cp "$(dirname "$SRC")/ssh_manager.py" "$APP/ssh_manager.py"
else
  echo "Descargando ssh_manager.py desde GitHub…"
  "$APP/venv/bin/python" -c "import sys,urllib.request as u; u.urlretrieve(sys.argv[1], sys.argv[2])" \
    "$RAW" "$APP/ssh_manager.py" || { echo "No pude descargar desde GitHub. Revisa tu conexión."; exit 1; }
fi

cat > "$BIN/sshmanager" <<LAUNCHER
#!/usr/bin/env bash
exec "$APP/venv/bin/python" "$APP/ssh_manager.py" "\$@"
LAUNCHER
chmod +x "$BIN/sshmanager"

echo "Listo. Escribe: sshmanager   (manual: sshmanager -h)"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "Aviso: añade $BIN a tu PATH (export PATH=\"\$HOME/.local/bin:\$PATH\")" ;;
esac
