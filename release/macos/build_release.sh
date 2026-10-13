#!/bin/bash
#
# Builds the macOS release of Prey2006: Prey2006.app and Prey2006-<version>-macos-arm64.dmg
# without any files of the retail game (see README.md in this directory).
#
# Usage: release/macos/build_release.sh [version]
#
# Environment:
#   PREY_RETAIL_DIR   directory with the retail pak000-004.pk4, needed to create the
#                     patches (default: ~/.local/share/prey06/base)
#   MIN_MACOS         minimum macOS version (default: 11.0)
#
# Needs Xcode (or the command line tools), CMake, Ninja and pkg-config.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
VERSION="${1:-$(git -C "$REPO" describe --tags --always | sed 's/^v//')}"
MIN_MACOS="${MIN_MACOS:-11.0}"
RETAIL="${PREY_RETAIL_DIR:-$HOME/.local/share/prey06/base}"
ARCH=arm64

BUILD="$REPO/build-release/macos"
DEPS="$BUILD/deps"
OUT="$BUILD/output"
APP="$BUILD/Prey2006.app"
DMG_STAGE="$BUILD/dmg"
DMG="$BUILD/Prey2006-$VERSION-macos-$ARCH.dmg"

export MACOSX_DEPLOYMENT_TARGET="$MIN_MACOS"
CMAKE_COMMON=(-G Ninja -DCMAKE_BUILD_TYPE=Release
	-DCMAKE_OSX_DEPLOYMENT_TARGET="$MIN_MACOS" -DCMAKE_OSX_ARCHITECTURES="$ARCH")

step() { printf '\n=== %s\n' "$*"; }

for tool in cmake ninja pkg-config; do
	command -v $tool > /dev/null || { echo "error: $tool is required" >&2; exit 1; }
done
[ -f "$RETAIL/pak000.pk4" ] || { echo "error: retail pk4s not found in $RETAIL (set PREY_RETAIL_DIR)" >&2; exit 1; }

# --- libraries: SDL2 and OpenAL Soft from neo/libs, built for MIN_MACOS ----------------

if [ ! -f "$DEPS/lib/libSDL2-2.0.0.dylib" ]; then
	step "Building SDL2"
	cmake -S "$REPO/neo/libs/SDL2" -B "$BUILD/sdl2" "${CMAKE_COMMON[@]}" \
		-DCMAKE_INSTALL_PREFIX="$DEPS" -DSDL_SHARED=ON -DSDL_STATIC=OFF -DSDL_TEST=OFF
	cmake --build "$BUILD/sdl2"
	cmake --install "$BUILD/sdl2"
fi

if [ ! -f "$DEPS/lib/libopenal.1.dylib" ]; then
	step "Building OpenAL Soft"
	cmake -S "$REPO/neo/libs/OpenalSoft" -B "$BUILD/openal" "${CMAKE_COMMON[@]}" \
		-DCMAKE_INSTALL_PREFIX="$DEPS" -DLIBTYPE=SHARED -DALSOFT_INSTALL=ON \
		-DALSOFT_UTILS=OFF -DALSOFT_EXAMPLES=OFF -DALSOFT_TESTS=OFF \
		-DALSOFT_BACKEND_PIPEWIRE=OFF -DALSOFT_BACKEND_JACK=OFF -DALSOFT_BACKEND_PORTAUDIO=OFF \
		-DALSOFT_REQUIRE_COREAUDIO=ON
	cmake --build "$BUILD/openal"
	cmake --install "$BUILD/openal"
fi

# --- engine and game -----------------------------------------------------------------

step "Building the engine"
# only our libraries, not the ones of Homebrew
PKG_CONFIG_LIBDIR="$DEPS/lib/pkgconfig" PKG_CONFIG_PATH="" \
cmake -S "$REPO/neo" -B "$BUILD/engine" "${CMAKE_COMMON[@]}" \
	-DOUTPUT_FOLDER="$OUT" -DDEDICATED=ON \
	-DOPENAL_INCLUDE_DIR="$DEPS/include" -DOPENAL_LIBRARY="$DEPS/lib/libopenal.dylib"
cmake --build "$BUILD/engine"

# --- app bundle ----------------------------------------------------------------------

step "Assembling Prey2006.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Frameworks" "$APP/Contents/Resources/licenses"

sed -e "s/@VERSION@/$VERSION/g" -e "s/@MIN_MACOS@/$MIN_MACOS/g" "$HERE/Info.plist.in" > "$APP/Contents/Info.plist"
printf 'APPL????' > "$APP/Contents/PkgInfo"

