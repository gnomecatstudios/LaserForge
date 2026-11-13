#!/usr/bin/env python3
"""Install the Linux portable app for the current user; no administrator access needed."""
import argparse
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys


def desktop_quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'


def install(source, data_home, desktop=None, machine=None):
    source, data_home = Path(source), Path(data_home)
    binary = source / 'LaserForge-Portable'
    machine = machine or platform.machine()
    expected = {'x86_64': 62, 'amd64': 62, 'aarch64': 183, 'arm64': 183, 'armv7l': 40, 'armv6l': 40}.get(machine.lower())
    with binary.open('rb') as stream:
        header = stream.read(20)
    if header[:4] != b'\x7fELF' or len(header) < 20 or header[5] != 1:
        raise ValueError('This setup needs a Linux portable package.')
    if expected is None or struct.unpack_from('<H', header, 18)[0] != expected:
        raise ValueError(f'This download does not match your {machine} computer. Download the matching Raspberry Pi or Linux package.')
    target = data_home / 'laserforge'
    target.mkdir(parents=True, exist_ok=True)
    # Rename a fresh file over the old binary so updating a running app is supported.
    staged = target / 'LaserForge-Portable.new'
    shutil.copy2(binary, staged)
    staged.chmod(0o755)
    staged.replace(target / binary.name)
    for name in ['Fonts', 'README.txt', 'LICENSE-LaserForge.txt', 'icon.png']:
        entry = source / name
        if entry.is_dir():
            shutil.copytree(entry, target / name, dirs_exist_ok=True)
        elif entry.is_file():
            shutil.copy2(entry, target / name)
    shortcut = '\n'.join([
        '[Desktop Entry]', 'Type=Application', 'Name=Laser Forge',
        'Comment=Design and run laser jobs offline',
        'Exec=' + desktop_quote(target / binary.name),
        'Icon=' + str(target / 'icon.png'), 'Terminal=true',
        'Categories=Graphics;Engineering;', 'StartupNotify=false', '',
    ])
    applications = data_home / 'applications'
    applications.mkdir(parents=True, exist_ok=True)
    (applications / 'laserforge.desktop').write_text(shortcut)
    if desktop and Path(desktop).is_dir():
        shortcut_file = Path(desktop) / 'Laser Forge.desktop'
        shortcut_file.write_text(shortcut)
        shortcut_file.chmod(0o755)
    return target


def desktop_directory():
    try:
        result = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True, check=True)
        candidate = Path(result.stdout.strip())
        if candidate.is_absolute() and candidate != Path.home():
            return candidate
    except (OSError, subprocess.CalledProcessError):
        pass
    return Path.home() / 'Desktop'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', action='store_true', help='install without a graphical dialog')
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        print('This setup is for Linux and Raspberry Pi OS.', file=sys.stderr)
        return 1
    root = None
    if not args.cli:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.title('Laser Forge Setup')
            logo = tk.PhotoImage(file=str(Path(__file__).resolve().parent / 'icon.png'))
            root.iconphoto(True, logo)
            root.withdraw()
            if not messagebox.askyesno('Install Laser Forge', 'Install Laser Forge for your user and add menu and desktop shortcuts?', parent=root):
                root.destroy()
                return 0
        except Exception as error:
            # A headless or minimal Pi can still use the explicitly selected CLI mode.
            print(f'Cannot open setup window: {error}. Run setup.py --cli from Terminal.', file=sys.stderr)
            return 1
    try:
        target = install(Path(__file__).resolve().parent,
                         Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')),
                         desktop_directory())
        text = f'Installed in {target}. Open Laser Forge from the application menu or desktop shortcut. Keep its launcher window open. Your desktop may ask you to allow launching the shortcut the first time.'
        if root:
            messagebox.showinfo('Laser Forge installed', text)
        else:
            print(text)
        return 0
    except (OSError, ValueError) as error:
        if root:
            messagebox.showerror('Setup failed', str(error))
        else:
            print(f'Setup failed: {error}', file=sys.stderr)
        return 1
    finally:
        if root:
            root.destroy()


if __name__ == '__main__':
    sys.exit(main())
