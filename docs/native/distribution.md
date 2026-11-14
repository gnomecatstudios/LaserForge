# Experimental native development and distribution

The Qt application is an additive migration target. The existing browser/PWA and
Go portable packages remain the feature-complete distribution. Native builds
must not replace them until the migration parity and release gates pass.

## Development

Use Python 3.11 or newer (3.12 in CI), Node.js 24, and the repository's pinned
pnpm version. Qt Widgets is provided by PySide6 6.8.3. No QtWebEngine is used.

```sh
python3 -m venv .venv-native
# Linux/macOS:
. .venv-native/bin/activate
# Windows PowerShell instead: .venv-native\Scripts\Activate.ps1
python -m pip install -r native/requirements-build.txt
python -m pip install -e native --no-deps
corepack pnpm install --frozen-lockfile
corepack pnpm exec vite build --config native/bridge/vite.config.ts
python -m laserforge_native
```

The headless Node process runs the retained TypeScript core through a bounded
JSON protocol. It renders no UI. Development resolves Node using
`LASERFORGE_NODE`, a bundled `runtime/node` (`node.exe` on Windows), or PATH.
Keep Node and the bridge build current after changes to libopenlaser.

Run automated validation without a physical laser:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s native/tests -p 'test_*.py'
QT_QPA_PLATFORM=offscreen python -m laserforge_native --smoke-test
```

In PowerShell set `$env:QT_QPA_PLATFORM = 'offscreen'` before running Python.
A smoke pass covers startup and a rendered scene; it does not establish feature
parity or certify a platform for machine operation.

## Build on each target OS

```sh
python scripts/build-native.py
# If bridge is already built:
python scripts/build-native.py --skip-bridge-build
```

The build uses PyInstaller onedir, with shared Qt libraries, Python runtime,
Node executable, bundled bridge, original red logo, application/library licenses,
Qt/PySide/Shiboken and JavaScript dependency license notices. No development
Python or Node installation should be required to launch the resulting package.
A SHA-256 file accompanies every archive. The build fails if it finds any
QtWebEngine dependency.

`--node PATH` chooses the Node executable to package. `--node-license PATH`
provides its complete matching license; otherwise the build tries adjacent
license files and then the exact Node release's upstream LICENSE over HTTPS.
Keep the included `notices/` tree with the package and review it before release.

The version comes from the root package.json; package names include it:

| Target | Recipe output | Validation requirement |
| --- | --- | --- |
| Windows x64 | `LaserForge-Native-windows-x64-v0.2.5.zip` | Build and smoke on Windows; check dialogs, DPI, icon, safe simulated jobs |
| Linux x64 | `LaserForge-Native-linux-x64-v0.2.5.tar.gz` | Build on Ubuntu 22.04; verify Ubuntu/Mint display and runtime dependencies |
| macOS Intel | `LaserForge-Native-macos-x64-v0.2.5.zip` containing LaserForge.app | Build and smoke on Intel macOS; signing and notarization before public release |
| macOS Apple Silicon | `LaserForge-Native-macos-arm64-v0.2.5.zip` containing LaserForge.app | Build and smoke on ARM macOS; signing and notarization before public release |

These are build recipes and experimental artifacts, not a statement that all
platforms have passed validation. See the migration validation record for actual
executed checks. macOS is explicitly requested for this migration, superseding
the legacy AGENTS.md platform preference for this additive target.

PyInstaller does not cross-compile. Windows/macOS artifacts must be built on their
own OS. Intel and ARM macOS packages are separate; no universal binary is claimed.
The native CI workflow builds each matrix target and smokes the packaged binary;
it uploads artifacts only and never publishes a release. If a hosted runner label
is unavailable, run the recipe on a matching maintained runner before claiming
support. Pi ARM64 remains a future native validation target. PySide6 wheels do
not provide an ARM32 desktop path; retain the existing Pi ARM32 browser package.

### Checks executed in this workspace

On 2026-11-14 the Linux x64 recipe completed with Python 3.12.14, PySide6 6.8.3,
Node 24.22.1 and PyInstaller 6.22.3. The generated tar.gz passed gzip integrity
verification. After extraction, its executable completed `--smoke-test` with
`PATH=/nonexistent` and `LASERFORGE_NODE` unset, using its bundled runtime. Required
branding/bridge/runtime/license files were verified and no QtWebEngine files
were present. The offscreen plugin emitted only its expected size-hint warning.

This host uses glibc 2.41. That build does not establish compatibility with older
Ubuntu or Mint releases; build on the oldest supported Linux baseline and test
there before distributing. Windows/macOS recipes and the newly added CI matrix
have not been executed from this workspace. AppImage and signing remain pending.

## Linux integration and troubleshooting

Linux builds depend on the host graphics stack even when Qt libraries are
bundled. For source development and headless CI on Ubuntu/Mint install
`libegl1 libopengl0 libxcb-cursor0 libxkbcommon-x11-0 libdbus-1-3`.
Use `QT_DEBUG_PLUGINS=1` to diagnose platform plugin loading. `offscreen` is for
CI only; use the normal xcb or Wayland platform on the desktop.

An AppImage is not produced yet. The portable tar archive is the current native
Linux recipe. AppImage requires an AppDir, desktop/icon metadata, dependency
closure, and testing on supported distributions; do not rename a tar archive or
claim AppImage support. The supplied `native/packaging/laserforge-native.desktop`
is a template: set Exec to the extracted executable's absolute path and Icon to
the bundled PNG, then install it under `~/.local/share/applications/`.

Future serial adapters will require access to `/dev/ttyUSB*` or `/dev/ttyACM*`.
On Ubuntu/Mint this is commonly granted through the `dialout` group; users must
log out and back in after an administrator adds their account. Do not use broad
world-writable device permissions. Native physical communication is currently
unavailable; simulator validation does not exercise USB/serial permissions.

## macOS signing and notarization

The experimental .app is unsigned. Before distribution, sign nested Node, Qt,
Python libraries and executables with a Developer ID Application identity using
the hardened runtime and minimal required entitlements; sign the application
last. Submit a ZIP/DMG through `xcrun notarytool`, inspect its report, staple the
ticket to the .app, and validate with `codesign --verify --deep --strict` and
`spctl --assess`. Test the signed download on both architectures. Signing,
notarization credentials and macOS runtime checks are not available in this
Linux workspace. Do not recommend disabling Gatekeeper as a distribution path.

## Updates and user data

The native updater is not enabled. The legacy Go/Python updater expects a small
allowlisted browser-launcher ZIP, a fixed loopback server and no Qt dependency
tree; it must never install a native package. Existing browser updates continue
unchanged. Native releases require a distinct artifact/manifest channel,
file-level checksums, staged replacement, rollback and startup health checks,
with full-package fallback. macOS signed bundle updates need platform-aware
replacement; modifying signed files individually would invalidate signatures.

Keep projects, preferences, materials and machine profiles in user-controlled
project locations and application data outside the executable tree. Updating or
replacing experimental archives must not overwrite those files. Until the native
update mechanism is validated, extract new versions into a separate directory and
retain the preceding package for rollback.

## Release gates

Require successful original regression checks; native geometry/serialization and
Qt interaction tests; representative .olaser project round trips; equivalent CAM
output; simulated machine jobs; target-OS executable smoke and visual checks;
brand and dependency-notice review; and comparable rendering measurements.
Physical machines must not be automatically activated during any CI check.
