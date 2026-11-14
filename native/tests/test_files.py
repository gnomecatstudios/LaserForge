import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from laserforge_native.files import atomic_write, read_project


class FileTests(unittest.TestCase):
    def test_atomic_replace_and_preserve_on_failure(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "project.olaser"
            atomic_write(path, b"original")
            with patch("laserforge_native.files.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    atomic_write(path, b"replacement")
            self.assertEqual(read_project(path), b"original")
            self.assertEqual(list(Path(root).iterdir()), [path])
            atomic_write(path, b"new")
            self.assertEqual(read_project(path), b"new")
