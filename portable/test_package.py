import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

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



class SupportedTargetsTests(unittest.TestCase):
    def test_build_and_publish_platforms_match(self):
        publish_spec = importlib.util.spec_from_file_location('publish_downloads', build.ROOT / 'scripts/publish-downloads.py')
        publish = importlib.util.module_from_spec(publish_spec)
        publish_spec.loader.exec_module(publish)
        self.assertEqual({target[0] for target in build.TARGETS}, set(publish.PLATFORMS))
        self.assertEqual({target[1] for target in build.TARGETS}, {'windows', 'linux'})
        self.assertEqual(len(build.TARGETS), 4)


if __name__ == '__main__':
    unittest.main()
