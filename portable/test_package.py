import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import json
import zipfile

spec = importlib.util.spec_from_file_location('build_portable', Path(__file__).resolve().parents[1] / 'scripts/build-portable.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


@unittest.skipUnless(shutil.which('dpkg-deb'), 'Debian packaging tools required')
class DebianPackageTests(unittest.TestCase):
    def test_package_architecture_shortcut_and_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = root / 'app'
            app.mkdir()
            (app / 'LaserForge-Portable').write_bytes(b'launcher fixture')
            (app / 'icon.png').write_bytes(b'icon')
            output = root / 'output'
            output.mkdir()
            build.package_deb(app, 'raspberry-pi-arm64', 'arm64', '0.1.0+test', output)
            package = output / 'LaserForge-Setup-raspberry-pi-arm64.deb'
            architecture = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Architecture'], text=True).strip()
            self.assertEqual(architecture, 'arm64')
            extracted = root / 'extracted'
            subprocess.run(['dpkg-deb', '-x', str(package), str(extracted)], check=True)
            binary = extracted / 'usr/lib/laserforge/LaserForge-Portable'
            self.assertEqual(binary.stat().st_mode & 0o777, 0o755)
            for name in ['usr', 'usr/lib', 'usr/lib/laserforge', 'usr/share/applications']:
                self.assertEqual((extracted / name).stat().st_mode & 0o777, 0o755)
            desktop = extracted / 'usr/share/applications/laserforge.desktop'
            self.assertIn('Exec=/usr/lib/laserforge/LaserForge-Portable', desktop.read_text())
            self.assertIn('Icon=/usr/lib/laserforge/icon.png', desktop.read_text())
            self.assertEqual((extracted / 'usr/lib/laserforge/icon.png').read_bytes(), b'icon')


class UpdaterPackagingTests(unittest.TestCase):
    def test_supported_archives_include_updater_and_release_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'dist').mkdir()
            (root / 'dist/index.html').write_text('app')
            (root / 'public').mkdir()
            for name in ['icon-192.png', 'favicon.ico', 'laserforge.icns']:
                (root / 'public' / name).write_bytes(b'icon fixture')
            (root / 'portable').mkdir()
            for name in ['update.py', 'setup.py', 'Start-LaserForge.cmd']:
                shutil.copy2(Path(__file__).with_name(name), root / 'portable' / name)
            (root / 'portable/launcher').mkdir(exist_ok=True)
            for name in ['main.go', 'go.mod']:
                (root / 'portable/launcher' / name).write_text('build fixture')
            for name in ['README.txt', 'LICENSE-LaserForge.txt']:
                (root / 'portable' / name).write_text(name)
            (root / 'portable/Fonts').mkdir(exist_ok=True)
            (root / 'portable/Fonts/font.ttf').write_bytes(b'font')
            def compiler(command, **kwargs):
                Path(command[command.index('-o') + 1]).write_bytes(b'compiled fixture')
            output = root / 'output'
            with patch.object(build, 'ROOT', root), patch.object(build, 'embed_windows_icon'), \
                    patch.object(build, 'package_deb'), patch.object(build.subprocess, 'run', side_effect=compiler), \
                    patch('sys.argv', ['build-portable.py', '--revision', 'test', '--output', str(output)]):
                build.main()
            self.assertEqual(len(build.TARGETS), 4)
            for platform, system, _, _ in build.TARGETS:
                with zipfile.ZipFile(output / f'LaserForge-Portable-{platform}.zip') as package:
                    prefix = 'LaserForge-Portable/'
                    self.assertIn(prefix + 'update.py', package.namelist())
                    self.assertEqual(json.loads(package.read(prefix + 'release.json')),
                                     {'platform': platform, 'version': build.APP_VERSION})
                    entry = 'Start-LaserForge.cmd' if system == 'windows' else 'setup.py'
                    self.assertIn(prefix + entry, package.namelist())


@unittest.skipUnless(sys.platform == 'darwin', 'macOS app bundle packaging is no longer maintained in CI')
class MacApplicationTests(unittest.TestCase):
    def test_finder_bundle_keeps_cli_and_uses_brand_icon(self):
        with tempfile.TemporaryDirectory(prefix='laser forge ') as folder:
            app = Path(folder) / 'LaserForge-Portable'
            app.mkdir()
            (app / 'LaserForge-Portable').write_bytes(b'original launcher')
            (app / 'LaserForge-Portable').chmod(0o755)
            build.package_macos(app)
            contents = app / 'Laser Forge.app/Contents'
            metadata = plistlib.loads((contents / 'Info.plist').read_bytes())
            self.assertEqual(metadata['CFBundleIconFile'], 'LaserForge.icns')
            self.assertEqual(metadata['CFBundleExecutable'], 'launch')
            self.assertEqual((contents / 'Resources/LaserForge.icns').read_bytes(),
                             (build.ROOT / 'public/laserforge.icns').read_bytes())
            self.assertEqual((contents / 'Resources/LaserForge-Portable').read_bytes(), b'original launcher')
            self.assertEqual((contents / 'MacOS/launch').stat().st_mode & 0o777, 0o755)
            subprocess.run(['sh', '-n', str(contents / 'MacOS/launch')], check=True)
            subprocess.run(['sh', '-n', str(app / 'LaserForge-Portable')], check=True)


if __name__ == '__main__':
    unittest.main()
