#!/bin/bash
#
# Builds pak007.pk4 (the widescreen HUD, menus and other fixes of Prey2006) from the
# player's own copy of Prey (2006).
#
# Most of these files are modified retail files, which can't be distributed, so the app
# only contains patches against them. This script takes the original files from the
# retail pk4s, applies the patches and writes pak007.pk4 next to the game data.
#
# Usage: install_assets.sh [--check] [<game data directory>]
#   --check    only check whether the game data is there and pak007.pk4 is up to date
#              exit code 0: OK, 1: pak007.pk4 must be (re)built, 2: retail pk4s missing
# The default game data directory is ~/.local/share/prey06/base.
#
# Only uses tools that come with macOS (unzip, bspatch, zip, md5).

set -u

RESOURCES="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="$RESOURCES/pak007"
LIST="$PAYLOAD/pak007.list"
RETAIL_PAKS="pak000.pk4 pak001.pk4 pak002.pk4 pak003.pk4 pak004.pk4"

CHECK=0
if [ "${1:-}" = "--check" ]; then
	CHECK=1
	shift
fi
DATA="${1:-$HOME/.local/share/prey06/base}"
STAMP="$DATA/.pak007.stamp"

missing=""
for p in $RETAIL_PAKS; do
	[ -f "$DATA/$p" ] || missing="$missing $p"
done

if [ $CHECK = 1 ]; then
	[ -n "$missing" ] && exit 2
	[ -f "$DATA/pak007.pk4" ] || exit 1
	[ "$(cat "$STAMP" 2>/dev/null)" = "$(md5 -q "$LIST")" ] || exit 1
	exit 0
fi

if [ -n "$missing" ]; then
	echo "error: the game data of Prey (2006) wasn't found in $DATA (missing:$missing)" >&2
	echo "Copy pak000.pk4 ... pak004.pk4 from your copy of the game there, see the Read Me." >&2
	exit 2
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/prey2006-pak007.XXXXXX")" || exit 1
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/pak"

# the original file: the last retail pk4 containing it (like the game) and with the expected checksum
extract_retail() {	# path expected_md5 output
	local p
	for p in pak004.pk4 pak003.pk4 pak002.pk4 pak001.pk4 pak000.pk4; do
		if unzip -p "$DATA/$p" "$1" > "$3" 2>/dev/null && [ -s "$3" ]; then
			[ "$(md5 -q "$3")" = "$2" ] && return 0
		fi
	done
	return 1
}

patched=0
copied=0
skipped=""
while read -r kind path a b; do
	case "$kind" in
		copy)
			mkdir -p "$WORK/pak/$(dirname "$path")"
			cp "$PAYLOAD/files/$path" "$WORK/pak/$path" || exit 1
			copied=$((copied + 1))
			;;
		patch)
			mkdir -p "$WORK/pak/$(dirname "$path")"
			if extract_retail "$path" "$a" "$WORK/original" &&
				bspatch "$WORK/original" "$WORK/pak/$path" "$PAYLOAD/patches/$path.bsdiff" &&
				[ "$(md5 -q "$WORK/pak/$path")" = "$b" ]; then
				patched=$((patched + 1))
			else
				# a different version of the game: keep its original file
				rm -f "$WORK/pak/$path"
				skipped="$skipped $path"
			fi
			;;
	esac
done < <(grep -v '^#' "$LIST")

if [ $patched = 0 ]; then
	echo "error: none of the original files matched, is this a supported version of Prey (2006)?" >&2
	exit 1
fi

( cd "$WORK/pak" && zip -q -X -r "$WORK/pak007.pk4" . ) || exit 1
mv -f "$WORK/pak007.pk4" "$DATA/pak007.pk4" || exit 1
md5 -q "$LIST" > "$STAMP"

echo "Created $DATA/pak007.pk4 ($patched patched, $copied added files)"
if [ -n "$skipped" ]; then
	echo "warning: these files differ in your copy of the game and were left unchanged:" >&2
	for s in $skipped; do echo "  $s" >&2; done
	exit 3
fi
exit 0
