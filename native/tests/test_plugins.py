"""Plugin discovery tests never execute third-party code."""

import json
from pathlib import Path
import tempfile
import unittest

from laserforge_native.plugins import (
    CAPABILITIES, PluginError, PluginRegistry, discover_plugins, read_manifest,
)


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def package(self, plugin_id="example.shapes", **patch):
        directory = self.root / plugin_id
        directory.mkdir(exist_ok=True)
        manifest = {
            "manifestVersion": 1, "apiVersion": 1, "id": plugin_id,
            "name": "Example shapes", "version": "1.0.0", "entrypoint": "main.py",
            "capabilities": ["drawing-tools"], "dependencies": {},
        }
        manifest.update(patch)
        (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
        # If this executes, the test must fail. Discovery only examines its path.
        (directory / "main.py").write_text("raise RuntimeError('plugin code ran')\n", encoding="utf-8")
        return directory

    def test_metadata_only_discovery_and_default_disabled(self):
        self.package()
        report = discover_plugins(self.root)
        self.assertEqual(report.issues, ())
        self.assertEqual(len(report.plugins), 1)
        registry = PluginRegistry(report)
        self.assertFalse(registry.is_enabled("example.shapes"))
        registry.set_enabled("example.shapes", True)
        self.assertTrue(registry.is_enabled("example.shapes"))
        self.assertEqual(registry.preferences(), {"example.shapes": True})
        registry.set_enabled("example.shapes", False)
        self.assertFalse(registry.is_enabled("example.shapes"))

    def test_capabilities_exclude_machine_and_hardware(self):
        self.assertFalse({"machine", "hardware", "serial", "usb", "bluetooth"} & CAPABILITIES)
        for name in ("hardware", "serial", "machine", "filesystem", "network"):
            with self.subTest(name=name):
                directory = self.package(capabilities=[name])
                with self.assertRaisesRegex(PluginError, "unsupported capabilities"):
                    read_manifest(directory)

    def test_invalid_manifests_are_isolated(self):
        self.package("good.plugin")
        self.package("bad.plugin", apiVersion=2)
        report = discover_plugins(self.root)
        self.assertEqual([p.id for p in report.plugins], ["good.plugin"])
        self.assertEqual(len(report.issues), 1)
        self.assertIn("apiVersion", report.issues[0].message)

    def test_reject_path_escape_and_nonportable_paths(self):
        for entry in ("../escape.py", "/tmp/plugin.py", "C:/plugin.py", "sub/../../plugin.py",
                      "sub\\plugin.py", "./main.py", "sub//main.py", "main.py/", "main.py\x00"):
            with self.subTest(entry=entry):
                with self.assertRaises(PluginError):
                    read_manifest(self.package(entrypoint=entry))

    def test_reject_symlinks(self):
        directory = self.package()
        (directory / "main.py").unlink()
        external = self.root / "external.py"
        external.write_text("", encoding="utf-8")
        try:
            (directory / "main.py").symlink_to(external)
        except OSError:
            self.skipTest("symbolic links unavailable for this account")
        with self.assertRaisesRegex(PluginError, "symbolic links"):
            read_manifest(directory)
        (directory / "main.py").unlink()
        (directory / "main.py").write_text("", encoding="utf-8")
        (directory / "plugin.json").rename(directory / "real.json")
        (directory / "plugin.json").symlink_to(directory / "real.json")
        with self.assertRaisesRegex(PluginError, "regular file"):
            read_manifest(directory)

    def test_reject_types_duplicates_unknown_fields_and_versions(self):
        for patch in ({"apiVersion": True}, {"manifestVersion": 2}, {"id": "Other"},
                      {"name": ""}, {"version": "1.0"}, {"version": "01.0.0"},
                      {"capabilities": "menus"}, {"capabilities": ["menus", "menus"]},
                      {"dependencies": {"other.plugin": "^1.0.0"}}, {"dependencies": ["thing"]},
                      {"installScript": "run.py"}):
            with self.subTest(patch=patch):
                with self.assertRaises(PluginError):
                    read_manifest(self.package(**patch))
        directory = self.package()
        (directory / "plugin.json").write_text('{"id":"a", "id":"b"}', encoding="utf-8")
        with self.assertRaisesRegex(PluginError, "duplicate manifest key"):
            read_manifest(directory)

    def test_dependency_versions_and_cycles(self):
        self.package("a.plugin", dependencies={"b.plugin": "1.0.0"})
        report = discover_plugins(self.root)
        self.assertEqual(report.plugins, ())
        self.assertIn("missing plugin dependency", report.issues[0].message)
        self.package("b.plugin", version="2.0.0")
        report = discover_plugins(self.root)
        self.assertEqual([p.id for p in report.plugins], ["b.plugin"])
        self.assertIn("requires 1.0.0", report.issues[0].message)
        self.package("b.plugin", dependencies={"a.plugin": "1.0.0"})
        report = discover_plugins(self.root)
        self.assertEqual(report.plugins, ())
        self.assertTrue(all("cycle" in issue.message for issue in report.issues))

    def test_deep_dependency_chain_does_not_recurse(self):
        for index in range(1050):
            dependencies = {f"p{index + 1}": "1.0.0"} if index < 1049 else {}
            self.package(f"p{index}", dependencies=dependencies)
        report = discover_plugins(self.root)
        self.assertEqual(len(report.plugins), 1050)
        self.assertEqual(report.issues, ())

    def test_enablement_dependencies_and_restore(self):
        self.package("a.plugin", dependencies={"b.plugin": "1.0.0"})
        self.package("b.plugin")
        report = discover_plugins(self.root)
        registry = PluginRegistry(report)
        with self.assertRaisesRegex(PluginError, "enable required plugins"):
            registry.set_enabled("a.plugin", True)
        registry.set_enabled("b.plugin", True)
        registry.set_enabled("a.plugin", True)
        restored = PluginRegistry(report, [key for key, value in registry.preferences().items() if value])
        self.assertEqual(registry.preferences(), restored.preferences())
        restored.set_enabled("b.plugin", False)
        self.assertFalse(restored.is_enabled("a.plugin"))
        removed = PluginRegistry(discover_plugins(self.root / "missing"), ["a.plugin"])
        self.assertEqual(removed.preferences(), {})

    def test_oversized_manifest_and_hidden_staging(self):
        directory = self.package()
        (directory / "plugin.json").write_bytes(b" " * (65536 + 1))
        with self.assertRaisesRegex(PluginError, "64 KiB"):
            read_manifest(directory)
        directory.rename(self.root / ".staging")
        self.assertEqual(discover_plugins(self.root).plugins, ())
        self.assertEqual(discover_plugins(self.root).issues, ())


if __name__ == "__main__":
    unittest.main()
