"""Offscreen Qt tests. No physical machine connection is created."""
import base64
import copy
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QIODevice, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from laserforge_native.viewport import DesignView, affine, path_from_data


def rectangle(identity="box", x=20, y=25, width=40, height=30):
    return {"id": identity, "kind": "vector", "name": identity, "layerId": "cut", "visible": True,
            "locked": False, "transform": [1, 0, 0, 1, x, y],
            "paths": [{"start": {"x": 0, "y": 0}, "closed": True,
                       "segments": [{"type": "L", "to": {"x": width, "y": 0}},
                                    {"type": "L", "to": {"x": width, "y": height}},
                                    {"type": "L", "to": {"x": 0, "y": height}}]}]}


def document(objects=None):
    return {"objects": objects if objects is not None else [rectangle()],
            "layers": [{"id": "cut", "visible": True, "mode": "line", "color": "#c0392b"}],
            "assets": {}}


class ViewportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view = DesignView()
        self.view.resize(900, 700)
        self.profile = {"bedWidth": 200, "bedHeight": 150, "originCorner": "bl"}
        self.view.set_document(document(), self.profile)
        self.view.show()
        self.view.fit_bed()
        self.app.processEvents()

    def tearDown(self):
        self.view.close()

    def test_cubic_path_and_six_value_affine_match_canonical_coordinates(self):
        path = path_from_data([{"start": {"x": 0, "y": 0}, "closed": False,
                                "segments": [{"type": "C", "c1": {"x": 1, "y": 2},
                                              "c2": {"x": 3, "y": 4}, "to": {"x": 5, "y": 6}}]}])
        self.assertEqual(path.elementCount(), 4)
        point = affine([2, 3, 4, 5, 6, 7]).map(QPointF(11, 13))
        self.assertEqual(point, QPointF(80, 105))

    def test_all_machine_corners_map_and_round_trip_in_mm(self):
        for corner in ("bl", "tl", "tr", "br"):
            profile = {**self.profile, "originCorner": corner}
            self.view.set_document(document(), profile)
            a = self.view.mapFromScene(QPointF(0, 0))
            b = self.view.mapFromScene(QPointF(100, 75))
            self.assertEqual(b.x() > a.x(), corner not in ("tr", "br"))
            self.assertEqual(b.y() > a.y(), corner in ("tl", "tr"))
            original = QPointF(43.125, 61.375)
            screen = self.view.viewportTransform().map(original)
            actual = self.view.viewportTransform().inverted()[0].map(screen)
            self.assertAlmostEqual(actual.x(), original.x(), places=10)
            self.assertAlmostEqual(actual.y(), original.y(), places=10)

    def test_selection_geometry_excludes_cosmetic_stroke_and_zoom(self):
        self.assertIsNone(self.view.selection_bounds())
        self.assertIsNone(self.view.object_bounds("missing"))
        self.assertEqual(self.view.object_bounds("box"), QRectF(20, 25, 40, 30))
        self.view.set_selected(["box"])
        self.assertEqual(self.view.selection_bounds(), QRectF(20, 25, 40, 30))

    def test_focused_view_arrow_nudge_uses_existing_mm_and_shift_shortcuts(self):
        self.view.set_selected(["box"])
        commands = []
        self.view.command.connect(lambda method, params: commands.append((method, params)))
        QTest.keyClick(self.view, Qt.Key.Key_Up)
        QTest.keyClick(self.view, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(commands, [("transform", {"ids": ["box"], "matrix": [1, 0, 0, 1, 0, 1]}),
                                    ("transform", {"ids": ["box"], "matrix": [1, 0, 0, 1, -10, 0]})])
        self.view.zoom_by(3)
        self.assertEqual(self.view.selection_bounds(), QRectF(20, 25, 40, 30))

    def test_scene_item_and_cached_path_survive_unrelated_snapshot(self):
        item = self.view.items_by_id["box"]
        path = item.path
        changed = document()
        changed["objects"][0]["name"] = "new name"
        self.view.set_document(changed, self.profile)
        self.assertIs(self.view.items_by_id["box"], item)
        self.assertIs(item.path, path)

    def test_layer_visibility_lock_z_order_and_removal(self):
        first, second = rectangle(), rectangle("other")
        self.view.set_document(document([first, second]), self.profile)
        self.assertIs(self.view._pick(self.view.mapFromScene(QPointF(30, 35))), self.view.items_by_id["other"])
        second["locked"] = True
        self.view.set_document(document([first, second]), self.profile)
        self.view.set_selected(["other"])
        self.assertEqual(self.view.selected_ids(), [])
        self.assertIs(self.view._pick(self.view.mapFromScene(QPointF(30, 35))), self.view.items_by_id["box"])
        hidden = document([first])
        hidden["layers"][0]["visible"] = False
        self.view.set_document(hidden, self.profile)
        self.assertFalse(self.view.items_by_id["box"].isVisible())
        self.assertNotIn("other", self.view.items_by_id)

    def test_click_and_shift_click_multiselection(self):
        self.view.set_document(document([rectangle(), rectangle("other", x=100)]), self.profile)
        QTest.mouseClick(self.view.viewport(), Qt.MouseButton.LeftButton, pos=self.view.mapFromScene(QPointF(30, 35)))
        self.assertEqual(self.view.selected_ids(), ["box"])
        QTest.mouseClick(self.view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier,
                         self.view.mapFromScene(QPointF(110, 35)))
        self.assertEqual(set(self.view.selected_ids()), {"box", "other"})

    def test_shape_drag_emits_physical_creation_once(self):
        self.view.set_tool("rect")
        self.view.object_snap = False
        commands = []
        self.view.command.connect(lambda method, params: commands.append((method, params)))
        start, end = QPointF(70, 80), QPointF(110, 100)
        QTest.mousePress(self.view.viewport(), Qt.MouseButton.LeftButton, pos=self.view.mapFromScene(start))
        QTest.mouseMove(self.view.viewport(), self.view.mapFromScene(end))
        self.assertEqual(commands, [])
        QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.LeftButton, pos=self.view.mapFromScene(end))
        self.assertEqual(len(commands), 1)
        method, params = commands[0]
        self.assertEqual(method, "createShape")
        self.assertEqual(params["kind"], "rect")
        for key, expected in (("x", 70), ("y", 80), ("width", 40), ("height", 20)):
            self.assertAlmostEqual(params[key], expected, delta=1 / self.view._zoom)

    def test_move_preview_then_one_atomic_bed_transform(self):
        self.view.object_snap = False
        self.view.set_selected(["box"])
        commands = []
        self.view.command.connect(lambda method, params: commands.append((method, params)))
        start, end = QPointF(35, 35), QPointF(45, 40)
        QTest.mousePress(self.view.viewport(), Qt.MouseButton.LeftButton, pos=self.view.mapFromScene(start))
        QTest.mouseMove(self.view.viewport(), self.view.mapFromScene(end))
        self.assertEqual(commands, [])
        QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.LeftButton, pos=self.view.mapFromScene(end))
        self.assertEqual(len(commands), 1)
        method, params = commands[0]
        self.assertEqual(method, "transform")
        self.assertEqual(params["ids"], ["box"])
        self.assertEqual(params["matrix"][:4], [1, 0, 0, 1])
        self.assertAlmostEqual(params["matrix"][4], 10, delta=1 / self.view._zoom)
        self.assertAlmostEqual(params["matrix"][5], 5, delta=1 / self.view._zoom)

    def test_grid_snap_and_validation(self):
        self.view.object_snap = False
        self.view.grid_snap = True
        self.view.set_grid(True, 2.5)
        self.assertEqual(self.view._snapped(QPointF(6.2, 7.8)), QPointF(5, 7.5))
        for invalid in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.view.set_grid(True, invalid)

    def test_move_snaps_selection_edges_to_grid_and_other_objects(self):
        self.view.set_document(document([rectangle(), rectangle("target", x=70, y=25)]), self.profile)
        self.view.set_selected(["box"])
        self.view.object_snap = False
        self.view.grid_snap = True
        self.view.set_grid(True, 10)
        # The 25-mm Y edge snaps to 30 mm, independent of where inside it we clicked.
        self.assertEqual(self.view._snapped_move(QPointF(9, 4), self.view.selection_bounds(), ["box"]),
                         QPointF(10, 5))
        self.view.grid_snap = False
        self.view.object_snap = True
        # Selection right edge at 69 mm snaps to the target's 70-mm left edge.
        snapped = self.view._snapped_move(QPointF(9, 0), self.view.selection_bounds(), ["box"])
        self.assertAlmostEqual(snapped.x(), 10)
        self.assertAlmostEqual(snapped.y(), 0)

    def test_escape_restores_drag_preview_and_emits_no_document_command(self):
        self.view.object_snap = False
        commands = []
        self.view.command.connect(lambda method, params: commands.append((method, params)))
        start, end = QPointF(35, 35), QPointF(45, 40)
        QTest.mousePress(self.view.viewport(), Qt.MouseButton.LeftButton, pos=self.view.mapFromScene(start))
        QTest.mouseMove(self.view.viewport(), self.view.mapFromScene(end))
        QTest.keyClick(self.view, Qt.Key.Key_Escape)
        self.assertEqual(commands, [])
        self.assertEqual(self.view.object_bounds("box"), QRectF(20, 25, 40, 30))

    def test_clickable_dimension_label_requests_property_focus(self):
        self.view.set_selected(["box"])
        self.view.viewport().repaint()
        requested = []
        self.view.dimensionClicked.connect(requested.append)
        QTest.mouseClick(self.view.viewport(), Qt.MouseButton.LeftButton,
                         pos=self.view._dimension_rects["width"].center().toPoint())
        self.assertEqual(requested, ["width"])

    def test_fit_selection_can_reach_geometry_outside_machine_bed(self):
        self.view.set_document(document([rectangle(x=10000, y=-2000)]), self.profile)
        self.view.set_selected(["box"])
        self.view.fit_selection()
        position = self.view.mapFromScene(QPointF(10020, -1985))
        self.assertTrue(self.view.viewport().rect().contains(position))

    def test_cursor_zoom_preserves_anchor_with_scrollbar_rounding_tolerance(self):
        anchor = self.view.mapFromScene(QPointF(60, 50))
        before = self.view.mapToScene(anchor)
        self.view.zoom_by(1.7, anchor)
        after = self.view.mapToScene(anchor)
        self.assertAlmostEqual(after.x(), before.x(), delta=1 / self.view._zoom + 1e-10)
        self.assertAlmostEqual(after.y(), before.y(), delta=1 / self.view._zoom + 1e-10)

    def test_raster_is_cached_and_top_row_stays_at_positive_local_y(self):
        image = QImage(2, 2, QImage.Format.Format_RGB32)
        image.fill(QColor("blue"))
        image.setPixelColor(0, 0, QColor("red"))
        image.setPixelColor(1, 0, QColor("red"))
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        obj = {"id": "image", "kind": "image", "layerId": "cut", "name": "image", "visible": True,
               "locked": False, "transform": [1, 0, 0, 1, 30, 30], "assetId": "asset", "width": 40, "height": 40}
        project = document([obj])
        project["assets"] = {"asset": {"data": base64.b64encode(buffer.data()).decode()}}
        self.view.set_document(project, self.profile)
        self.view.set_grid(False, 10)
        self.app.processEvents()
        rendered = self.view.viewport().grab().toImage()
        top = self.view.mapFromScene(QPointF(50, 60))
        bottom = self.view.mapFromScene(QPointF(50, 40))
        self.assertGreater(rendered.pixelColor(top).red(), 200)
        self.assertLess(rendered.pixelColor(top).blue(), 50)
        self.assertGreater(rendered.pixelColor(bottom).blue(), 200)
        self.assertLess(rendered.pixelColor(bottom).red(), 50)
        cached = self.view.items_by_id["image"].image
        self.view.set_document(copy.deepcopy(project), self.profile)
        self.assertIs(self.view.items_by_id["image"].image, cached)

    def test_handles_resize_and_rotate_emit_core_transforms(self):
        self.view.object_snap = False
        self.view.set_selected(["box"])
        self.app.processEvents()
        self.view.viewport().repaint()
        commands = []
        self.view.command.connect(lambda method, params: commands.append((method, params)))
        start = self.view._handles["br"].toPoint()
        end = self.view.mapFromScene(QPointF(80, 70))
        QTest.mousePress(self.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(self.view.viewport(), end)
        QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
        self.assertEqual(commands[0][0], "transform")
        self.assertAlmostEqual(commands[0][1]["matrix"][0], 1.5, delta=0.02)
        self.assertAlmostEqual(commands[0][1]["matrix"][3], 1.5, delta=0.02)
        # Restore canonical snapshot before the next independent edit.
        self.view.set_document(document(), self.profile)
        self.view.set_selected(["box"])
        self.view.viewport().repaint()
        start = self.view._handles["rotate"].toPoint()
        center = self.view.mapFromScene(QPointF(40, 40))
        delta = start - center
        end = center + QPoint(-delta.y(), delta.x())
        QTest.mousePress(self.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(self.view.viewport(), end)
        QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
        self.assertEqual(len(commands), 2)
        matrix = commands[1][1]["matrix"]
        self.assertAlmostEqual(matrix[0], 0, delta=0.01)
        self.assertAlmostEqual(abs(matrix[1]), 1, delta=0.01)


if __name__ == "__main__":
    unittest.main()
