"""Native millimetre viewport. Qt paints; libopenlaser remains the document authority.

No device-pixel ratio, view zoom, or screen coordinate enters an emitted document
command. Geometry is cached in each graphics item, and the scene's BSP index
provides culling and selection candidate lookup.
"""
from __future__ import annotations

import base64
import math

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor, QImage, QPainter, QPainterPath, QPainterPathStroker, QPen,
    QTransform,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView, QMenu


def path_from_data(paths: list[dict]) -> QPainterPath:
    """Translate original absolute line/cubic paths without flattening them."""
    result = QPainterPath()
    result.setFillRule(Qt.FillRule.OddEvenFill)
    for path in paths:
        start = path["start"]
        result.moveTo(start["x"], start["y"])
        for segment in path["segments"]:
            target = segment["to"]
            if segment["type"] == "L":
                result.lineTo(target["x"], target["y"])
            else:
                c1, c2 = segment["c1"], segment["c2"]
                result.cubicTo(c1["x"], c1["y"], c2["x"], c2["y"], target["x"], target["y"])
        if path["closed"]:
            result.closeSubpath()
    return result


def affine(values: list[float]) -> QTransform:
    """Qt's six-value constructor uses the canonical [a,b,c,d,e,f] order."""
    return QTransform(*values)


class SceneObjectItem(QGraphicsItem):
    def __init__(self, obj: dict, layer: dict, asset: dict | None = None):
        super().__init__()
        self.obj = {}
        self.path = QPainterPath()
        self.image = QImage()
        self._geometry_key = None
        self._asset_key = None
        self._bounds = QRectF()
        self.update_document(obj, layer, asset)

    def update_document(self, obj: dict, layer: dict, asset: dict | None = None):
        geometry_key = (obj.get("kind"), obj.get("paths"), obj.get("width"), obj.get("height"))
        if geometry_key != self._geometry_key:
            self.prepareGeometryChange()
            self.path = path_from_data(obj.get("paths", []))
            if obj["kind"] == "image":
                self.path.addRect(0, 0, obj["width"], obj["height"])
            elif self.path.isEmpty() and obj["kind"] == "text":
                self.path.addRect(0, 0, max(1, len(obj.get("text", ""))) * obj.get("fontSize", 4) * 0.6,
                                  obj.get("fontSize", 4))
            self._bounds = self.path.controlPointRect().adjusted(-0.5, -0.5, 0.5, 0.5)
            self._geometry_key = geometry_key
        data = asset.get("data", asset.get("base64", "")) if asset else ""
        if data != self._asset_key:
            self.image = QImage.fromData(base64.b64decode(data)) if data else QImage()
            self._asset_key = data
        self.obj, self.layer = obj, layer
        self.setTransform(affine(obj["transform"]))
        self.setVisible(bool(obj.get("visible", True) and layer.get("visible", True)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, not obj.get("locked", False))
        if obj.get("locked", False):
            self.setSelected(False)
        self.setToolTip(obj.get("name", obj["kind"]))
        self.update()

    def boundingRect(self) -> QRectF:
        return self._bounds

    def shape(self) -> QPainterPath:
        stroke = QPainterPathStroker()
        stroke.setWidth(0.8)
        return self.path.united(stroke.createStroke(self.path))

    def paint(self, painter: QPainter, option, widget=None):
        color = QColor(self.layer.get("color", "#c0392b"))
        pen = QPen(color, 1.4)
        pen.setCosmetic(True)
        painter.setPen(pen)
        if self.obj["kind"] == "image":
            if not self.image.isNull():
                painter.save()
                # Bitmap rows are top-down; canonical image-local coordinates are Y-up.
                painter.translate(0, self.obj["height"])
                painter.scale(1, -1)
                painter.drawImage(QRectF(0, 0, self.obj["width"], self.obj["height"]), self.image)
                painter.restore()
            else:
                painter.drawPath(self.path)
        else:
            if self.layer.get("mode") == "fill":
                fill = QColor(color)
                fill.setAlpha(65)
                painter.setBrush(fill)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.path)


