#!/usr/bin/env bash
# Build an x86_64 AppImage of Dig.
#
# One file a stranger can download, mark executable, and run, with no install,
# no root, and nothing from their own system needed. That means the Python
# interpreter, PySide6, Qt 6 including WebEngine, and every shared library the
# three of them reach for all go inside.
#
#   packaging/build-appimage.sh [output-directory]
#
# The AppImage is built from what is installed on this machine, which is the
# same set the tests and the fidelity pass ran against.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$HERE/dist}"
WORK="${TMPDIR:-/tmp}/dig-appimage.$$"
APPDIR="$WORK/AppDir"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$HERE/dig/__init__.py")"

say() { printf '\n== %s\n' "$*"; }
die() { printf 'build-appimage: %s\n' "$*" >&2; exit 1; }

[ -n "$VERSION" ] || die "could not read the version out of dig/__init__.py"
command -v python3 >/dev/null || die "python3 is not on the PATH"
command -v ldd >/dev/null || die "ldd is not on the PATH"

# The virtual environment is what the tests and the fidelity pass run against,
# so it is what gets bundled. It borrows PySide6 from the system, so the two
# places have to be looked up separately.
PYBIN="$HERE/.venv/bin/python"
[ -x "$PYBIN" ] || PYBIN="$(command -v python3)"
PY_MINOR="$("$PYBIN" -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
PY_REAL="$("$PYBIN" -c 'import sys;print(sys._base_executable)')"
PY_STDLIB="$("$PYBIN" -c 'import sysconfig;print(sysconfig.get_paths()["stdlib"])')"
# The interpreter looks for its own library under sys.platlibdir, which is
# lib64 here and lib elsewhere, so the AppDir has to use the same word.
PY_LIBDIR="$("$PYBIN" -c 'import sys;print(sys.platlibdir)')"
PY_SIDE="$("$PYBIN" -c 'import PySide6,os;print(os.path.dirname(os.path.dirname(PySide6.__file__)))')"
QT_LIBEXEC="$(ls -d /usr/lib64/qt6/libexec 2>/dev/null || true)"
QT_PLUGINS="$(ls -d /usr/lib64/qt6/plugins 2>/dev/null || true)"
QT_RESOURCES="$(ls -d /usr/share/qt6/resources 2>/dev/null || true)"
QT_TRANSLATIONS="$(ls -d /usr/share/qt6/translations 2>/dev/null || true)"

[ -d "$PY_STDLIB" ] || die "cannot find the Python standard library"
[ -n "$QT_LIBEXEC" ] || die "cannot find Qt's libexec, so QtWebEngineProcess is missing"
[ -n "$QT_RESOURCES" ] || die "cannot find Qt's WebEngine resources"

# Libraries every Linux already has, and that bundling would break rather than
# help: the loader and the C library have to be the host's.
KEEP_OUT='^(ld-linux|libc|libm|libdl|librt|libpthread|libresolv|libnsl|libutil|libgcc_s|libstdc\+\+|libGL|libGLX|libGLdispatch|libEGL|libOpenGL|libdrm|libgbm|libX11|libxcb|libXext|libXau|libXdmcp|libwayland)'

mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/$PY_LIBDIR" "$APPDIR/usr/bin" "$APPDIR/usr/share"
trap 'rm -rf "$WORK"' EXIT

# ------------------------------------------------------------------ the app

say "Dig $VERSION"
mkdir -p "$APPDIR/usr/lib/dig"
for item in app.py dig assets packaging LICENSE README.md; do
  cp -r "$HERE/$item" "$APPDIR/usr/lib/dig/"
done
find "$APPDIR/usr/lib/dig" -name '__pycache__' -type d -prune -exec rm -rf {} +

# --------------------------------------------------------------- the python

say "Python $PY_MINOR"
PY_HOME="$APPDIR/usr/$PY_LIBDIR/python$PY_MINOR"
mkdir -p "$PY_HOME"
cp -r "$PY_STDLIB"/. "$PY_HOME/"
rm -rf "$PY_HOME/test" "$PY_HOME/idlelib" "$PY_HOME/tkinter" \
       "$PY_HOME/turtledemo" "$PY_HOME/ensurepip"
