#!/usr/bin/env bash
# Install Dig for the current user only.
#
# Nothing is written outside your home folder. No root, no system packages, no
# useradd, nothing in /usr. That matters on Bazzite and any other image-based
# system where /usr is read-only.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
BIN_DIR="$HOME/.local/bin"

VENV="$HERE/.venv"
PYTHON="${PYTHON:-python3}"

say() { printf '%s\n' "$*"; }

if [ "$(id -u)" -eq 0 ]; then
  say "Run this as yourself, not as root. Dig installs into your home folder only."
  exit 1
fi

say "Installing Dig from $HERE"

# ---------- dependencies ----------

if [ ! -d "$VENV" ]; then
  say "  creating the virtual environment"
  "$PYTHON" -m venv "$VENV"
fi

say "  installing pinned dependencies"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$HERE/requirements.txt"

# ---------- launcher ----------

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/dig" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/python" "$HERE/app.py" "\$@"
EOF
chmod +x "$BIN_DIR/dig"
say "  launcher at $BIN_DIR/dig"

# ---------- icons ----------

for size in 16 24 32 48 64 128 256 512; do
  target="$ICONS_DIR/${size}x${size}/apps"
  mkdir -p "$target"
  if [ -f "$HERE/assets/icons/dig-${size}.png" ]; then
    cp "$HERE/assets/icons/dig-${size}.png" "$target/dig.png"
  fi
done
mkdir -p "$ICONS_DIR/scalable/apps"
cp "$HERE/assets/icons/dig.svg" "$ICONS_DIR/scalable/apps/dig.svg"
say "  icons in $ICONS_DIR"

# ---------- desktop entry ----------

mkdir -p "$APPS_DIR"
sed "s|__EXEC__|$BIN_DIR/dig|" "$HERE/packaging/dig.desktop" > "$APPS_DIR/dig.desktop"
chmod +x "$APPS_DIR/dig.desktop"
say "  launcher entry at $APPS_DIR/dig.desktop"

# ---------- let the desktop notice ----------

command -v update-desktop-database >/dev/null 2>&1 && \
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
  gtk-update-icon-cache -f -t "$ICONS_DIR" >/dev/null 2>&1 || true

say ""
say "Dig is installed. Find it in your application menu, or run: dig"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say "Add $BIN_DIR to your PATH to run it by name from a terminal." ;;
esac
say "Your data will live in ${XDG_DATA_HOME:-$HOME/.local/share}/dig"
