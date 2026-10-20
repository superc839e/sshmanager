#!/usr/bin/env bash
# Instala SSH Manager y crea el comando global "sshmanager"
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.local/share/sshmanager"
BIN="$HOME/.local/bin"
mkdir -p "$APP" "$BIN"

python3 -m venv "$APP/venv" || {
  echo "Falta el módulo venv. En Debian/Ubuntu: sudo apt install python3-venv"
  exit 1
}
"$APP/venv/bin/pip" install --quiet --upgrade textual paramiko
cp "$DIR/ssh_manager.py" "$APP/ssh_manager.py"

cat > "$BIN/sshmanager" <<LAUNCHER
#!/usr/bin/env bash
exec "$APP/venv/bin/python" "$APP/ssh_manager.py" "\$@"
LAUNCHER
chmod +x "$BIN/sshmanager"

echo "Listo. Escribe: sshmanager"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "Aviso: añade $BIN a tu PATH (export PATH=\"\$HOME/.local/bin:\$PATH\")" ;;
esac
