# macOS release

`build_release.sh` builds `Prey2006.app` and `Prey2006-<version>-macos-arm64.dmg`. The disk image contains only the engine: no files of the retail game and no files derived from them.

## Requirements

- Xcode or the command line tools, CMake, Ninja, pkg-config (`brew install cmake ninja pkg-config`)
- The retail `pak000.pk4` ... `pak004.pk4`, used to create the patches and to check the result (default `~/.local/share/prey06/base`, or set `PREY_RETAIL_DIR`)

## Building

```bash
release/macos/build_release.sh 1.5.4-1
```

Everything is built in `build-release/macos` (ignored by git):

1. SDL2 and OpenAL Soft from `neo/libs` for macOS 11 (`MIN_MACOS`). The Homebrew libraries can't be used: they are built for the macOS version of the build machine, and Homebrew's SDL2 is sdl2-compat, which needs SDL3.
2. The engine, the dedicated server and the game library, with `OUTPUT_FOLDER=build-release/macos/output`, so `output/macosx` isn't touched.
3. `Prey2006.app`:
   - `Contents/MacOS/Prey2006`: `launcher.sh`, the main executable. It checks the game data, runs `install_assets.sh` if `pak007.pk4` is missing or outdated, and starts `prey06`.
   - `Contents/MacOS/prey06`, `prey06ded`, `gamearm64.dylib`
   - `Contents/Frameworks`: SDL2 and OpenAL Soft. The rpaths to the build directories are removed.
   - `Contents/Resources/pak007`: the pak007 payload (see below), `install_assets.sh`, the icon (drawn by `make_icon.swift`) and the licenses.
4. Ad-hoc signing. The app isn't notarized (that needs a paid Apple Developer account), so the players have to allow it once, see `ReadMe.txt`.
5. The disk image with the app, a link to Applications, `Read Me.txt` (`ReadMe.txt`) and the licenses. Before it is created, `pak007.py verify` checks every file, including the files in pk4/zip archives, against all files of the retail pk4s and against the files of `base/` that must not be released. The build fails if it finds one.

## pak007.pk4 without retail files

`base/` (packed into `pak007.pk4` by the CMake build) contains three kinds of files. `pak007.manifest` says what happens to each file:

| Kind | Examples | In the release |
|---|---|---|
| own files | `guis/anchors.guifragment`, `masterservers.lst` | `copy`: shipped as they are |
| modified retail files | `guis/*.gui`, `guis/**/*.guifragment`, `materials/gfx.mtr`, `materials/video.mtr` | `patch`: only a BSDIFF40 patch against the retail file is shipped |
| retail artwork and other files | hi-res loading screen, intro videos (3D Realms, Human Head), tutorial maps (Prey SDK), material editor files | not listed: never released |

The console textures `textures/gfx/console1.tga` and `console2.tga` are of unclear origin, so the release uses our own ones from `assets/` instead.

`pak007.py payload` creates the patches. It matches lines and ignores whitespace: the retail files have CRLF line endings and `base/` has LF. Matching bytes would turn every line into a change, and the patch would contain the whole retail file. Each patch is checked with the system's `bspatch`. `pak007.list` records the md5 of the retail file and of the result for every patch.

On the player's Mac, `install_assets.sh` takes each original file from the retail pk4s, checks its md5, applies the patch, and packs everything into `~/.local/share/prey06/base/pak007.pk4`. It only uses tools that come with macOS (`unzip`, `bspatch`, `zip`, `md5`). If a file of the player's copy differs (another version of the game), that file is skipped and the game uses its original. The engine gives `pak007.pk4` precedence over the retail pk4s, whatever directory it is in.

When a file in `base/` changes, add it to the manifest if it's new, and decide whether it is `copy` (own work) or `patch` (based on a retail file). Files not in the manifest are not released.

## Local setup with the files that aren't released

To get the same layout as a player, and still have the files that can't be released (hi-res loading screen, intro videos, tutorial maps, ...):

```bash
python3 release/macos/pak007.py extras ~/.local/share/prey06/base/zz_prey2006_extras.pk4
```

This packs every file of `base/` that is not in the manifest, except `default.cfg`. The name sorts after the retail pk4s, so its files override the retail ones (for example the loading screen).

## Publishing

- Use a tag that doesn't start with `v` (for example `macos-1.5.4-1`). Tags `v*` start `.github/workflows/Releases.yml`, which drafts a release with the CI builds of all platforms. Those builds contain the complete `pak007.pk4` from `base/`, including the retail files.
- Upload the `.dmg` and its `.sha256`, and copy the instructions from `ReadMe.txt` into the release notes.
