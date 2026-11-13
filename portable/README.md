<p align="center"><img src="../public/mark.png" width="88" height="88" alt="Laser Forge logo" /></p>

# LaserForge Portable Offline

Download a ZIP, extract it, and run the launcher. No Node.js, Python, installer,
or internet connection is needed to launch. Desktop Chrome or Edge must already
be installed for USB machine control. The browser is not bundled.

| System | Download |
| --- | --- |
| Windows x64 | [Portable ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-windows-x64.zip) |
| Linux x64 | [Portable ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-linux-x64.zip) |
| Raspberry Pi OS 64-bit (ARM64) | [Portable ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-RPi-ARM64.zip) |
| Raspberry Pi OS 32-bit (ARMv6+) | [Portable ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-RPi-ARM32.zip) |

[SHA-256 checksums](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/SHA256SUMS.txt)

For Raspberry Pi setup and architecture selection, see [Raspberry Pi](raspberry-pi.md).

On Windows, double-click `LaserForge-Portable.exe`; the executable carries the Laser Forge icon. On Linux, run `./LaserForge-Portable` in Terminal; `chmod +x LaserForge-Portable` may be needed.
Keep the launcher window open. It serves embedded app files only on
<http://127.0.0.1:5190/> and opens your default browser. Use Chrome or Edge
manually if your default browser does not support machine connections.
Press Ctrl+C in the launcher window to stop.

## Easy setup on Raspberry Pi and Linux

The Linux portable ZIPs include `setup.py`. Open it with Python 3 to use the
setup dialog, or run `python3 setup.py --cli` from the extracted folder. It checks
the processor architecture, installs under `~/.local/share/laserforge`, makes the
launcher executable, and creates menu and desktop shortcuts. It needs no administrator
access. The dialog requires Python's Tkinter support; the CLI uses Python's standard
library only. A desktop shortcut may require **Allow Launching** on first use.

To remove a Python setup installation, delete `~/.local/share/laserforge`,
`~/.local/share/applications/laserforge.desktop`, and the **Laser Forge.desktop**
shortcut.

## Updates

Python 3.9 or newer enables background update downloads on Windows x64, Linux
x64 and Raspberry Pi OS ARM64/ARM32. macOS is no longer a release target.

- **Pi/Linux Python setup:** run the new package's `setup.py` once. Its menu and
  desktop shortcuts then use `python3 update.py --launch`.
- **Windows:** install Python 3.9+ with its `py` launcher, then open
  `Start-LaserForge.cmd` instead of the native executable.
- **Other portable folders:** run `python3 update.py --launch` from the extracted
  folder (`py -3 update.py --launch` on Windows).

The helper starts Laser Forge immediately and checks the public downloads
repository in a background thread. New stable releases for the installed platform
are downloaded and checked against that release's SHA-256 checksums. They are
staged without changing the running app. Close the app and launcher after saving
your projects and disconnecting the laser; the staged release installs before the
next launch. Keep the same browser profile and local address for autosaves.
The helper does not stop a laser, close the browser or restart a running launcher.

The next launch revalidates the staged release online before applying it. If
GitHub is unavailable, it starts the installed version and leaves the update for
later. If a newer release has replaced the staged one, a fresh background download
is needed. Installation write failures restore replaced files; sudden power loss
or a failed rollback can still require manually reinstalling the portable package.
Projects and browser settings are outside the files the updater replaces.
Checksums verify download integrity, not a publisher signature: this trusts the
public downloads repository and HTTPS. Release signing is not implemented.

Commands for manual use:

Opening `update.py` without arguments launches the app with background updates,
just like `python3 update.py --launch` (or `py -3 update.py --launch` on Windows).
Run it from an extracted portable package containing `release.json` and the native
launcher.

```sh
python3 update.py --check
python3 update.py --download
# Save projects, disconnect the laser and close the launcher first:
python3 update.py --apply
```

Running the native executable directly keeps the existing manual-update behavior.
**About → Check for updates** remains a manual download option. The Python helper refuses system installation paths. It does not request administrator access.

Existing users need one manual download/install of a release containing the new
helper and `release.json`. Existing packages cannot gain this feature remotely.

## Branding and icons

The app, browser tab, installable web app, Windows executable, Linux and Raspberry Pi shortcuts, and setup window use the same gear-and-lightning logo. Each portable package includes `icon.png` and `LaserForge.ico`. These assets come from `public/logo-source.png`.

## Offline fonts and project storage

The interface fonts and app assets are included. For offline text outlines,
import `Fonts/Geist-500.ttf` through the font picker, or import your own font.
Other Google Fonts need an initial download. Font licensing is in `Fonts/OFL.txt`.
Documentation links and USB driver downloads need internet.

Browser autosaves stay in the browser profile on each computer. Save `.olaser`
projects and export machine profiles to carry them to another computer. Saves
from the public website do not automatically appear at the local address.

## Build the launcher

The package's `VERSION.txt` records its source revision. New packages include
node drawing, Unite and double-click node editing. Rebuilding from a newer checkout
includes that checkout's app instead. Building requires internet for dependencies
and the repository's Node.js/pnpm setup, plus Go 1.24 or later. Windows icon embedding uses the pinned `github.com/akavel/rsrc@v0.10.2` build tool.

From the repository root, on a POSIX shell:

```sh
pnpm install --frozen-lockfile
pnpm exec playwright install chromium
pnpm icons
pnpm build
python3 scripts/build-portable.py
```

The script cross-compiles all four supported ZIPs and refreshes SHA-256 checksums. Use `--target raspberry-pi-arm64`
to build only that target. Set `--go /path/to/go` to choose the compiler.

For manual cross compilation, add `GOOS` and `GOARCH` before `go build`:
`windows/amd64` (use an `.exe` output name), `linux/amd64`, `linux/arm64`,
`linux/arm` (also set `GOARM=6`).
`launcher/dist/` is generated and excluded from Git.
Include this README, the app license, and the Fonts folder when distributing.

## Validation

Every native build verifies that its executable embeds every production web asset,
including the complete editor, text/layout tools, machine controls, workers, fonts
and WebAssembly. Windows uses the same app payload as Linux and Raspberry Pi.
The build also checks offline font and updater companions. Run the check separately
with `python3 scripts/verify-portable-parity.py` after `pnpm build`.
Branding is checked with `python3 scripts/verify-portable-branding.py`, including
the Windows executable icon and embedded web logo.

The refreshed Linux ZIP was extracted, installed with Python setup into an isolated
user-data directory, and launched. Its browser-open request was verified. In fresh
Chromium with external requests blocked, the bundled app created a rectangle and
opened its four nodes on double-click without page errors. Installer tests cover
architecture mismatch, permissions, shortcuts, fonts, and reinstall.
Run them with `python3 -m unittest discover -s portable -p 'test_*.py'`.

The Linux launcher was run in Chromium with all non-loopback requests blocked
and a fresh browser profile. The app loaded, created a project, and connected
to the virtual machine in Idle state without page errors. Update checks contact GitHub when online; an offline check does not block the app.
Windows executables were cross-compiled and their executable formats
checked; they have not been run on those operating systems. Physical laser
hardware has not been tested.

The Raspberry Pi ARM64 and ARM32 launchers were cross-compiled and their ELF
architecture headers checked. They have not been run on a Raspberry Pi.

The app and launcher are distributed under the repository's MIT license.

## Publish an update

Bump the app version in `package.json`, run the required checks, build the app, then rebuild all portable packages. The public release must use the same stable version.

```sh
python3 scripts/publish-downloads.py --packages portable/downloads
python3 scripts/publish-downloads.py --packages portable/downloads --publish
```