find "$PY_HOME" -name '__pycache__' -type d -prune -exec rm -rf {} +
cp "$PY_REAL" "$APPDIR/usr/bin/python3"

# The extension modules, which live beside the pure Python on Fedora.
if [ -d "$PY_STDLIB/lib-dynload" ] && [ ! -d "$PY_HOME/lib-dynload" ]; then
  mkdir -p "$PY_HOME/lib-dynload"
  cp -r "$PY_STDLIB/lib-dynload/." "$PY_HOME/lib-dynload/"
fi

# ------------------------------------------------------------------- pyside

say "PySide6 and Qt"
SITE="$PY_HOME/site-packages"
mkdir -p "$SITE"
cp -r "$PY_SIDE/PySide6" "$SITE/"
for extra in shiboken6 shiboken6_generator; do
  [ -d "$PY_SIDE/$extra" ] && cp -r "$PY_SIDE/$extra" "$SITE/"
done
# segno is pure Python and small; the pairing QR code needs it, and it lives in
# the virtual environment rather than beside PySide6.
segno_at="$("$PYBIN" -c 'import segno,os;print(os.path.dirname(segno.__file__))' 2>/dev/null || true)"
[ -n "$segno_at" ] && cp -r "$segno_at" "$SITE/"
find "$SITE" -name '__pycache__' -type d -prune -exec rm -rf {} +
# Qt's own examples and build files are not needed to run anything.
rm -rf "$SITE/PySide6/examples" "$SITE/PySide6/include" \
       "$SITE/PySide6/typesystems" "$SITE/shiboken6_generator"

mkdir -p "$APPDIR/usr/lib/qt6"
cp -r "$QT_LIBEXEC" "$APPDIR/usr/lib/qt6/"
[ -n "$QT_PLUGINS" ] && cp -r "$QT_PLUGINS" "$APPDIR/usr/lib/qt6/"
mkdir -p "$APPDIR/usr/share/qt6"
cp -r "$QT_RESOURCES" "$APPDIR/usr/share/qt6/"
[ -n "$QT_TRANSLATIONS" ] && cp -r "$QT_TRANSLATIONS" "$APPDIR/usr/share/qt6/"
# Only the plugins a desktop app actually loads. The rest is other people's
# software that happens to live in the same folder on this distribution.
if [ -d "$APPDIR/usr/lib/qt6/plugins" ]; then
  ( cd "$APPDIR/usr/lib/qt6/plugins" && \
    for d in *; do
      case "$d" in
        platforms|platformthemes|imageformats|iconengines|xcbglintegrations| \
        wayland-*|tls|networkinformation|egldeviceintegrations|generic| \
        platforminputcontexts|sqldrivers) ;;
        *) rm -rf "$d" ;;
      esac
    done )
fi

# ------------------------------------------------- every library they reach for

say "Shared libraries"
collect() {
  local target="$1"
  ldd "$target" 2>/dev/null | awk '/=> \//{print $3}'
}

needed="$WORK/needed"
: > "$needed"
{
  collect "$APPDIR/usr/bin/python3"
  collect "$APPDIR/usr/lib/qt6/libexec/QtWebEngineProcess"
  find "$SITE/PySide6" -name '*.so*' \
    -exec sh -c 'ldd "$1" 2>/dev/null | awk "/=> \//{print \$3}"' _ {} \;
  find "$PY_HOME/lib-dynload" -name '*.so' \
    -exec sh -c 'ldd "$1" 2>/dev/null | awk "/=> \//{print \$3}"' _ {} \; 2>/dev/null
  find "$APPDIR/usr/lib/qt6/plugins" -name '*.so' \
    -exec sh -c 'ldd "$1" 2>/dev/null | awk "/=> \//{print \$3}"' _ {} \; 2>/dev/null
} | sort -u > "$needed"

# Anything those libraries themselves need, until nothing new turns up.
round=0
while [ $round -lt 8 ]; do
  more="$WORK/more"
  : > "$more"
  while read -r lib; do
    [ -f "$lib" ] && collect "$lib"
  done < "$needed" | sort -u > "$more"
  cat "$needed" "$more" | sort -u > "$WORK/both"
  if cmp -s "$WORK/both" "$needed"; then break; fi
  mv "$WORK/both" "$needed"
  round=$((round + 1))
