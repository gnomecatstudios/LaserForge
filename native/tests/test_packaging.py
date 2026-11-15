"""Prevent unsupported/mislabeled native packages, without building foreign binaries."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("laserforge_native_builder", Path(__file__).resolve().parents[2] / "scripts/build-native.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PackagingTargetTests(unittest.TestCase):
    def test_windows_and_linux_x64_userspace(self):
        self.assertEqual(builder.target_id("win32", "AMD64", 64), "windows-x64")
        self.assertEqual(builder.target_id("linux", "x86_64", 64), "linux-x64")

    def test_pi_64_bit_userspace(self):
        self.assertEqual(builder.target_id("linux", "aarch64", 64), "linux-arm64")
        self.assertEqual(builder.target_id("linux", "arm64", 64), "linux-arm64")

    def test_32_bit_pi_userspace_on_64_bit_kernel_is_not_mislabeled(self):
        for machine in ("aarch64", "armv7l", "armv6l"):
            with self.assertRaisesRegex(ValueError, "ARM32 browser package"):
                builder.target_id("linux", machine, 32)

    def test_unrequested_platforms_rejected(self):
        with self.assertRaisesRegex(ValueError, "macOS is not a LaserForge target"):
            builder.target_id("darwin", "arm64", 64)
        for system, machine in (("win32", "arm64"), ("freebsd", "x86_64"), ("linux", "riscv64")):
            with self.assertRaisesRegex(ValueError, "No native packaging recipe"):
                builder.target_id(system, machine, 64)