class DesignView(QGraphicsView):
    selectionChanged = Signal(list)
    command = Signal(str, dict)
    status = Signal(str)
    dimensionClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("designViewport")
        self.setScene(QGraphicsScene(self))
        self.scene().setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        self.scene().selectionChanged.connect(self._selection_changed)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setBackgroundBrush(QColor("#dce0e5"))
        self.items_by_id: dict[str, SceneObjectItem] = {}
        self.project = {"objects": [], "layers": [], "assets": {}}
        self.profile = {"bedWidth": 400, "bedHeight": 400, "originCorner": "bl"}
        self.tool = "select"
        self.grid_visible = True
        self.grid_spacing = 10.0
        self.grid_snap = False
        self.object_snap = True
        self._zoom = 1.0
        self._space = False
        self._drag = None
        self._ghost = None
        self._measure = None
        self._guides = []
        self._preview = None
        self._preview_path = QPainterPath()
        self._handles = {}
        self._dimension_rects = {}
        self._syncing = False
        self.setSceneRect(-400, -400, 1200, 1200)
        self._apply_view_transform()

    def set_document(self, project: dict, profile: dict):
        self._syncing = True
        selected = self.selected_ids()
        old_frame = tuple(self.profile.get(k) for k in ("bedWidth", "bedHeight", "originCorner"))
        self.project, self.profile = project, profile
        layers = {layer["id"]: layer for layer in project["layers"]}
        wanted = {obj["id"] for obj in project["objects"]}
        for identity in self.items_by_id.keys() - wanted:
            item = self.items_by_id.pop(identity)
            self.scene().removeItem(item)
        for z, obj in enumerate(project["objects"]):
            layer = layers.get(obj["layerId"], {"visible": False})
            asset = project.get("assets", {}).get(obj.get("assetId"))
            item = self.items_by_id.get(obj["id"])
            if item is None:
                item = SceneObjectItem(obj, layer, asset)
                self.items_by_id[obj["id"]] = item
                self.scene().addItem(item)
            else:
                item.update_document(obj, layer, asset)
            item.setPos(0, 0)
            item.setZValue(z)
            item.setSelected(obj["id"] in selected and not obj.get("locked", False) and item.isVisible())
        w, h = profile["bedWidth"], profile["bedHeight"]
        extent = QRectF(0, 0, w, h).united(self.scene().itemsBoundingRect())
        margin = max(w, h, 1000)
        self.setSceneRect(extent.adjusted(-margin, -margin, margin, margin))
        self._syncing = False
        self.set_preview(None)
        self._selection_changed()
        if old_frame != tuple(profile.get(k) for k in ("bedWidth", "bedHeight", "originCorner")):
            self.fit_bed()
        self.viewport().update()

    def selected_ids(self) -> list[str]:
        return [identity for identity, item in self.items_by_id.items() if item.isSelected()]

    def set_selected(self, ids: list[str]):
        self._syncing = True
        for identity, item in self.items_by_id.items():
            item.setSelected(identity in ids and item.isVisible() and not item.obj.get("locked", False))
        self._syncing = False
        self._selection_changed()

    def object_bounds(self, identity: str) -> QRectF | None:
        item = self.items_by_id.get(identity)
        return item.mapToScene(item.path).boundingRect() if item is not None else None

    def selection_bounds(self) -> QRectF | None:
        bounds = None
        for item in self.scene().selectedItems():
            # Exact path geometry: cosmetic pen margins must never change physical dimensions.
            box = item.mapToScene(item.path).boundingRect()
            bounds = box if bounds is None else bounds.united(box)
        return bounds

    def _selection_changed(self):
        if not self._syncing:
            self.selectionChanged.emit(self.selected_ids())
            self.viewport().update()

    def set_tool(self, tool: str):
        self.tool = tool
        self._drag = None
        self._ghost = None
        self.setCursor(Qt.CursorShape.OpenHandCursor if tool == "pan" else
                       Qt.CursorShape.CrossCursor if tool != "select" else Qt.CursorShape.ArrowCursor)
        self.viewport().update()

    def set_grid(self, visible: bool, spacing: float):
        if not math.isfinite(spacing) or spacing <= 0:
            raise ValueError("Grid spacing must be a positive finite millimetre value")
        self.grid_visible, self.grid_spacing = visible, spacing
        self.viewport().update()

    def _apply_view_transform(self):
        corner = self.profile.get("originCorner", "bl")
        sx = -1 if corner in ("tr", "br") else 1
        sy = 1 if corner in ("tl", "tr") else -1
        self.setTransform(QTransform.fromScale(sx * self._zoom, sy * self._zoom))

    def fit_bed(self):
        self._fit(QRectF(0, 0, self.profile["bedWidth"], self.profile["bedHeight"]))

    def fit_selection(self):
        box = self.selection_bounds()
        if box is not None and not box.isNull():
            self._fit(box)

    def _fit(self, box: QRectF):
        self._zoom = min(200, max(0.05, min((self.viewport().width() - 96) / max(box.width(), 1),
                                          (self.viewport().height() - 96) / max(box.height(), 1))))
        self._apply_view_transform()
        self.centerOn(box.center())
        self.viewport().update()

    def zoom_by(self, factor: float, anchor=None):
        if not math.isfinite(factor) or factor <= 0:
            return
        anchor = self.viewport().rect().center() if anchor is None else anchor
        before = self.mapToScene(anchor)
        self._zoom = min(200, max(0.05, self._zoom * factor))
        self._apply_view_transform()
        after = self.mapToScene(anchor)
        self.centerOn(self.mapToScene(self.viewport().rect().center()) + before - after)
        self.viewport().update()

    def wheelEvent(self, event):
        self.zoom_by(1.0015 ** event.angleDelta().y(), event.position().toPoint())
        event.accept()

    def set_preview(self, plan: dict | None):
        self._preview = plan
        path = QPainterPath()
        for toolpath in (plan or {}).get("toolpaths", []):
            for run in toolpath.get("runs", []):
                points = run["points"]
                if len(points) >= 4:
                    path.moveTo(points[0], points[1])
                    for i in range(2, len(points), 2):
                        path.lineTo(points[i], points[i + 1])
        self._preview_path = path
        self.viewport().update()

    def _snapped(self, point: QPointF, exclude=None) -> QPointF:
        """Bounded object candidates use the scene index; snapping stays in bed mm."""
        x, y = point.x(), point.y()
        self._guides = []
        if self.grid_snap:
            x, y = round(x / self.grid_spacing) * self.grid_spacing, round(y / self.grid_spacing) * self.grid_spacing
        if self.object_snap:
            tolerance = 7 / self._zoom
            candidates = self.scene().items(QRectF(x - tolerance, y - tolerance, tolerance * 2, tolerance * 2))
            best_x = best_y = tolerance
            for item in candidates:
                if not isinstance(item, SceneObjectItem) or item.obj["id"] in (exclude or []) or not item.isVisible():
                    continue
                box = item.mapToScene(item.path).boundingRect()
                for target in (box.left(), box.center().x(), box.right()):
                    if abs(target - point.x()) < best_x:
                        best_x, x = abs(target - point.x()), target
                for target in (box.top(), box.center().y(), box.bottom()):
                    if abs(target - point.y()) < best_y:
                        best_y, y = abs(target - point.y()), target
            if best_x < tolerance:
                self._guides.append(("x", x))
            if best_y < tolerance:
                self._guides.append(("y", y))
        return QPointF(x, y)

    def _pick(self, screen_point):
        # Native index narrows candidates; stroke tolerance stays approximately screen-sized.
        tolerance = 6 / self._zoom
        scene_point = self.mapToScene(screen_point)
        candidates = self.scene().items(QRectF(scene_point.x() - tolerance, scene_point.y() - tolerance,
                                               tolerance * 2, tolerance * 2))
        for item in candidates:
            if not isinstance(item, SceneObjectItem) or not item.isVisible() or item.obj.get("locked", False):
                continue
            path = item.mapToScene(item.path)
            stroke = QPainterPathStroker()
            stroke.setWidth(tolerance * 2)
            if path.contains(scene_point) or stroke.createStroke(path).contains(scene_point):
                return item
        return None

    def _snapped_move(self, delta: QPointF, box: QRectF, exclude: list[str]) -> QPointF:
        """Snap moving selection bounds, rather than its arbitrary click position."""
        self._guides = []
        dx, dy = delta.x(), delta.y()
        if self.grid_snap:
            dx = round((box.left() + dx) / self.grid_spacing) * self.grid_spacing - box.left()
            dy = round((box.top() + dy) / self.grid_spacing) * self.grid_spacing - box.top()
        if self.object_snap:
            moved = box.translated(dx, dy)
            tolerance = 7 / self._zoom
            candidates = self.scene().items(moved.adjusted(-tolerance, -tolerance, tolerance, tolerance))
            best_x = best_y = tolerance
            adjust_x = adjust_y = 0
            guide_x = guide_y = None
            for item in candidates:
                if not isinstance(item, SceneObjectItem) or item.obj["id"] in exclude or not item.isVisible():
                    continue
                target = item.mapToScene(item.path).boundingRect()
                for a in (moved.left(), moved.center().x(), moved.right()):
                    for b in (target.left(), target.center().x(), target.right()):
                        if abs(a - b) < best_x:
                            best_x, adjust_x, guide_x = abs(a - b), b - a, b
                for a in (moved.top(), moved.center().y(), moved.bottom()):
                    for b in (target.top(), target.center().y(), target.bottom()):
                        if abs(a - b) < best_y:
                            best_y, adjust_y, guide_y = abs(a - b), b - a, b
            dx, dy = dx + adjust_x, dy + adjust_y
            if guide_x is not None:
                self._guides.append(("x", guide_x))
            if guide_y is not None:
                self._guides.append(("y", guide_y))
        return QPointF(dx, dy)

    def _save_drag(self, kind, point, **kwargs):
        self._drag = {"kind": kind, "screen": point, "start": self.mapToScene(point),
                      "ids": self.selected_ids(),
                      "originals": {identity: QTransform(item.transform()) for identity, item in self.items_by_id.items()
                                    if item.isSelected()}, **kwargs}

    def mousePressEvent(self, event):
        self.setFocus()
        point = event.position().toPoint()
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and
                                                            (self.tool == "pan" or self._space)):
            self._save_drag("pan", point, h=self.horizontalScrollBar().value(), v=self.verticalScrollBar().value())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        if self.tool == "select":
            for axis, label in self._dimension_rects.items():
                if label.contains(QPointF(point)):
                    self.dimensionClicked.emit(axis)
                    return
            for handle, position in self._handles.items() if self.selected_ids() else []:
                if (position - QPointF(point)).manhattanLength() < 11:
                    box = self.selection_bounds()
                    self._save_drag("rotate" if handle == "rotate" else "resize", point,
                                    handle=handle, box=box)
                    return
            picked = self._pick(point)
            additive = bool(event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
            if picked:
                ids = self.selected_ids()
                identity = picked.obj["id"]
                if additive:
                    self.set_selected([i for i in ids if i != identity] if identity in ids else ids + [identity])
                elif identity not in ids:
                    self.set_selected([identity])
                if picked.isSelected():
                    self._save_drag("move", point, box=self.selection_bounds())
            else:
                if not additive:
                    self.set_selected([])
                self._save_drag("marquee", point, additive=additive)
        elif self.tool in ("rect", "ellipse", "measure"):
            self._save_drag(self.tool, point)
            self._drag["start"] = self._snapped(self.mapToScene(point))
        event.accept()

    def mouseMoveEvent(self, event):
        point = event.position().toPoint()
        scene_point = self.mapToScene(point)
        self.status.emit(f"X {scene_point.x():.3f} mm   Y {scene_point.y():.3f} mm")
        drag = self._drag
        if drag:
            kind = drag["kind"]
            if kind == "pan":
                delta = point - drag["screen"]
                self.horizontalScrollBar().setValue(drag["h"] - delta.x())
                self.verticalScrollBar().setValue(drag["v"] - delta.y())
            elif kind == "move":
                if (point - drag["screen"]).manhattanLength() < 3:
                    return
                delta = self._snapped_move(scene_point - drag["start"], drag["box"], drag["ids"])
                matrix = QTransform.fromTranslate(delta.x(), delta.y())
                drag["matrix"] = [1, 0, 0, 1, delta.x(), delta.y()]
                self._preview_transform(matrix)
            elif kind in ("resize", "rotate"):
                self._transform_drag(scene_point, event.modifiers())
            elif kind in ("rect", "ellipse", "marquee"):
                target = self._snapped(scene_point) if kind != "marquee" else scene_point
                self._ghost = QRectF(drag["start"], target).normalized()
            elif kind == "measure":
                self._measure = (drag["start"], self._snapped(scene_point))
            self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _preview_transform(self, matrix):
        # Qt combines transforms in row-vector order. original * change applies
        # the bed-space change after the object's original local transform.
        for identity, original in self._drag["originals"].items():
            self.items_by_id[identity].setTransform(original * matrix)

    def _transform_drag(self, target, modifiers):
        drag = self._drag
        box, start = drag["box"], drag["start"]
        if drag["kind"] == "rotate":
            center = box.center()
            angle = math.atan2(target.y() - center.y(), target.x() - center.x()) - math.atan2(start.y() - center.y(), start.x() - center.x())
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                angle = round(angle / (math.pi / 12)) * math.pi / 12
            c, s = math.cos(angle), math.sin(angle)
            values = [c, s, -s, c, center.x() - c * center.x() + s * center.y(), center.y() - s * center.x() - c * center.y()]
        else:
            handle = drag["handle"]
            pivot = QPointF(box.right() if "l" in handle else box.left() if "r" in handle else box.center().x(),
                            box.bottom() if "t" in handle else box.top() if "b" in handle else box.center().y())
            target = self._snapped(target, drag["ids"])
            dx, dy = start.x() - pivot.x(), start.y() - pivot.y()
            sx = (target.x() - pivot.x()) / dx if ("l" in handle or "r" in handle) and abs(dx) > 1e-9 else 1
            sy = (target.y() - pivot.y()) / dy if ("t" in handle or "b" in handle) and abs(dy) > 1e-9 else 1
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                sx = sy = sx if abs(sx - 1) > abs(sy - 1) else sy
            sx = math.copysign(max(abs(sx), 0.001), sx)
            sy = math.copysign(max(abs(sy), 0.001), sy)
            values = [sx, 0, 0, sy, pivot.x() * (1 - sx), pivot.y() * (1 - sy)]
        drag["matrix"] = values
        self._preview_transform(affine(values))

    def mouseReleaseEvent(self, event):
        drag = self._drag
        if drag and event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            kind = drag["kind"]
            if "matrix" in drag:
                # Keep preview until the authoritative snapshot arrives; on failure
                # the shell restores its snapshot, so failed commands do not persist.
                self.command.emit("transform", {"ids": drag["ids"], "matrix": drag["matrix"]})
            elif kind in ("rect", "ellipse") and self._ghost is not None:
                box = self._ghost
                if box.width() >= 0.01 and box.height() >= 0.01:
                    self.command.emit("createShape", {"kind": kind, "x": box.left(), "y": box.top(),
                                                      "width": box.width(), "height": box.height()})
            elif kind == "marquee" and self._ghost is not None:
                ids = drag["ids"] if drag["additive"] else []
                for item in self.scene().items(self._ghost, Qt.ItemSelectionMode.IntersectsItemShape):
                    if isinstance(item, SceneObjectItem) and item.isVisible() and not item.obj.get("locked", False):
                        if item.obj["id"] not in ids:
                            ids.append(item.obj["id"])
                self.set_selected(ids)
            self._drag, self._ghost, self._guides = None, None, []
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.tool == "pan" else
                           Qt.CursorShape.CrossCursor if self.tool != "select" else Qt.CursorShape.ArrowCursor)
            self.viewport().update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        arrows = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                  Qt.Key.Key_Up: (0, 1), Qt.Key.Key_Down: (0, -1)}
        if event.key() in arrows and self.selected_ids():
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx, dy = arrows[event.key()]
            self.command.emit("transform", {"ids": self.selected_ids(),
                                            "matrix": [1, 0, 0, 1, dx * step, dy * step]})
            event.accept()
        elif event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            if self._drag:
                for identity, original in self._drag["originals"].items():
                    self.items_by_id[identity].setTransform(original)
            self._drag, self._ghost, self._measure = None, None, None
            self.set_tool("select")
            self.set_selected([])
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self._space = False
        if self._drag:
            for identity, original in self._drag["originals"].items():
                item = self.items_by_id.get(identity)
                if item is not None:
                    item.setTransform(original)
            self._drag, self._ghost, self._guides = None, None, []
        self.viewport().update()
        super().focusOutEvent(event)

    def contextMenuEvent(self, event):
        self.create_context_menu(event.pos()).exec(event.globalPos())

    def create_context_menu(self, position):
        picked = self._pick(position)
        if picked and not picked.isSelected():
            self.set_selected([picked.obj["id"]])
        ids = self.selected_ids()
        menu = QMenu(self)
        for label, method, params in (("Copy", "clipboardCopy", {}),
                                      ("Cut", "clipboardCut", {}),
                                      ("Simplify paths…", "simplifySelection", {}),
                                      ("Duplicate", "duplicate", {"ids": ids}),
                                      ("Delete", "delete", {"ids": ids}),
                                      ("Bring to front", "reorder", {"ids": ids, "where": "front"}),
                                      ("Send to back", "reorder", {"ids": ids, "where": "back"})):
            action = menu.addAction(label)
            action.setEnabled(bool(ids))
            action.triggered.connect(lambda checked=False, m=method, p=params: self.command.emit(m, p))
        menu.addAction("Paste", lambda: self.command.emit("clipboardPaste", {}))
        menu.addSeparator()
        menu.addAction("Fit bed", self.fit_bed)
        menu.addAction("Fit selection", self.fit_selection).setEnabled(bool(ids))
        return menu

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        bed = QRectF(0, 0, self.profile["bedWidth"], self.profile["bedHeight"])
        painter.fillRect(bed, QColor("#ffffff"))
        if self.grid_visible:
            step = self.grid_spacing
            # Avoid an excessive grid loop at extreme zoom-outs or huge beds.
            while step * self._zoom < 6:
                step *= 2
            visible = rect.intersected(bed)
            painter.setPen(QPen(QColor("#e8ebef"), 0))
            x = math.ceil(visible.left() / step) * step
            while x <= visible.right():
                painter.drawLine(QPointF(x, visible.top()), QPointF(x, visible.bottom()))
                x += step
            y = math.ceil(visible.top() / step) * step
            while y <= visible.bottom():
                painter.drawLine(QPointF(visible.left(), y), QPointF(visible.right(), y))
                y += step
        painter.setPen(QPen(QColor("#a3abb6"), 0))
        painter.drawRect(bed)

    def drawForeground(self, painter, rect):
        painter.save()
        if self._preview:
            pen = QPen(QColor("#0b8793"), 2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawPath(self._preview_path)
        if self._ghost is not None:
            pen = QPen(QColor("#c0392b"), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if self._drag and self._drag["kind"] == "ellipse":
                painter.drawEllipse(self._ghost)
            else:
                painter.drawRect(self._ghost)
        painter.setPen(QPen(QColor("#d08824"), 0, Qt.PenStyle.DashLine))
        for axis, value in self._guides:
            painter.drawLine(QPointF(value, rect.top()), QPointF(value, rect.bottom())) if axis == "x" else painter.drawLine(QPointF(rect.left(), value), QPointF(rect.right(), value))
        if self._measure:
            a, b = self._measure
            painter.setPen(QPen(QColor("#0b8793"), 0))
            painter.drawLine(a, b)
        painter.resetTransform()
        if self._measure:
            a, b = self._measure
            target = self.mapFromScene(b)
            painter.setPen(QColor("#0b6570"))
            painter.drawText(target + QPoint(8, -8),
                             f"{math.hypot(b.x() - a.x(), b.y() - a.y()):.3f} mm")
        self._draw_selection(painter)
        self._draw_rulers(painter)
        painter.restore()

    def _draw_selection(self, painter):
        self._handles, self._dimension_rects = {}, {}
        if not self.selected_ids():
            return
        box = self.selection_bounds()
        # Handle names refer to canonical scene bounds, so mirrors do not change math.
        points = {"tl": box.topLeft(), "t": QPointF(box.center().x(), box.top()), "tr": box.topRight(),
                  "r": QPointF(box.right(), box.center().y()), "br": box.bottomRight(),
                  "b": QPointF(box.center().x(), box.bottom()), "bl": box.bottomLeft(),
                  "l": QPointF(box.left(), box.center().y())}
        self._handles = {key: QPointF(self.mapFromScene(value)) for key, value in points.items()}
        screen = self.mapFromScene(box).boundingRect()
        rotate = QPointF(screen.center().x(), screen.top() - 26)
        self._handles["rotate"] = rotate
        painter.setPen(QPen(QColor("#c0392b"), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(screen)
        painter.drawLine(QPointF(screen.center().x(), screen.top()), rotate)
        painter.setPen(QPen(QColor("#c0392b"), 1))
        painter.setBrush(QColor("white"))
        for key, p in self._handles.items():
            if key == "rotate":
                painter.drawEllipse(p, 4, 4)
            else:
                painter.drawRect(QRectF(p.x() - 3, p.y() - 3, 6, 6))
        width = QRectF(screen.center().x() - 48, screen.bottom() + 10, 96, 22)
        height = QRectF(screen.right() + 12, screen.center().y() - 11, 96, 22)
        self._dimension_rects = {"width": width, "height": height}
        for area, value in ((width, box.width()), (height, box.height())):
            painter.fillRect(area, QColor("#fff4f2"))
            painter.setPen(QColor("#a12f25"))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, f"{value:.3f} mm")

    def _draw_rulers(self, painter):
        width, height = self.viewport().width(), self.viewport().height()
        painter.fillRect(QRectF(0, 0, width, 19), QColor("#f3f4f6"))
        painter.fillRect(QRectF(0, 0, 38, height), QColor("#f3f4f6"))
        painter.setPen(QColor("#616b79"))
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        step = self.grid_spacing
        while step * self._zoom < 55:
            step *= 2
        x = math.ceil(max(0, visible.left()) / step) * step
        while x <= min(self.profile["bedWidth"], visible.right()):
            sx = self.mapFromScene(QPointF(x, 0)).x()
            painter.drawText(QRectF(sx - 23, 1, 46, 17), Qt.AlignmentFlag.AlignCenter, f"{x:g}")
            x += step
        y = math.ceil(max(0, visible.top()) / step) * step
        while y <= min(self.profile["bedHeight"], visible.bottom()):
            sy = self.mapFromScene(QPointF(0, y)).y()
            painter.drawText(QRectF(0, sy - 9, 34, 18), Qt.AlignmentFlag.AlignRight, f"{y:g}")
            y += step
        painter.fillRect(QRectF(0, 0, 38, 19), QColor("#f3f4f6"))
        painter.drawText(QRectF(0, 0, 34, 19), Qt.AlignmentFlag.AlignCenter, "mm")
