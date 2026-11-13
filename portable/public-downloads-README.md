<p align="center"><img src="logo.png" width="88" height="88" alt="Laser Forge logo" /></p>

# Laser Forge downloads

Design, preview and run laser jobs in your browser, with an offline portable launcher.
This repository hosts packaged apps and update releases. The development repository remains private.

## Downloads

[View all public releases and downloads](https://github.com/gnomecatstudios/laserforge-downloads/releases).

| Platform | Portable ZIP | Installer |
| --- | --- | --- |
| Windows x64 | [Download](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-windows-x64.zip) | Extract and run |
| Linux x64 | [Download](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-linux-x64.zip) | [Debian / Ubuntu](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Setup-linux-x64.deb) |
| Raspberry Pi / Linux ARM64 | [Download](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-raspberry-pi-arm64.zip) | [Debian / Pi OS](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Setup-raspberry-pi-arm64.deb) |
| Raspberry Pi / Linux ARM32 | [Download](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-raspberry-pi-arm32.zip) | [Debian / Pi OS](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Setup-raspberry-pi-arm32.deb) |

[SHA-256 checksums](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/SHA256SUMS.txt)

## Installation

Install desktop Chrome or Edge first for USB machine control. A browser is not bundled.
Download the package for your operating system and processor, then extract the entire ZIP.

- **Windows:** open `LaserForge-Portable.exe` in the extracted folder.
- **Linux:** run `chmod +x LaserForge-Portable`, then `./LaserForge-Portable` in the extracted folder. For a menu shortcut, run `python3 setup.py --cli`. The optional graphical setup requires Tkinter.
- **Raspberry Pi:** use a desktop Pi OS with Chromium installed. Run `uname -m`: choose ARM64 for `aarch64`, ARM32 for `armv7l` or `armv6l`. Then follow the Linux steps.
- **Debian / Ubuntu / Pi OS installer:** open the `.deb` in your package installer, or run `sudo apt install ./LaserForge-Setup-<platform>.deb`, substituting the downloaded filename. Open **Laser Forge** from the application menu.

Keep the launcher window open while using the app. It serves only on this computer at
<http://127.0.0.1:5190/>. If your default browser is incompatible, open that address in Chrome or Edge.
Ctrl+C in the launcher window stops it.

## Updates

Version 0.2.1 and later check for updates at startup when online. An **Update available** popup
appears after the laser is disconnected. Choose **Download update** or **Later**.
You can also use **About → Check for updates**, or **Check for updates** in the project menu.
Checks contact GitHub without an account or token; projects and machine data are not sent.
Offline use continues normally.

Older versions need one manual download from this page to get the popup.
Save your `.olaser` project and export machine profiles before upgrading. Close the app and launcher,
extract the new ZIP into a new folder, and start its launcher. Linux shortcut installations can run
the new `setup.py --cli` again; Debian users can install the newer `.deb` through the package manager.
Nothing installs or restarts automatically. If the browser offers a separate Reload update, use it
after disconnecting the laser to load the newly installed app.

Autosaves remain in the same browser profile at the same local address. Keep backups before clearing
browser data. Bundled fonts are in `Fonts/`; import `Geist-500.ttf` for offline text outlines.
Other Google Fonts need an initial download.

## Credits

Laser Forge is a fork of [openlaser by Anam Ahmed](https://github.com/theanam/openlaser.app), under the MIT license.
Packages include the app license and the bundled font's OFL license. Windows and Raspberry Pi
builds are cross-compiled; they still need native testing. Physical laser hardware has not been tested.
