# Prey2006

A fork of [FriskTheFallenHuman/Prey2006](https://github.com/FriskTheFallenHuman/Prey2006) (the Prey 2006 SDK integrated with the dhewm3 / Doom 3 GPL codebase) with fixes for game portals, widescreen and macOS. See the original repository for the project itself, building on other platforms and credits.

You need your own copy of Prey (2006) to play, the game data is not included.

## macOS

Download `Prey2006-<version>-macos-arm64.dmg` from the [releases](https://github.com/skowronmateusz/Prey2006/releases) (Apple Silicon, macOS 11 or newer):

1. Drag `Prey2006.app` into Applications.
2. Copy `pak000.pk4` ... `pak004.pk4` from your copy of the game (on the DVD in `Setup/Data/Base`, in a Windows installation in `base`) into `~/.local/share/prey06/base/`. If they are missing, the app offers to create and open this folder.
3. Start the app. The first time, macOS blocks it because it isn't notarized: right-click it and choose Open, or allow it in System Settings > Privacy & Security. If macOS says the app is damaged: `xattr -dr com.apple.quarantine /Applications/Prey2006.app`.

On the first start the app creates `~/.local/share/prey06/base/pak007.pk4` with the widescreen HUD, menus and other fixed files. Most of them are modified files of the game, so the app only contains patches and applies them to your copy of the game. The full instructions are in the `Read Me.txt` of the disk image ([release/macos/ReadMe.txt](../release/macos/ReadMe.txt)).

Savegames are stored in `~/.local/share/prey06/base`, the configuration in `~/.config/prey06/base`.

Building the release: [release/macos/README.md](../release/macos/README.md).

## Changes

Compared to the original repository:

### Game portals

- The view through a portal now has proper parallax: the portal camera mirrors the viewer's offset from the source portal, so the view changes when moving towards or away from the portal (it only rotated before).
- Geometry between the portal camera and the destination is clipped away, including opaque surfaces.
- Portal surfaces are drawn as flat windows on the portal plane. They are recessed frames, which caused a dark wedge next to the portal edge and black cones at grazing angles.
- Portals seen from behind and portals behind a destination portal are no longer rendered.
- The player's shadow stays hidden in portal views.
- The skybox seen next to a portal no longer covers the view through it: skybox views are now rendered before portal views, which draw over them where they overlap on screen.
- The view through a portal no longer disappears right before walking through it. The player is teleported when its origin crosses the portal plane, so the view gets closer to the plane than the near clip distance and the portal surface was clipped away, showing what is behind the source portal. The portal surface is now pushed away from the view (keeping its screen position), which also keeps the weapon visible.
- The `directportal` distance cull reads the correct shader parm (parm5 instead of parm6).
- New cvars: `r_portalFadeScale` (default 0 = no fade) scales the default entity def fade distances, `r_portalMapFadeScale` (default 1) scales the fade distances set by maps, and `r_portalMaxDepth` limits portals seen through portals.

### Widescreen / ultrawide

- The level loading screen shows the 4:3 level image completely, centered with black bars, instead of a cropped part of it stretched over the screen. The level title and progress bar are centered correctly.
- For ultrawide monitors, set `r_aspectRatio -1` (auto) so the horizontal FOV widens with the window instead of the image being stretched. The HUD keeps its aspect ratio with `gui_hudAdjustAspect 1` (default).

### Savegames

- Savegames stay loadable when a `.gui` file changed since saving. GUI registers are restored by name instead of by position, so adding `anchor` to the HUD for widescreen no longer crashes when loading older savegames.
- Fixed a one byte stack overflow in `idDeclManager::MakeNameCanonical()` for names that are too long, which aborted the game.

### Player getting stuck

- The player no longer gets stuck in walls, at curved wall/floor transitions or at railings in levels far from the map origin (e.g. The Old Tribes). The collision code computes Plücker coordinates in double precision again, as the original x87 builds effectively did; in single precision (x86_64, arm64) the rounding errors let the player bounding box slip into the geometry.

### macOS build

- After linking, the executables and the game dylib are relinked against `@rpath` (`neo/CMakeModules/MacBundleLibs.cmake`), with `@executable_path/../Frameworks` first and the original library directories (e.g. Homebrew) as fallback. The built `prey06` and `gamearm64.dylib` can be copied into `Prey2006.app/Contents/MacOS` as they are and use the libraries in the app bundle, and they still run from `output/macosx`.

- `release/macos/build_release.sh` builds `Prey2006.app` and a disk image without files of the retail game: SDL2 and OpenAL Soft from `neo/libs` and the binaries are built for macOS 11, the modified retail files of `pak007.pk4` ship as patches. `OUTPUT_FOLDER` can be set to build into another directory than `output/<os>`.

### File system

- `pak007.pk4` (the port's widescreen HUD, menus, loading screen and other fixed assets, next to the executable) now takes precedence over all other pk4s of the base game. Before, the directory of the executable was searched last when the game data was in another directory (for example `~/.local/share/prey06/base` on macOS/Linux), so the original files in `pak000.pk4` were used and the HUD was stretched. Loose files in the search directories and mods (`fs_game`) can still override it.
- The empty placeholder `base/default.cfg` is no longer packed into `pak007.pk4`, it replaced the default key bindings of the game.
