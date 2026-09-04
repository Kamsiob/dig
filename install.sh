#!/usr/bin/env bash
# Install Dig for the current user only.
#
# Nothing is written outside your home folder. No root, no system packages, no
# useradd, nothing in /usr. That matters on Bazzite and any other image based
# system where /usr is read only.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS_DIR="$DATA_HOME/applications"
ICONS_DIR="$DATA_HOME/icons/hicolor"
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
  # If PySide6 is already on this system, reuse it rather than downloading a
  # second copy of a very large package.
  if "$PYTHON" -c "import PySide6, PySide6.QtWebEngineWidgets" >/dev/null 2>&1; then
    say "  creating the virtual environment (reusing the system PySide6)"
    "$PYTHON" -m venv --system-site-packages "$VENV"
  else
    say "  creating the virtual environment"
    "$PYTHON" -m venv "$VENV"
  fi
fi

if ! "$VENV/bin/python" -c "import PySide6.QtWebEngineWidgets" >/dev/null 2>&1; then
  say "  installing pinned dependencies"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r "$HERE/requirements.txt"
fi

if ! "$VENV/bin/python" -c "import PySide6.QtWebEngineWidgets" >/dev/null 2>&1; then
  say "Dig needs PySide6 with QtWebEngine and it could not be installed."
  exit 1
fi

# ---------- icons ----------

say "  installing icons"
for size in 16 24 32 48 64 128 256 512; do
  src="$HERE/assets/icons/dig-$size.png"
  [ -f "$src" ] || continue
  dest="$ICONS_DIR/${size}x${size}/apps"
  mkdir -p "$dest"
  cp -f "$src" "$dest/dig.png"
done
if [ -f "$HERE/assets/icons/dig.svg" ]; then
  mkdir -p "$ICONS_DIR/scalable/apps"
  cp -f "$HERE/assets/icons/dig.svg" "$ICONS_DIR/scalable/apps/dig.svg"
fi
command -v gtk-update-icon-cache >/dev/null 2>&1 &&
  gtk-update-icon-cache -q -t -f "$ICONS_DIR" 2>/dev/null || true

# ---------- launcher ----------

say "  installing the launcher"
mkdir -p "$APPS_DIR"
# The file has to be named dig.desktop: the app calls setDesktopFileName("dig")
# so KDE Plasma on Wayland groups the window with this launcher.
sed "s|__EXEC__|$HERE/run|" "$HERE/packaging/dig.desktop" > "$APPS_DIR/dig.desktop"
chmod +x "$APPS_DIR/dig.desktop"
command -v update-desktop-database >/dev/null 2>&1 &&
  update-desktop-database -q "$APPS_DIR" 2>/dev/null || true

# ---------- command line ----------

mkdir -p "$BIN_DIR"
ln -sf "$HERE/run" "$BIN_DIR/dig"

say ""
say "Dig is installed."
say "  Launcher:  $APPS_DIR/dig.desktop"
say "  Command:   $BIN_DIR/dig"
say "  Your data: ${XDG_DATA_HOME:-$HOME/.local/share}/dig"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say ""
     say "  $BIN_DIR is not on your PATH, so the dig command will not be found."
     say "  Add it, or just launch Dig from your applications menu." ;;
esac
