#!/usr/bin/env bash
# Everything a release is made of: the AppImage, the source, and the sums.
#
#   packaging/build-release.sh [output-directory]
#
# The source tarball is what git has, so it is exactly what the repository
# holds and nothing that happens to be lying around beside it. The sums are
# there so a stranger can check what they downloaded before running it.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$HERE/dist}"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$HERE/dig/__init__.py")"

say() { printf '\n== %s\n' "$*"; }
die() { printf 'build-release: %s\n' "$*" >&2; exit 1; }

[ -n "$VERSION" ] || die "could not read the version out of dig/__init__.py"
command -v git >/dev/null || die "git is not on the PATH"

if [ -n "$(git -C "$HERE" status --porcelain)" ]; then
  die "the working tree has changes. The source tarball is made from what git
has, so commit or stash first and the tarball will match the tag."
fi

mkdir -p "$OUT"
rm -f "$OUT/SHA256SUMS"

say "Source"
tarball="$OUT/dig-$VERSION-source.tar.gz"
git -C "$HERE" archive --format=tar.gz \
    --prefix="dig-$VERSION/" -o "$tarball" HEAD
say "Wrote $(basename "$tarball"), $(du -h "$tarball" | cut -f1)"

say "AppImage"
appimage="$OUT/Dig-$VERSION-x86_64.AppImage"
if [ -f "$appimage" ] && [ "${REUSE_APPIMAGE:-}" = "1" ]; then
  say "Reusing the one already built"
else
  "$HERE/packaging/build-appimage.sh" "$OUT"
fi

say "Sums"
( cd "$OUT" && sha256sum "Dig-$VERSION-x86_64.AppImage" "dig-$VERSION-source.tar.gz" \
    > SHA256SUMS )
cat "$OUT/SHA256SUMS"

say "Checking them back"
( cd "$OUT" && sha256sum -c SHA256SUMS )

say "Release $VERSION is in $OUT"
ls -lh "$OUT"
