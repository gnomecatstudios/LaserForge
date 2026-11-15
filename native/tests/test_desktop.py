"""Real native shell + bundled Node core, with simulated controllers only."""
import os
import base64
from pathlib import Path
import tempfile
import time
import unittest
import json
import zipfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from laserforge_native.bridge import bridge_path
from laserforge_native.window import MainWindow, icon_path


@unittest.skipUnless(bridge_path().is_file(), "Build the native bridge before desktop integration tests")
class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.errors = []
        self.dialog = patch("laserforge_native.window.QMessageBox.warning")
        self.dialog.start()
        self.window = MainWindow(settings=QSettings(str(self.root / "settings.ini"), QSettings.Format.IniFormat))
        self.window.core.failed.connect(lambda method, message: self.errors.append((method, message)))
        self.window.show()
        self.wait(lambda: self.window.snapshot is not None and not self.window.core.pending)

    def tearDown(self):
        QApplication.clipboard().clear()  # Release Qt-owned MIME data before offscreen platform teardown.
        self.window.dirty = False
        self.window.close()
        self.dialog.stop()
        self.temporary.cleanup()
        self.assertEqual(self.errors, [])

    def wait(self, condition, timeout=10):
        deadline = time.monotonic() + timeout
        while not condition():
            if time.monotonic() > deadline:
                self.fail(f"Native operation timed out: pending={self.window.core.pending}, errors={self.errors}")
            QTest.qWait(10)
        self.app.processEvents()

    def settled(self):
        self.wait(lambda: not self.window.core.pending)

    def shape(self, **params):
        self.window.command("createShape", {"kind": "rect", "x": 20, "y": 30, "width": 40, "height": 25, **params})
        self.settled()
        return self.window.snapshot["project"]["objects"][-1]["id"]

    def test_dimension_edit_undo_preview_and_file_round_trip(self):
        object_id = self.shape()
        self.assertEqual(self.window.view.selected_ids(), [object_id])
        self.assertAlmostEqual(self.window.fields["width"].value(), 40)
        self.window.aspect.setChecked(False)
        self.window.fields["width"].setValue(80)
        self.window.change_dimension("width")
        self.settled()
        self.assertAlmostEqual(self.window.view.selection_bounds().width(), 80)
        self.assertAlmostEqual(self.window.view.selection_bounds().height(), 25)
        self.window.actions["undo"].trigger()
        self.settled()
        self.assertAlmostEqual(self.window.view.selection_bounds().width(), 40)
        self.window.actions["preview"].trigger()
        self.settled()
        self.assertTrue(self.window.previewing)
        self.assertIn("lines", self.window.job_info.text())
        self.window.path = self.root / "design.olaser"
        self.window.save_project()
        self.settled()
        saved = self.window.path.read_bytes()
        self.assertEqual(saved[:2], b"PK")
        self.assertFalse(self.window.dirty)
        self.window.new_project()
        self.settled()
        self.assertEqual(self.window.snapshot["project"]["objects"], [])
        self.window.load_path(self.root / "design.olaser")
        self.settled()
        self.assertEqual(self.window.snapshot["project"]["objects"][0]["id"], object_id)
        self.assertFalse(self.window.dirty)
        self.window.simulate()
        self.settled()
        self.assertIn('"simulation": true', self.window.job_info.text())

    def test_pending_edit_marks_dirty_and_text_field_keeps_edit_shortcuts(self):
        object_id = self.shape()
        self.window.dirty = False
        self.window.command("transform", {"ids": [object_id], "matrix": [1, 0, 0, 1, 1, 0]})
        self.assertTrue(self.window.dirty, "Closing while an edit is pending must prompt to save")
        self.settled()
        self.window.layer_name.setFocus()
        self.window.layer_name.selectAll()
        QTest.keyClicks(self.window.layer_name, "New vector layer")
        QTest.keyClick(self.window.layer_name, Qt.Key.Key_Backspace)
        self.assertEqual(len(self.window.snapshot["project"]["objects"]), 1)
        self.assertEqual(self.window.view.selected_ids(), [object_id])
        self.assertEqual(self.window.layer_name.text(), "New vector laye")
        QTest.keyClick(self.window.layer_name, Qt.Key.Key_Enter)
        self.settled()
        self.assertEqual(self.window.snapshot["project"]["layers"][0]["name"], "New vector laye")

    def test_raster_import_decodes_with_qt_and_compiles_using_retained_raster_cam(self):
        path = self.root / "photo.png"
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.fill(QColor("black"))
        image.save(str(path))
        # Qt writes a default 96-DPI pHYs chunk even when resolution is unset.
        # Remove that optional chunk to exercise the original 254-DPI fallback.
        encoded = path.read_bytes()
        without_density = bytearray(encoded[:8])
        offset = 8
        while offset < len(encoded):
            length = int.from_bytes(encoded[offset:offset + 4], "big")
            chunk = encoded[offset:offset + length + 12]
            if chunk[4:8] != b"pHYs":
                without_density.extend(chunk)
            offset += length + 12
        path.write_bytes(without_density)
        with patch("laserforge_native.window.QFileDialog.getOpenFileName", return_value=(str(path), "")):
            self.window.import_art()
        self.settled()
        project = self.window.snapshot["project"]
        obj = project["objects"][0]
        self.assertAlmostEqual(obj["width"], .4)
        self.assertAlmostEqual(obj["height"], .4)
        self.assertEqual(base64.b64decode(project["assets"][obj["assetId"]]["data"]), path.read_bytes())
        layer = next(layer for layer in project["layers"] if layer["id"] == obj["layerId"])
        self.assertEqual(layer["mode"], "image")
        self.assertEqual(len(self.window._compile_params()["rasters"]), 1)
        plans = []
        self.window.core.request("compile", self.window._compile_params(), plans.append)
        self.settled()
        self.assertGreater(plans[0]["stats"]["burnDistance"], 0)
        self.assertTrue(plans[0]["toolpaths"])

    def test_alignment_is_applied_in_bed_coordinates_and_layers_can_move(self):
        first = self.shape()
        second = self.shape(x=100, y=60)
        self.window.view.set_selected([first, second])
        self.window.align("left")
        self.settled()
        self.assertEqual(self.window.view.object_bounds(first).left(), self.window.view.object_bounds(second).left())
        self.window.command("addLayer", {"name": "Engraving", "mode": "fill"})
        self.settled()
        self.window.layer_list.setCurrentRow(1)
        self.window.assign_layer()
        self.settled()
        layer_id = self.window.snapshot["project"]["layers"][1]["id"]
        self.assertTrue(all(obj["layerId"] == layer_id for obj in self.window.snapshot["project"]["objects"]))

    def test_save_flushes_focused_editor_before_serialization_and_stays_clean(self):
        self.shape()
        self.window.layer_name.setFocus()
        self.window.layer_name.selectAll()
        QTest.keyClicks(self.window.layer_name, "Uncommitted name")
        self.window.path = self.root / "focused.olaser"
        self.window.save_project()
        self.settled()
        with zipfile.ZipFile(self.window.path) as archive:
            manifest = json.loads(archive.read("project.json"))
        self.assertEqual(manifest["project"]["layers"][0]["name"], "Uncommitted name")
        self.assertFalse(self.window.dirty)

    def test_preview_switched_off_while_compile_pending_stays_off(self):
        self.shape()
        self.window.actions["preview"].trigger()
        self.window.actions["preview"].trigger()
        self.settled()
        self.assertFalse(self.window.previewing)
        self.assertFalse(self.window.actions["preview"].isChecked())

    def test_packaged_icon_uses_staged_branding_directory(self):
        branding = self.root / "branding"
        branding.mkdir()
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.fill(QColor("red"))
        image.save(str(branding / "mark.png"))
        with patch("laserforge_native.window.resource_root", return_value=self.root):
            self.assertEqual(icon_path(), branding / "mark.png")
        self.assertFalse(self.window.windowIcon().isNull())

    def test_native_clipboard_shortcuts_cut_paste_and_undo(self):
        self.shape()
        self.window.view.setFocus()
        QTest.keyClick(self.window.view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.settled()
        QTest.keyClick(self.window.view, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.settled()
        self.assertEqual(len(self.window.snapshot["project"]["objects"]), 2)
        self.assertEqual(len(self.window.view.selected_ids()), 1)
        QTest.keyClick(self.window.view, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        self.settled()
        self.assertEqual(len(self.window.snapshot["project"]["objects"]), 1)
        self.window.actions["undo"].trigger()
        self.settled()
        self.assertEqual(len(self.window.snapshot["project"]["objects"]), 2)

    def test_native_simplification_and_local_file_drop(self):
        from PySide6.QtCore import QMimeData, QPointF, QUrl
        from PySide6.QtGui import QDropEvent
        self.window.command("addPaths", {"paths": [{"closed": False, "start": {"x": 0, "y": 0}, "segments": [
            {"type": "L", "to": {"x": 10, "y": .01}}, {"type": "L", "to": {"x": 20, "y": 0}}]}]})
        self.settled()
        with patch("laserforge_native.window.QInputDialog.getDouble", return_value=(.1, True)):
            self.window.actions["simplify"].trigger()
        self.settled()
        self.assertEqual(len(self.window.snapshot["project"]["objects"][0]["paths"][0]["segments"]), 1)
        self.window.path = self.root / "drop.olaser"
        self.window.save_project()
        self.settled()
        self.window.new_project()
        self.settled()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.root / "drop.olaser"))])
        event = QDropEvent(QPointF(100, 100), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.window.dropEvent(event)
        self.settled()
        self.assertTrue(event.isAccepted())
        self.assertEqual(len(self.window.snapshot["project"]["objects"]), 1)

    def test_native_context_menu_copy_and_paste(self):
        self.shape()
        point = self.window.view.mapFromScene(self.window.view.selection_bounds().center())
        menu = self.window.view.create_context_menu(point)
        next(action for action in menu.actions() if action.text() == "Copy").trigger()
        self.settled()
        pasted_menu = self.window.view.create_context_menu(point)
        next(action for action in pasted_menu.actions() if action.text() == "Paste").trigger()
        self.settled()
        self.assertEqual(len(self.window.snapshot["project"]["objects"]), 2)
