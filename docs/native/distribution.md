# Experimental native development and distribution

The Qt application is an additive migration target. The existing browser/PWA and
Go portable packages remain the feature-complete distribution. Native builds
must not replace them until the migration parity and release gates pass.
The requested targets are Windows x64, Linux Mint x64 and Raspberry Pi OS.
Existing Pi ARM64/ARM32 browser packages remain available. macOS is outside the
current scope, consistent with the repository's platform preference.

## Development

Use CPython 3.11–3.13 (3.12 in CI), Node.js 24, and the repository's pinned
pnpm version. The application requires Python 3.11 or newer, while pinned
PySide6 6.8.3 requires Python below 3.14. Qt Widgets is provided by that pinned
PySide6 version. No QtWebEngine is used.

```sh
python3.12 -m venv .venv-native
# Linux Mint / compatible Raspberry Pi OS 64-bit:
. .venv-native/bin/activate
# Windows: create with py -3.12 -m venv .venv-native, then in PowerShell:
# .venv-native\Scripts\Activate.ps1
python -m pip install -r native/requirements-build.txt
python -m pip install -e native --no-deps
corepack pnpm install --frozen-lockfile
corepack pnpm exec vite build --config native/bridge/vite.config.ts
python -m laserforge_native
```

Choose an installed interpreter in the supported range; substitute `python3.13`
on a compatible Pi installation if appropriate. Linux Mint 21's default Python
3.10 cannot run this application. Use a separate Python 3.12 development/build
environment; keep the distribution's system Python intact. Mint 22's default
Python 3.12 satisfies the Python requirement.

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
| Linux Mint x64 | `LaserForge-Native-linux-x64-v0.2.5.tar.gz` | Build on Ubuntu 22.04 with Python 3.12; test on actual Mint 21 and 22 desktops |
| Raspberry Pi OS 64-bit | Experimental source/build path only; potential `LaserForge-Native-linux-arm64-v0.2.5.tar.gz` | Requires compatible ARM64 userspace, glibc and Python; build and test on a Pi before distributing |
| Raspberry Pi OS 32-bit | Existing `LaserForge-Portable-RPi-ARM32-v0.2.5.zip` browser package | Native Qt runtime is blocked by missing ARM32 wheels and the current Node distribution path |

These are build recipes and experimental artifacts, not a statement that all
platforms have passed validation. See the migration validation record for actual
executed checks. Native Windows, Mint and Pi validation is still required; the
Pi table entry does not announce a tested native Pi package.

PyInstaller does not cross-compile. Build Windows on Windows, Linux x64 on a
matching Linux baseline, and Pi ARM64 on a compatible ARM64 system. The native
CI workflow produces experimental artifacts and never publishes a release.
An x64 CI smoke does not validate Mint desktops or Raspberry Pi hardware.

### Linux Mint runtime baselines

| Distribution | Ubuntu base | Default Python | glibc baseline | Native development requirement |
| --- | --- | --- | --- | --- |
| Mint 21.x x64 | Ubuntu 22.04 | 3.10 | 2.35 | Separate CPython 3.11–3.13; build recipe uses 3.12 |
| Mint 22.x x64 | Ubuntu 24.04 | 3.12 | 2.39 | Default Python meets the requirement; validate Qt display dependencies |

The pinned PySide6, Essentials, Addons and Shiboken6 x64 wheels carry
`cp39-abi3-manylinux_2_28_x86_64` tags, so both Mint glibc baselines meet the wheel
floor. This does not establish compatibility for an application frozen on a newer
host. Build the portable x64 application on Ubuntu 22.04 with Python 3.12, then
test the packaged runtime on both Mint versions. The package includes Python,
so Mint 21 users should not need to replace Python to launch a validated bundle.
No native Linux Mint runtime test has been performed in this workspace.

### Raspberry Pi OS constraints and experimental source setup

Official PyPI metadata for all four pinned Qt packages lists
`cp39-abi3-manylinux_2_39_aarch64` as the Linux ARM64 wheel tag, with
`Requires-Python: >=3.9,<3.14`. Combining that with LaserForge's own requirement
means the current wheel-based Pi source path needs all of:

