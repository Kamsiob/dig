#!/usr/bin/env bash
# Remove Dig for the current user.
#
# Your ideas, apps and attachments are NOT touched. This removes the launcher,
# the icons and the virtual environment only. The data folder is printed at the
# end so you can delete it yourself if you want it gone.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
BIN_DIR="$HOME/.local/bin"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/dig"

say() { printf '%s\n' "$*"; }

say "Removing Dig"

rm -f "$BIN_DIR/dig"
rm -f "$APPS_DIR/dig.desktop"

for size in 16 24 32 48 64 128 256 512; do
  rm -f "$ICONS_DIR/${size}x${size}/apps/dig.png"
done
rm -f "$ICONS_DIR/scalable/apps/dig.svg"

if [ -d "$HERE/.venv" ]; then
  rm -rf "$HERE/.venv"
  say "  virtual environment removed"
fi

command -v update-desktop-database >/dev/null 2>&1 && \
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
  gtk-update-icon-cache -f -t "$ICONS_DIR" >/dev/null 2>&1 || true

say ""
say "Dig is removed. Your data was left alone:"
say "  $DATA_DIR"
say "Delete that folder yourself if you want the ideas gone too."
