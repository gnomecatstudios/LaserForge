<p align="center"><img src="../public/mark.png" width="88" height="88" alt="Laser Forge logo" /></p>

# LaserForge Portable Offline

Download a ZIP, extract it, and run the launcher. No Node.js, Python, installer,
or internet connection is needed to launch. Desktop Chrome or Edge must already
be installed for USB machine control. The browser is not bundled.

| System | Download |
| --- | --- |
| Windows x64 | [Portable ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-windows-x64.zip) |
| Linux x64 | [Portable ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-linux-x64.zip) |
| Raspberry Pi OS 64-bit (ARM64) | [Portable ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-raspberry-pi-arm64.zip) |
| Raspberry Pi OS 32-bit (ARMv6+) | [Portable ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-raspberry-pi-arm32.zip) |

[SHA-256 checksums](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/SHA256SUMS.txt)

For Raspberry Pi setup and architecture selection, see [Raspberry Pi](raspberry-pi.md).

On Windows, double-click `LaserForge-Portable.exe`; the executable carries the Laser Forge icon. On Linux, run `./LaserForge-Portable` in Terminal; `chmod +x LaserForge-Portable` may be needed.
Keep the launcher window open. It serves embedded app files only on
<http://127.0.0.1:5190/> and opens your default browser. Use Chrome or Edge
manually if your default browser does not support machine connections.
Press Ctrl+C in the launcher window to stop.

## Easy setup on Raspberry Pi and Linux

For Raspberry Pi OS 64-bit (`uname -m` reports `aarch64`), download
[LaserForge Setup for Raspberry Pi ARM64](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Setup-raspberry-pi-arm64.deb).
For 32-bit Pi OS, use [ARM32 setup](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Setup-raspberry-pi-arm32.deb).
For an Intel/AMD Linux desktop, use [Linux x64 setup](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Setup-linux-x64.deb).

Open the `.deb` in your system's package installer and choose Install. It installs
the app and adds **Laser Forge** to the application menu. Your desktop must have a
package-installer application configured; if double-clicking opens an archive
viewer, use Open With → your package installer. On systems without a graphical
package installer, run `sudo apt install ./LaserForge-Setup-raspberry-pi-arm64.deb`
from the download folder (substitute your package name). A desktop and a compatible
browser must already be installed. The launcher window stays open while the app runs.

The Linux portable ZIPs also include `setup.py`. Open it with Python 3 to use the
setup dialog, or run `python3 setup.py --cli` from the extracted folder. It checks
the processor architecture, installs under `~/.local/share/laserforge`, makes the
launcher executable, and creates menu and desktop shortcuts. It needs no administrator
access. The dialog requires Python's Tkinter support; the CLI uses Python's standard
library only. A desktop shortcut may require **Allow Launching** on first use.

To remove a Python setup installation, delete `~/.local/share/laserforge`,
`~/.local/share/applications/laserforge.desktop`, and the **Laser Forge.desktop**
shortcut. Remove a Debian installation through the system package manager.

## Updates

Portable builds from version 0.2.1 check the public [downloads repository](https://github.com/gnomecatstudios/LaserForgeDownloads) on startup. **About → Check for updates** and the project menu offer a manual check. The popup waits until the laser is disconnected. Choose **Download update** or **Later**; nothing installs or restarts automatically.

Older versions need one manual download. Save your project, close the app and launcher, then extract the new ZIP into a new folder. Run its launcher, or rerun the new Linux setup for shortcuts. Debian installations can upgrade using the newer `.deb`. Keep the same browser profile and local address to retain autosaves. Export projects and profiles as backups.

## Branding and icons

The app, browser tab, installable web app, Windows executable, Linux and Raspberry Pi shortcuts, and setup window use the same gear-and-lightning logo. Each portable package includes `icon.png` and `LaserForge.ico`. These assets come from `public/logo-source.png`; `pnpm icons` generates the shared browser icons and Windows icon container.

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

The script cross-compiles all four platform ZIPs, builds three Debian installers using
`dpkg-deb`, and refreshes SHA-256 checksums. Use `--target raspberry-pi-arm64`
to build only that target. Set `--go /path/to/go` to choose the compiler.

For manual cross compilation, add `GOOS` and `GOARCH` before `go build`:
`windows/amd64` (use an `.exe` output name), `linux/amd64`, `linux/arm64`,
`linux/arm` (also set `GOARM=6`).
`launcher/dist/` is generated and excluded from Git.
Include this README, the app license, and the Fonts folder when distributing.

## Validation

The refreshed Linux ZIP was extracted, installed with Python setup into an isolated
user-data directory, and launched. Its browser-open request was verified. In fresh
Chromium with external requests blocked, the bundled app created a rectangle and
opened its four nodes on double-click without page errors. Installer tests cover
architecture mismatch, permissions, shortcuts, fonts, reinstall and Debian layout.
Run them with `python3 -m unittest discover -s portable -p 'test_*.py'`.

The new Raspberry Pi Debian packages are cross-compiled; package architecture and
permissions are checked here. They still need an installation test on actual Pi OS.

The Linux launcher was run in Chromium with all non-loopback requests blocked
and a fresh browser profile. The app loaded, created a project, and connected
to the virtual machine in Idle state without page errors. Update checks contact GitHub when online; an offline check does not block the app.
Windows executables were cross-compiled and their executable formats
checked; they have not been run on Windows. Physical laser
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

The first command validates the packages without publishing. The second requires authenticated GitHub CLI access and creates a public release with four native ZIPs, three Debian installers, and their checksums. It excludes the source ZIP and uploads only the public downloads README, logo and license to the downloads repository. It leaves the source repository private.
