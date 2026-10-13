<p align="center"> <img src="https://cdn2.steamgriddb.com/logo_thumb/c5ab0bc60ac7929182aadd08703f1ec6.png">

> [!TIP]
> We have a discord server, feel free to join the discussion, the invite is [here.](https://discord.gg/tJDGrk6w4H)

> [!CAUTION]
> You **MUST** source your own legal copy of Prey (2006) to run this, i wouldn't provide any links for this.
> i've been getting a lot of questions about but, please keep in mind this is just a source port.

> [!IMPORTANT]
> We are currently looking for contributors that wants to contribute into this project.

> [!CAUTION]
> This project is far from being completed, currently there is a lot of visual problems with guis and the game portals.
> 
> The binaries are provide as-is, support may be limited due to my lack of knowledge,
> This project was create due to the insatisfaction of some source ports barely fixing or improving
> and or sacrificing features for other platforms.
> I hope you guys understand, but contributions are welcome :)

# Introduction

Prey 2006 SDK integrated with Doom 3 GPL release

## About

This project is a code integration of the Prey 2006 SDK against the Doom 3 GPL codebase.
This means this includes new engine side features that were in the Prey 2006 engine,
and some adjustments to the Prey 2006 SDK code.

This runs in a semi vanilla Dhewm3 v1.5.4 fork that specifically removes imgui, soft particles and joystick support for the time being.

## Changes in this fork

Compared to the [original repository](https://github.com/FriskTheFallenHuman/Prey2006):

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

### File system

- `pak007.pk4` (the port's widescreen HUD, menus, loading screen and other fixed assets, next to the executable) now takes precedence over all other pk4s of the base game. Before, the directory of the executable was searched last when the game data was in another directory (for example `~/.local/share/prey06/base` on macOS/Linux), so the original files in `pak000.pk4` were used and the HUD was stretched. Loose files in the search directories and mods (`fs_game`) can still override it.

## Compiling

For Windows:

- Clone the repo.
- Install [Visual Studio 2019](https://visualstudio.microsoft.com/vs/older-downloads/) or Visual [Visual Studio 2022](https://visualstudio.microsoft.com/vs/)
- [CMake](https://cmake.org/download/)
- Run either **cmake_msvc2019.cmd** or **cmake_msvc2022.cmd**

For Debian/Ubuntu

- Intall the dependencies
  - ```sudo apt install libgl1-mesa-dev libsdl2-dev libopenal-dev libcurl4-openssl-dev cmake ninja-build```
- Make **cmake_linux.sh** a executable and execute with
  - ```./cmake_linux.sh gcc release```

For other Linux Distros: It should compile just fine in theory.

## Credits

This fork wouldn't be possible by the 3 previous attempts of porting Prey before me:

- [PreyDoom](https://github.com/jmarshall23/PreyDoom)
- [PreyVR](https://github.com/neitey/PreyVR)
- [com.n0n3m4.diii4a](https://github.com/glKarin/com.n0n3m4.diii4a)
- [dhewm3](https://github.com/dhewm/dhewm3)
