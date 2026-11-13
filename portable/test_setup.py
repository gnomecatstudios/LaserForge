import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('laserforge_setup', Path(__file__).with_name('setup.py'))
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def fixture(self, root, machine=183):
        source = root / 'download'
        source.mkdir()
        header = bytearray(20)
        header[:4] = b'\x7fELF'
        header[5] = 1
        struct.pack_into('<H', header, 18, machine)
        (source / 'LaserForge-Portable').write_bytes(header)
        (source / 'Fonts').mkdir()
        (source / 'Fonts/font.ttf').write_bytes(b'font')
        (source / 'icon.png').write_bytes(b'icon')
        return source

    def test_installs_arm64_with_executable_shortcuts_and_fonts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = self.fixture(root)
            desktop = root / 'Desktop'
            desktop.mkdir()
            data = root / 'data with spaces'
            target = setup.install(source, data, desktop, 'aarch64')
            self.assertEqual((target / 'LaserForge-Portable').stat().st_mode & 0o777, 0o755)
            self.assertEqual((target / 'Fonts/font.ttf').read_bytes(), b'font')
            self.assertEqual((target / 'icon.png').read_bytes(), b'icon')
            shortcut = (data / 'applications/laserforge.desktop').read_text()
            self.assertIn('Exec="' + str(target / 'LaserForge-Portable') + '"', shortcut)
            self.assertIn('Icon=' + str(target / 'icon.png'), shortcut)
            self.assertEqual((desktop / 'Laser Forge.desktop').read_text(), shortcut)
            setup.install(source, data, desktop, 'aarch64')  # Reinstall safely.

    def test_rejects_x64_download_on_pi_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = self.fixture(root, 62)
            with self.assertRaisesRegex(ValueError, 'does not match'):
                setup.install(source, root / 'data', machine='aarch64')
            self.assertFalse((root / 'data').exists())

    def test_rejects_non_executable_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = self.fixture(root)
            (source / 'LaserForge-Portable').write_bytes(b'not an executable')
            with self.assertRaises(ValueError):
                setup.install(source, root / 'data', machine='aarch64')

    def test_desktop_exec_escapes_shell_characters(self):
        self.assertEqual(setup.desktop_quote('/a/$b%"'), '"/a/\\$b%%\\""')


if __name__ == '__main__':
    unittest.main()
