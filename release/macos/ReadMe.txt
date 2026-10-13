Prey2006 for macOS
==================

Prey2006 is a source port of Prey (2006) based on dhewm3 and the Prey SDK.

This download contains ONLY the engine. The game data (levels, models, textures,
sounds, music, videos) is not included: you need your own copy of Prey (2006)
for Windows, for example the original DVD.

Requirements: a Mac with Apple Silicon (M1 or newer) and macOS 11 or newer.


1. Install the app
------------------

Drag Prey2006.app onto the Applications folder in this window.


2. Copy the game data
---------------------

You need these five files from your copy of Prey (2006):

    pak000.pk4  pak001.pk4  pak002.pk4  pak003.pk4  pak004.pk4

Where to find them:
  - on the DVD:                        Setup/Data/Base/
  - in a Windows installation:         C:\Program Files\Prey\base\
    (or the "base" folder wherever Prey was installed)

Copy them into this folder on your Mac:

    ~/.local/share/prey06/base/

("~" is your home folder.) The easiest way:
  a) Start Prey2006.app once. It notices that the game data is missing,
     creates the folder and offers to open it ("Open Folder").
  b) Copy the five .pk4 files into the opened folder.

Or in Terminal:

    mkdir -p ~/.local/share/prey06/base
    cp /Volumes/<DVD name>/Setup/Data/Base/pak00*.pk4 ~/.local/share/prey06/base/

Tip: the folder starts with a dot-named folder (.local), which the Finder hides.
In the Finder use Go > Go to Folder... (Shift-Cmd-G) and paste the path above.

Other files from the game (game00.pk4, the Windows executables, the PunkBuster
files, ...) are not needed.


3. Start the game
-----------------

Start Prey2006 from the Applications folder.

The first time you open it, macOS will refuse to open it, because the app is not
notarized by Apple (it is a free hobby project):
  - Right-click (or Control-click) Prey2006.app and choose Open, then Open again.
  - On newer macOS versions: try to open the app once, then go to
    System Settings > Privacy & Security, scroll down and click "Open Anyway".
  - If macOS says the app "is damaged and can't be opened", run in Terminal:

        xattr -dr com.apple.quarantine /Applications/Prey2006.app

On the first start (and after updating the app) Prey2006 prepares its
widescreen HUD, menus and other fixes: they are modified versions of files of
the original game, so the app only contains the changes and applies them to
your copy of the game. This takes a few seconds and creates

    ~/.local/share/prey06/base/pak007.pk4

Your copy of the game is not modified. If something goes wrong, the details are
in ~/.local/share/prey06/install_assets.log.


Tips
----

- Savegames and screenshots are stored in ~/.local/share/prey06/base/ as well,
  the configuration in ~/.config/prey06/base/.
- Ultrawide monitors: open the console (Shift+Esc, or the key left of "1")
  and enter:  r_aspectRatio -1
- To uninstall, delete Prey2006.app and the folders ~/.local/share/prey06 and
  ~/.config/prey06.


Supported versions of the game
------------------------------

The fixes are made for the files of the retail DVD of Prey (2006) (version 1.0).
With other versions, files that differ are left as they are in your copy of the
game (the app tells you about it), the game still works.


License and source code
-----------------------

Prey2006 is free software under the GNU General Public License v3, see the
Licenses folder. It uses SDL2 (zlib license) and OpenAL Soft (LGPL).

Source code: https://github.com/skowronmateusz/Prey2006
Based on:    https://github.com/FriskTheFallenHuman/Prey2006

Prey is a trademark of its respective owners. This project is not affiliated
with or endorsed by them.