- A 64-bit ARM CPU **and 64-bit ARM64 userspace/Python**; a 64-bit kernel alone
  does not make a 32-bit Raspberry Pi OS installation compatible.
- glibc 2.39 or newer for the pinned PySide6 wheels.
- CPython 3.11–3.13, a virtual environment, recent pip, and an ARM64 Node.js 24
  executable; use the repository's pinned pnpm version.
- A desktop display stack and the Linux Qt runtime libraries listed below.
- Building the retained core bridge before launching, then running the native
  tests, offscreen smoke and actual desktop checks on the Pi.

Raspberry Pi OS based on Debian Bookworm normally has glibc 2.36 and Python
3.11: its Python version meets the application requirement, but its glibc is
below the pinned ARM64 wheel floor. A newer 64-bit installation, such as a
Trixie-based system with glibc 2.41 and Python 3.13, meets these particular
version constraints; **it has not been tested with this application**. Check the
actual installation before attempting the development commands above:

```sh
getconf GNU_LIBC_VERSION
dpkg --print-architecture
python3 -c "import platform, struct, sys; print(platform.machine(), struct.calcsize('P') * 8, sys.version)"
node -p 'process.arch + " " + process.version'
```

After satisfying those prerequisites, use the development commands, run the
native test suite and smoke, and then try `python scripts/build-native.py` on
the ARM64 system. Successful installation of wheels alone is not Pi validation.
Supporting older Pi distributions would require a separately maintained Qt/
PySide build or a reviewed dependency change, followed by full regression tests.

There are no official PySide6 6.8.3 Linux ARM32 wheels. Node.js 24 labels Linux
ARMv7 experimental, and its 24.22.1 release lists ARM64 Linux archives but no
ARM32 Linux archive. The current native runtime therefore has no validated
ARM32 installation or packaging path. Retain both existing Pi browser packages,
`LaserForge-Portable-RPi-ARM64-v0.2.5.zip` and
`LaserForge-Portable-RPi-ARM32-v0.2.5.zip`, while native work continues.

Wheel constraints were checked against the official
[PySide6 6.8.3 metadata](https://pypi.org/pypi/PySide6/6.8.3/json), and the
corresponding Essentials, Addons and Shiboken6 release metadata. Node constraints
were checked against its
[24.22.1 build requirements](https://github.com/nodejs/node/blob/v24.22.1/BUILDING.md)
and [release archive list](https://nodejs.org/dist/v24.22.1/SHASUMS256.txt).

### Checks executed in this workspace

On 2026-11-14 the Linux x64 recipe completed with Python 3.12.14, PySide6 6.8.3,
Node 24.22.1 and PyInstaller 6.22.3. The generated tar.gz passed gzip integrity
verification. After extraction, its executable completed `--smoke-test` with
`PATH=/nonexistent` and `LASERFORGE_NODE` unset, using its bundled runtime. Required
branding/bridge/runtime/license files were verified and no QtWebEngine files
were present. The offscreen plugin emitted only its expected size-hint warning.

This host uses glibc 2.41, newer than both Mint baselines above. The resulting
archive must not be presented as a validated Mint download. Rebuild on the
Ubuntu 22.04 baseline and test on Mint 21/22 before distributing. Windows, Mint
and Pi runtime tests and the newly added CI matrix have not been executed from
this workspace. AppImage and Windows signing remain pending.

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
On Ubuntu/Mint and Raspberry Pi OS this is commonly granted through the `dialout`
group; users must log out and back in after an administrator adds their account. Do not use broad
world-writable device permissions. Native physical communication is currently
unavailable; simulator validation does not exercise USB/serial permissions.

## Updates and user data

The native updater is not enabled. The legacy Go/Python updater expects a small
allowlisted browser-launcher ZIP, a fixed loopback server and no Qt dependency
tree; it must never install a native package. Existing browser updates continue
unchanged. Native releases require a distinct artifact/manifest channel,
file-level checksums, staged replacement, rollback and startup health checks,
with full-package fallback and platform-aware replacement.

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
