#!/usr/bin/env bash
# Build a standalone LearnCad AppImage for Linux.
#
#   ./linux/build_appimage.sh
#   LEARNCAD_ENGINE_APPIMAGE=/path/to/engine.AppImage ./linux/build_appimage.sh
#
# The result bundles the modeling engine and LearnCad, then launches straight
# into LearnCad with its own isolated user data directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's:.*<version>\(.*\)</version>.*:\1:p' "$ROOT/package.xml" | head -n1)"
[ -n "$VERSION" ] || { echo "Could not read version from package.xml" >&2; exit 1; }

BUILD="$ROOT/dist/build"
APPDIR="$BUILD/LearnCad.AppDir"
TOOLS="$BUILD/tools"
TOOL="$TOOLS/appimagetool"
OUT="$ROOT/dist/LearnCad-$VERSION-linux-x86_64.AppImage"

find_engine() {
    if [ -n "${LEARNCAD_ENGINE_APPIMAGE:-}" ] && [ -f "$LEARNCAD_ENGINE_APPIMAGE" ]; then
        printf '%s\n' "$LEARNCAD_ENGINE_APPIMAGE"
        return
    fi
    if [ -n "${FREECAD_APPIMAGE:-}" ] && [ -f "$FREECAD_APPIMAGE" ]; then
        printf '%s\n' "$FREECAD_APPIMAGE"
        return
    fi
    local candidate
    for candidate in \
        "$HOME/Applications"/FreeCAD*Linux*x86_64*.AppImage \
        "$HOME/Applications"/FreeCAD*.AppImage \
        "$ROOT"/../Applications/FreeCAD*Linux*x86_64*.AppImage \
        /opt/FreeCAD*.AppImage \
        /opt/*/FreeCAD*.AppImage; do
        if [ -f "$candidate" ]; then
            printf '%s\n' "$candidate"
            return
        fi
    done
    return 1
}

ENGINE_APPIMAGE="$(find_engine || true)"
if [ -z "$ENGINE_APPIMAGE" ]; then
    cat >&2 <<'EOF'
Could not find a compatible engine AppImage. Set:

    LEARNCAD_ENGINE_APPIMAGE=/path/to/engine.AppImage ./linux/build_appimage.sh
EOF
    exit 1
fi

echo "LearnCad version : $VERSION"
echo "Engine AppImage  : $ENGINE_APPIMAGE"

mkdir -p "$BUILD" "$TOOLS"

if [ ! -x "$APPDIR/AppRun.freecad" ]; then
    echo "Extracting the modeling engine (first run only)..."
    rm -rf "$APPDIR" "$BUILD/squashfs-root"
    (
        cd "$BUILD"
        "$ENGINE_APPIMAGE" --appimage-extract >/dev/null
    )
    mv "$BUILD/squashfs-root" "$APPDIR"
    mv "$APPDIR/AppRun" "$APPDIR/AppRun.freecad"
fi

echo "Installing LearnCad into the bundle..."
rm -rf "$APPDIR/usr/Mod/LearnCad"
mkdir -p "$APPDIR/usr/Mod/LearnCad/freecad"
cp "$ROOT/package.xml" "$APPDIR/usr/Mod/LearnCad/"
cp "$ROOT/LICENSE" "$APPDIR/usr/Mod/LearnCad/"
cp "$ROOT/README.md" "$APPDIR/usr/Mod/LearnCad/"
cp -R "$ROOT/freecad/CADet" "$APPDIR/usr/Mod/LearnCad/freecad/CADet"
find "$APPDIR/usr/Mod/LearnCad" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$APPDIR/usr/Mod/LearnCad" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

install -m 755 "$ROOT/linux/AppRun" "$APPDIR/AppRun"
install -m 644 "$ROOT/linux/learncad.desktop" "$APPDIR/learncad.desktop"
install -d "$APPDIR/learncad-defaults"
install -m 644 "$ROOT/linux/learncad-defaults/user.cfg" "$APPDIR/learncad-defaults/user.cfg"
install -m 644 "$ROOT/brand/app-icon/learncad-app.svg" "$APPDIR/learncad.svg"
install -m 644 "$ROOT/brand/app-icon/learncad-app-compass-256.png" "$APPDIR/learncad.png"
ln -sfn learncad.svg "$APPDIR/.DirIcon"

install -d "$APPDIR/usr/share/icons/hicolor/scalable/apps"
install -d "$APPDIR/usr/share/icons/hicolor/256x256/apps"
install -m 644 "$ROOT/brand/app-icon/learncad-app.svg" \
    "$APPDIR/usr/share/icons/hicolor/scalable/apps/learncad.svg"
install -m 644 "$ROOT/brand/app-icon/learncad-app-compass-256.png" \
    "$APPDIR/usr/share/icons/hicolor/256x256/apps/learncad.png"

rm -f "$APPDIR/org.freecad.FreeCAD.desktop"
rm -f "$APPDIR/.DirIcon.dpkg-dist"

# Rebrand the bundled engine desktop entry and icons as a fallback, so any
# desktop that still resolves the engine id shows LearnCad anyway.
install -m 644 "$ROOT/linux/learncad.desktop" \
    "$APPDIR/usr/share/applications/org.freecad.FreeCAD.desktop"
ICON_ROOT="$APPDIR/usr/share/icons/hicolor"
if [ -d "$ICON_ROOT/scalable/apps" ]; then
    install -m 644 "$ROOT/brand/app-icon/learncad-app.svg" \
        "$ICON_ROOT/scalable/apps/org.freecad.FreeCAD.svg"
fi
for size in 16 32 48 64 256; do
    if [ -d "$ICON_ROOT/${size}x${size}/apps" ]; then
        install -m 644 "$ROOT/brand/app-icon/learncad-app-compass-${size}.png" \
            "$ICON_ROOT/${size}x${size}/apps/org.freecad.FreeCAD.png"
    fi
done

if [ ! -x "$TOOL" ]; then
    echo "Downloading appimagetool..."
    curl -fL --retry 2 -o "$TOOL" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOL"
fi

rm -f "$OUT"
echo "Packing AppImage (this takes a few minutes)..."
ARCH=x86_64 "$TOOL" --no-appstream "$APPDIR" "$OUT"

chmod +x "$OUT"
echo
echo "Built:  $OUT"
echo "Size:   $(du -h "$OUT" | cut -f1)"
echo "SHA256: $(sha256sum "$OUT" | cut -d' ' -f1)"
echo
echo "Run it with: $OUT"