install -m 755 "$HERE/launcher.sh" "$APP/Contents/MacOS/Prey2006"
install -m 755 "$OUT/prey06" "$OUT/prey06ded" "$APP/Contents/MacOS/"
install -m 644 "$BUILD/engine/game$ARCH.dylib" "$APP/Contents/MacOS/"
cp "$DEPS/lib/libSDL2-2.0.0.dylib" "$APP/Contents/Frameworks/"
cp -L "$DEPS/lib/libopenal.1.dylib" "$APP/Contents/Frameworks/"

# the binaries also have rpaths to the build directories (to run from $OUT), remove them
for bin in "$APP/Contents/MacOS/prey06" "$APP/Contents/MacOS/prey06ded"; do
	otool -l "$bin" | awk '/cmd LC_RPATH/ { getline; getline; print $2 }' | while read -r rp; do
		[ "$rp" = "@executable_path/../Frameworks" ] || install_name_tool -delete_rpath "$rp" "$bin"
	done
done
for lib in "$APP/Contents/Frameworks/"*.dylib; do
	install_name_tool -id "@rpath/$(basename "$lib")" "$lib"
done

install -m 755 "$HERE/install_assets.sh" "$APP/Contents/Resources/install_assets.sh"
python3 -I "$HERE/pak007.py" --retail "$RETAIL" payload "$APP/Contents/Resources/pak007"

ICONSET="$BUILD/Prey2006.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"
swift "$HERE/make_icon.swift" "$BUILD/icon_1024.png" 1024
for size in 16 32 128 256 512; do
	sips -z $size $size "$BUILD/icon_1024.png" --out "$ICONSET/icon_${size}x${size}.png" > /dev/null
	double=$((size * 2))
	sips -z $double $double "$BUILD/icon_1024.png" --out "$ICONSET/icon_${size}x${size}@2x.png" > /dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/Prey2006.icns"

cp "$REPO/.github/COPYING.txt" "$APP/Contents/Resources/licenses/Prey2006-GPL-3.0.txt"
cp "$REPO/neo/libs/SDL2/LICENSE.txt" "$APP/Contents/Resources/licenses/SDL2-zlib.txt"
cp "$REPO/neo/libs/OpenalSoft/COPYING" "$APP/Contents/Resources/licenses/OpenAL-Soft-LGPL-2.0.txt"
cp "$REPO/neo/libs/OpenalSoft/LICENSE-pffft" "$APP/Contents/Resources/licenses/OpenAL-Soft-pffft.txt"

# check that the binaries run on MIN_MACOS and only use system libraries or the bundle
for bin in "$APP/Contents/MacOS/prey06" "$APP/Contents/MacOS/prey06ded" "$APP/Contents/MacOS/game$ARCH.dylib" "$APP/Contents/Frameworks/"*.dylib; do
	minos="$(otool -l "$bin" | awk '/LC_BUILD_VERSION/ { f = 1 } f && $1 == "minos" { print $2; exit }')"
	if [ "$minos" != "$MIN_MACOS" ]; then
		echo "error: $(basename "$bin") requires macOS $minos" >&2
		exit 1
	fi
	if otool -L "$bin" | tail -n +2 | awk '{ print $1 }' | grep -Ev '^(/usr/lib/|/System/|@rpath/)'; then
		echo "error: $(basename "$bin") links libraries outside the system and the app bundle" >&2
		exit 1
	fi
done

step "Signing (ad-hoc)"
codesign --force --sign - "$APP/Contents/Frameworks/"*.dylib "$APP/Contents/MacOS/game$ARCH.dylib" \
	"$APP/Contents/MacOS/prey06" "$APP/Contents/MacOS/prey06ded"
codesign --force --sign - "$APP"
codesign --verify --deep --strict "$APP"

# --- disk image ----------------------------------------------------------------------

step "Creating the disk image"
rm -rf "$DMG_STAGE" "$DMG"
mkdir -p "$DMG_STAGE"
cp -R "$APP" "$DMG_STAGE/"
ln -s /Applications "$DMG_STAGE/Applications"
cp "$HERE/ReadMe.txt" "$DMG_STAGE/Read Me.txt"
cp -R "$APP/Contents/Resources/licenses" "$DMG_STAGE/Licenses"

step "Checking for files of the retail game"
python3 -I "$HERE/pak007.py" --retail "$RETAIL" verify "$DMG_STAGE"

hdiutil create -volname "Prey2006 $VERSION" -srcfolder "$DMG_STAGE" -fs HFS+ -format UDZO -ov "$DMG"
shasum -a 256 "$DMG" | tee "$DMG.sha256"
echo "Done: $DMG"
