#!/usr/bin/env bash
# Remove Dig's launcher, icons, and command from your home folder.
#
# Your data is never touched. It stays in ~/.local/share/dig, with the
# attachments and the recovery history, until you delete it yourself.

set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS_DIR="$DATA_HOME/applications"
ICONS_DIR="$DATA_HOME/icons/hicolor"
BIN_DIR="$HOME/.local/bin"

say() { printf '%s\n' "$*"; }

say "Removing Dig"

rm -f "$APPS_DIR/dig.desktop"
command -v update-desktop-database >/dev/null 2>&1 &&
  update-desktop-database -q "$APPS_DIR" 2>/dev/null || true

for size in 16 24 32 48 64 128 256 512; do
  rm -f "$ICONS_DIR/${size}x${size}/apps/dig.png"
done
rm -f "$ICONS_DIR/scalable/apps/dig.svg"
command -v gtk-update-icon-cache >/dev/null 2>&1 &&
  gtk-update-icon-cache -q -t -f "$ICONS_DIR" 2>/dev/null || true

[ -L "$BIN_DIR/dig" ] && rm -f "$BIN_DIR/dig"

say ""
say "Dig is removed."
say "Your data is still at $DATA_HOME/dig. Delete that folder if you want it gone."
