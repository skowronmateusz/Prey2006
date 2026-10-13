# macOS release

`build_release.sh` builds `Prey2006.app` and `Prey2006-<version>-macos-arm64.dmg`. The disk image contains only the engine: no files of the retail game and no files derived from them.

The GitHub workflow `.github/workflows/macOS.yml` runs the tests and the build for every push to `main` and every pull request. Pushing a tag `macos-<version>` publishes a release.

## Publishing a release

```bash
git tag macos-1.5.4-2
git push fork macos-1.5.4-2
```

The workflow then:

1. runs the tests of the release tools (`tests/test_pak007.py`), including the check that `pak007.manifest` covers every file of `base/` and that the committed patches are up to date,
2. builds the app and runs the app tests (`tests/test_app.py`),
3. checks the disk image for files that must not be released,
4. creates the GitHub release `macos-1.5.4-2` with the disk image, its SHA-256 and the notes from `release-notes.md.in`.

The version is the tag without `macos-`. Don't use tags starting with `v`: they start `.github/workflows/Releases.yml`, the release workflow of the original repository for the other platforms.

## Changing files in base/

The CI doesn't have the retail game, so the patches of `pak007.pk4` are created locally and committed:

- **New file in `base/`:** add it to `pak007.manifest` as `copy` (own work), `patch` (based on a retail file) or `exclude` (must not be released). The tests fail if a file isn't listed.
- **Changed `patch` file, or a new one:** run `python3 release/macos/pak007.py patches`. It needs the retail pk4s in `~/.local/share/prey06/base`, or set `PREY_RETAIL_DIR`. Commit `release/macos/patches`. The tests fail if a patch is outdated.

## Building locally

Requirements: Xcode or the command line tools, CMake, Ninja, pkg-config (`brew install cmake ninja pkg-config`).

```bash
release/macos/build_release.sh 1.5.4-2
python3 -m unittest discover -s release/macos/tests -v
```

If the retail pk4s are found (`PREY_RETAIL_DIR`, default `~/.local/share/prey06/base`), the disk image is also compared with every file of the retail game. On CI it is only compared with the excluded files of `base/`.

Everything is built in `build-release/macos`, which git ignores:

1. SDL2 and OpenAL Soft from `neo/libs`, built for macOS 11 (`MIN_MACOS`). The Homebrew libraries can't be used: they are built for the macOS version of the build machine, and Homebrew's SDL2 is sdl2-compat, which needs SDL3.
2. The engine, the dedicated server and the game library, with `OUTPUT_FOLDER=build-release/macos/output`, so `output/macosx` isn't touched.
3. `Prey2006.app`:
   - `Contents/MacOS/Prey2006` is `launcher.sh`, the main executable. It checks the game data, runs `install_assets.sh` if `pak007.pk4` is missing or outdated, and starts `prey06`.
   - `Contents/MacOS/prey06`, `prey06ded` and `gamearm64.dylib`.
   - `Contents/Frameworks`: SDL2 and OpenAL Soft. The rpaths to the build directories are removed.
   - `Contents/Resources`: the pak007 payload (`pak007.py payload`), `install_assets.sh`, the icon (drawn by `make_icon.swift`) and the licenses.
4. Ad-hoc signing and `tests/test_app.py`. The app isn't notarized, because that needs a paid Apple Developer account, so players have to allow it once (see `ReadMe.txt`).
5. The disk image with the app, a link to Applications, `Read Me.txt` (`ReadMe.txt`) and the licenses. `pak007.py verify` checks every file first, including the files inside archives.

## pak007.pk4 without retail files

`base/` (packed into `pak007.pk4` by the CMake build) contains three kinds of files:

| Kind | Examples | Manifest | In the release |
|---|---|---|---|
| own files | `guis/anchors.guifragment`, `masterservers.lst` | `copy` | shipped as they are |
| modified retail files | `guis/*.gui`, `guis/**/*.guifragment`, `materials/gfx.mtr`, `materials/video.mtr` | `patch` | only a BSDIFF40 patch against the retail file |
| retail artwork and others | hi-res loading screen, intro videos, tutorial maps (Prey SDK), material editor files | `exclude` | never |

The console textures `textures/gfx/console1.tga` and `console2.tga` are of unclear origin. The release uses our own ones from `assets/` instead.

`pak007.py patches` matches lines and ignores whitespace, because the retail files have CRLF line endings and `base/` has LF. Matching bytes would turn every line into a change, and the patch would contain the whole retail file (the tests check for this). Each patch is checked with the system's `bspatch`. `patches/patches.list` records the md5 of the retail file and of the result.

On the player's Mac, `install_assets.sh` takes each original file from the retail pk4s, checks its md5, applies the patch, and packs everything into `~/.local/share/prey06/base/pak007.pk4`. It only uses tools that come with macOS (`unzip`, `bspatch`, `zip`, `md5`). If a file of the player's copy differs (another version of the game), that file is skipped and the game uses its original. The engine gives `pak007.pk4` precedence over the retail pk4s, whatever directory it is in.

## Local setup with the excluded files

To get the same layout as a player, and still have the excluded files (hi-res loading screen, intro videos, tutorial maps, ...):

```bash
python3 release/macos/pak007.py extras ~/.local/share/prey06/base/zz_prey2006_extras.pk4
```

The name sorts after the retail pk4s, so its files override the retail ones (for example the loading screen). `default.cfg` is left out: it is an empty placeholder that would replace the key bindings of the game.

## Other platforms

The workflows for Linux, Windows and FreeBSD come from the original repository. They don't upload `pak007.pk4` as a CI artifact, because it contains files of the retail game, so their builds use the original HUD and menus.