done

copied=0
while read -r lib; do
  base="$(basename "$lib")"
  if printf '%s' "$base" | grep -Eq "$KEEP_OUT"; then continue; fi
  # Qt's own libraries are already inside PySide6 on this distribution.
  if [ -f "$APPDIR/usr/lib/$base" ]; then continue; fi
  cp -L "$lib" "$APPDIR/usr/lib/$base" 2>/dev/null && copied=$((copied + 1))
done < "$needed"
say "$copied libraries bundled"

# ---------------------------------------------------------------- the wrapper

cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
# Everything Dig needs is inside this file. Nothing is read from the system
# except the kernel, the C library, and the graphics drivers.
HERE="$(dirname "$(readlink -f "$0")")"
for d in lib64 lib; do
  found="$(ls "$HERE/usr/$d" 2>/dev/null | sed -n 's/^python\([0-9]\+\.[0-9]\+\)$/\1/p' | head -1)"
  if [ -n "$found" ]; then PY_LIBDIR="$d"; PY_MINOR="$found"; break; fi
done
SITE="$HERE/usr/$PY_LIBDIR/python$PY_MINOR/site-packages"

export LD_LIBRARY_PATH="$HERE/usr/lib:$SITE/PySide6/Qt/lib:${LD_LIBRARY_PATH:-}"
export PYTHONHOME="$HERE/usr"
export PYTHONPATH="$SITE:$HERE/usr/lib/dig"
export PYTHONDONTWRITEBYTECODE=1

export QTWEBENGINEPROCESS_PATH="$HERE/usr/lib/qt6/libexec/QtWebEngineProcess"
export QTWEBENGINE_RESOURCES_PATH="$HERE/usr/share/qt6/resources"
export QTWEBENGINE_LOCALES_PATH="$HERE/usr/share/qt6/translations/qtwebengine_locales"
export QT_PLUGIN_PATH="$HERE/usr/lib/qt6/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="$HERE/usr/lib/qt6/plugins/platforms"

# The Chromium sandbox needs either a setuid helper or user namespaces, and an
# AppImage can promise neither. Dig loads one local file and refuses every
# request that is not already on this computer, so there is nothing for the
# sandbox to contain.
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox ${QTWEBENGINE_CHROMIUM_FLAGS:-}"

exec "$HERE/usr/bin/python3" "$HERE/usr/lib/dig/app.py" "$@"
RUN
chmod +x "$APPDIR/AppRun"

cp "$HERE/packaging/dig.desktop" "$APPDIR/dig.desktop"
sed -i 's|^Exec=.*|Exec=dig|' "$APPDIR/dig.desktop"
mkdir -p "$APPDIR/usr/share/applications"
cp "$APPDIR/dig.desktop" "$APPDIR/usr/share/applications/dig.desktop"

icon="$(ls "$HERE"/assets/icons/*256*.png 2>/dev/null | head -1)"
[ -n "$icon" ] || icon="$(ls "$HERE"/assets/icons/*.png 2>/dev/null | head -1)"
[ -n "$icon" ] || die "no icon to put in the AppImage"
cp "$icon" "$APPDIR/dig.png"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp "$icon" "$APPDIR/usr/share/icons/hicolor/256x256/apps/dig.png"

# ------------------------------------------------------------------ pack it

say "Packing"
mkdir -p "$OUT"
tool="${APPIMAGETOOL:-$(command -v appimagetool || true)}"
if [ -z "$tool" ]; then
  tool="$WORK/appimagetool"
  curl -fsSL -o "$tool" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage \
    || die "no appimagetool, and it could not be downloaded"
  chmod +x "$tool"
fi

target="$OUT/Dig-$VERSION-x86_64.AppImage"
rm -f "$target"
ARCH=x86_64 "$tool" --appimage-extract-and-run "$APPDIR" "$target" >/dev/null 2>&1 \
  || ARCH=x86_64 "$tool" "$APPDIR" "$target"
chmod +x "$target"

say "Built $target"
du -h "$target" | cut -f1
