<p align="center"><img src="../public/mark.png" width="88" height="88" alt="Laser Forge logo" /></p>

# Raspberry Pi portable offline version

Use Raspberry Pi OS **with a desktop and Chromium installed**. The package
includes the app and a local server, but does not include a browser. Raspberry
Pi OS Lite needs a desktop/browser setup to use the app on the Pi itself.

## Choose your download

In a terminal, run `uname -m`:

| Result | Package |
| --- | --- |
| `aarch64` | [ARM64 ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-raspberry-pi-arm64.zip) |
| `armv7l` or `armv6l` | [ARM32 ZIP](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Portable-raspberry-pi-arm32.zip) |

Choose based on your installed operating system, even if the Pi's processor
supports 64-bit. The ARM32 server targets ARMv6 or newer; browser availability
and performance on older Pi models may limit the app's usability.

## Install from the desktop

For `aarch64`, download [ARM64 setup](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Setup-raspberry-pi-arm64.deb).
For `armv7l` or `armv6l`, download [ARM32 setup](https://github.com/gnomecatstudios/LaserForgeDownloads/releases/latest/download/LaserForge-Setup-raspberry-pi-arm32.deb).
Open the `.deb` with your system package installer, install it, and open
**Laser Forge** from the application menu. Keep its launcher window open.
A graphical package installer must be available; otherwise use
`sudo apt install ./LaserForge-Setup-raspberry-pi-arm64.deb` from the download
folder, substituting the correct package name.

Alternatively, the ZIP includes `setup.py`, which installs for your user and
creates menu and desktop shortcuts. Open with Python 3 for the setup dialog,
or run `python3 setup.py --cli` in its folder. The dialog needs Tkinter.

## Start without installing

Extract the ZIP, open a terminal in the extracted `LaserForge-Portable` folder,
then run:

```sh
chmod +x LaserForge-Portable
./LaserForge-Portable
```

Keep the terminal open and open **http://127.0.0.1:5190/** in Chromium.
If the default browser opens something else, paste the address into Chromium.
Stop the launcher with Ctrl+C. There is no Node.js or Python runtime dependency.
The server listens only on this Pi; it does not expose the app over your LAN.

## Connect the laser

Use Chromium's USB/Web Serial connection. If your user cannot access the serial
device, add yourself to the serial-device group, usually `dialout`:

```sh
sudo usermod -aG dialout "$USER"
```

Log out and back in after changing group membership. Linux Bluetooth support
may require Chromium's experimental Web Platform features; the app's Bluetooth
connection help describes the setting.

## Offline text and saves

Import the included `Fonts/Geist-500.ttf` through the font picker for offline
text outlines. Other Google Fonts need a first download. Browser autosaves stay
on this Pi; save `.olaser` files to move projects to another device.

## Validation

Both launchers were cross-compiled from the same launcher and embedded app
used by the existing portable packages. Executable architecture headers and
ZIP integrity/checksums were checked. Raspberry Pi execution, Chromium Web
Serial support, and physical laser connections have not been tested on hardware.

See [the portable README](README.md) for source revision and build instructions.
