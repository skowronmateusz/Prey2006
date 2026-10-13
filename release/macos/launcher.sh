#!/bin/bash
#
# Main executable of Prey2006.app: makes sure the game data is there and pak007.pk4
# was built from it (see install_assets.sh), then starts the game.

MACOS="$(cd "$(dirname "$0")" && pwd)"
RESOURCES="$MACOS/../Resources"
DATA="$HOME/.local/share/prey06/base"
LOG="$HOME/.local/share/prey06/install_assets.log"

alert() {	# message [buttons...] -> prints the clicked button
	local msg="$1"
	shift
	local buttons=""
	for b in "$@"; do buttons="$buttons, \"$b\""; done
	osascript - "$msg" <<EOF 2>/dev/null
on run argv
	set r to display dialog (item 1 of argv) with title "Prey2006" buttons {${buttons#, }} default button 1 with icon caution
	return button returned of r
end run
EOF
}

"$RESOURCES/install_assets.sh" --check "$DATA"
case $? in
	0)
		;;
	2)
		mkdir -p "$DATA"
		answer="$(alert "The game data of Prey (2006) wasn't found.

Copy the files pak000.pk4, pak001.pk4, pak002.pk4, pak003.pk4 and pak004.pk4 from your copy of the game (on the DVD in Setup/Data/Base) into the folder:

$DATA

Then start Prey2006 again. See the Read Me for details." "Open Folder" "Quit")"
		[ "$answer" = "Open Folder" ] && open "$DATA"
		exit 1
		;;
	*)
		mkdir -p "$(dirname "$LOG")"
		"$RESOURCES/install_assets.sh" "$DATA" > "$LOG" 2>&1
		case $? in
			0) ;;
			3)
				alert "Some files of the widescreen HUD and menus couldn't be installed because your copy of the game has a different version. The game will use its original files instead.

Details: $LOG" "OK" > /dev/null
				;;
			*)
				answer="$(alert "Preparing the game data failed. Details: $LOG" "Start Anyway" "Quit")"
				[ "$answer" = "Start Anyway" ] || exit 1
				;;
		esac
		;;
esac

exec "$MACOS/prey06" "$@"
