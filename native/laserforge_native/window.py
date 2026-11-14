"""Native Qt desktop shell. Persisted edits are commands to the canonical core."""
from __future__ import annotations

import base64
import json
import math
import mimetypes
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QImage, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDockWidget, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QToolBar, QVBoxLayout, QWidget,
)

from . import __version__
from .bridge import CoreProcess, resource_root
from .files import atomic_write, read_project
from .viewport import DesignView

MUTATIONS = {"createShape", "addPaths", "addImage", "transform", "delete", "duplicate", "reorder", "undo", "redo", "addLayer", "updateLayer", "moveLayer", "updateObject", "importDxf", "applyMaterial", "setJobSettings"}


def icon_path() -> Path:
    root = resource_root()
    return root / "branding/mark.png" if (root / "branding/mark.png").exists() else root.parent / "public/mark.png"


def spin(minimum=-1_000_000, maximum=1_000_000, suffix=" mm"):
    field = QDoubleSpinBox()
    field.setRange(minimum, maximum)
    field.setDecimals(3)
    field.setSuffix(suffix)
    field.setKeyboardTracking(False)
    return field


class MainWindow(QMainWindow):
    def __init__(self, *, settings=None, smoke=False, screenshot=None):
        super().__init__()
        self.settings = settings or QSettings("LaserForge", "NativePreview")
        self.smoke = smoke
        self.screenshot = screenshot
        self.snapshot = None
        self.path: Path | None = None
        self.dirty = False
        self.revision = 0
        self.edit_generation = 0
        self.preview_generation = 0
        self.loading_fields = False
        self.previewing = False
        self.profile = self.settings.value("machineProfile", {})
        self.catalogs = {}
        self.setWindowTitle(f"LaserForge Native Preview · {__version__}")
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(1440, 900)
        self.view = DesignView()
        self.setCentralWidget(self.view)
        self.view.command.connect(self.command)
        self.view.selectionChanged.connect(self.update_properties)
        self.view.status.connect(self.statusBar().showMessage)
        self.view.dimensionClicked.connect(lambda key: self.fields[key].setFocus())
        self.actions: dict[str, QAction] = {}
        self._menus()
        self._properties()
        self._layers()
        self._machine()
        self._toolbar()
        self.statusBar().showMessage("Starting retained libopenlaser core…")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)
        self.view.set_grid(self.settings.value("gridVisible", True, type=bool), self.settings.value("gridSpacing", 10., type=float))
        self.core = CoreProcess(self)
        self.core.response.connect(self._response)
        self.core.failed.connect(self._error)
        self.core.started.connect(lambda: self.core.request("hello", callback=self._hello))
        QTimer.singleShot(0, self.core.start)

    def _action(self, menu, key, text, shortcut, callback, *, checkable=False):
        action = QAction(text, self)
        if shortcut:
            if isinstance(shortcut, list):
                action.setShortcuts([QKeySequence(s) for s in shortcut])
            else:
                action.setShortcut(shortcut)
        action.setCheckable(checkable)
        action.triggered.connect(callback)
        menu.addAction(action)
        self.actions[key] = action
        return action

    def _menus(self):
        bar = self.menuBar()
        file = bar.addMenu("&File")
        self._action(file, "new", "&New project", QKeySequence.StandardKey.New, lambda: self._discard_then(self.new_project))
        self._action(file, "open", "&Open project…", QKeySequence.StandardKey.Open, self.open_project)
        self._action(file, "save", "&Save", QKeySequence.StandardKey.Save, self.save_project)
        self._action(file, "saveAs", "Save &as…", QKeySequence.StandardKey.SaveAs, lambda: self.save_project(save_as=True))
        self._action(file, "import", "&Import DXF or image…", "Ctrl+I", self.import_art)
        self._action(file, "export", "&Export G-code…", "Ctrl+E", self.export_job)
        file.addSeparator()
        self._action(file, "quit", "Quit", QKeySequence.StandardKey.Quit, self.close)
        edit = bar.addMenu("&Edit")
        self._action(edit, "undo", "&Undo", QKeySequence.StandardKey.Undo, lambda: self.command("undo"))
        self._action(edit, "redo", "&Redo", ["Ctrl+Shift+Z", "Ctrl+Y"], lambda: self.command("redo"))
        self._action(edit, "duplicate", "&Duplicate", "Ctrl+D", lambda: self.selected_command("duplicate"))
        self._action(edit, "delete", "&Delete", ["Delete", "Backspace"], lambda: self.selected_command("delete"))
        self._action(edit, "selectAll", "Select &all", QKeySequence.StandardKey.SelectAll, self.select_all)
        self._action(edit, "front", "Bring to front", None, lambda: self.selected_command("reorder", where="front"))
        self._action(edit, "back", "Send to back", None, lambda: self.selected_command("reorder", where="back"))
        layout = edit.addMenu("Align && distribute")
        for mode, label in [("left", "Align left"), ("right", "Align right"), ("top", "Align top"), ("bottom", "Align bottom"), ("centerX", "Center horizontally"), ("centerY", "Center vertically"), ("distributeX", "Distribute horizontally"), ("distributeY", "Distribute vertically")]:
            self._action(layout, mode, label, None, lambda checked=False, m=mode: self.align(m))
        self._action(edit, "preferences", "Preferences…", None, self.preferences)
        view = self.view_menu = bar.addMenu("&View")
        self._action(view, "fit", "Fit &bed", ["Ctrl+0", "Shift+1"], self.view.fit_bed)
        self._action(view, "fitSelection", "Fit selection", "Shift+2", self.view.fit_selection)
        self._action(view, "zoomIn", "Zoom in", "Ctrl+=", lambda: self.view.zoom_by(1.25))
        self._action(view, "zoomOut", "Zoom out", "Ctrl+-", lambda: self.view.zoom_by(.8))
        self._action(view, "preview", "Job preview", "P", self.toggle_preview, checkable=True)
        self._action(view, "grid", "Show grid", None, self.toggle_grid, checkable=True).setChecked(True)
        self._action(view, "gridSnap", "Snap to grid", None, lambda checked: setattr(self.view, "grid_snap", checked), checkable=True)
        self._action(view, "objectSnap", "Snap to objects", None, lambda checked: setattr(self.view, "object_snap", checked), checkable=True).setChecked(True)
        tools = bar.addMenu("&Tools")
        group = QActionGroup(self)
        for tool, text, key in [("select", "Select", "V"), ("pan", "Pan", "H"), ("rect", "Rectangle", "R"), ("ellipse", "Ellipse", "E"), ("measure", "Measure", "M")]:
            action = self._action(tools, tool, text, key, lambda checked=False, t=tool: self.view.set_tool(t), checkable=True)
            group.addAction(action)
        self.actions["select"].setChecked(True)
        help_menu = bar.addMenu("&Help")
        self._action(help_menu, "help", "Migration status && shortcuts", ["F1", "?"], self.show_help)
        self._action(help_menu, "updates", "Native updates…", None, self.show_updates)
        self._action(help_menu, "about", "About LaserForge", None, self.about)
        escape = QAction(self)
        escape.setShortcut("Escape")
        escape.triggered.connect(lambda: (self.view.set_selected([]), self.view.set_tool("select")))
        self.addAction(escape)

    def _toolbar(self):
        toolbar = QToolBar("Design tools", self)
        toolbar.setObjectName("tools")
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        for key in ["select", "pan", "rect", "ellipse", "measure"]:
            toolbar.addAction(self.actions[key])
        top = QToolBar("Project", self)
        top.setObjectName("project")
        self.addToolBar(top)
        for key in ["new", "open", "save", "undo", "redo", "fit", "preview"]:
            top.addAction(self.actions[key])
        tag = QLabel("  NATIVE PREVIEW · Simulation only  ")
        tag.setStyleSheet("color: #c0392b; font-weight: bold")
        top.addWidget(tag)

    def _dock(self, title, name, widget, area=Qt.DockWidgetArea.RightDockWidgetArea):
        dock = QDockWidget(title, self)
        dock.setObjectName(name)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self.view_menu.addAction(dock.toggleViewAction())
        return dock

    def _properties(self):
        widget = QWidget()
        form = QFormLayout(widget)
        self.fields = {key: spin(.001 if key in {"width", "height"} else -1_000_000) for key in ["x", "y", "width", "height"]}
        for key, field in self.fields.items():
            field.setObjectName(f"dimension_{key}")
            form.addRow({"x": "X", "y": "Y", "width": "Width", "height": "Height"}[key], field)
            field.editingFinished.connect(lambda k=key: self.change_dimension(k))
        self.rotation = spin(-360, 360, "°")
        self.rotation.setValue(0)
        form.addRow("Rotate by", self.rotation)
        rotate = QPushButton("Apply rotation")
        rotate.clicked.connect(self.rotate_selection)
        form.addRow(rotate)
        self.aspect = QCheckBox("Keep aspect ratio")
        self.aspect.setChecked(True)
        form.addRow(self.aspect)
        self.selection_info = QLabel("No selection")
        form.addRow(self.selection_info)
        self._dock("Selection · mm", "selection", widget)

    def _layers(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.layer_list = QListWidget()
        self.layer_list.setObjectName("layers")
        self.layer_list.currentRowChanged.connect(self.update_layer_fields)
        layout.addWidget(self.layer_list)
        buttons = QHBoxLayout()
        for text, callback in [("+ Layer", lambda: self.command("addLayer")), ("↑", lambda: self.move_layer(-1)), ("↓", lambda: self.move_layer(1))]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        form = QFormLayout()
        self.layer_name = QLineEdit()
        self.layer_name.editingFinished.connect(lambda: self.patch_layer(name=self.layer_name.text()))
        form.addRow("Name", self.layer_name)
        self.layer_mode = QComboBox()
        self.layer_mode.addItems(["line", "fill", "image"])
        self.layer_mode.currentTextChanged.connect(lambda value: self.patch_layer(mode=value))
        form.addRow("Mode", self.layer_mode)
        self.speed = spin(1, 1_000_000, " mm/min")
        self.power = spin(0, 100, " %")
        self.passes = QSpinBox()
        self.passes.setRange(1, 1000)
        self.speed.editingFinished.connect(lambda: self.patch_layer(speed=self.speed.value()))
        self.power.editingFinished.connect(lambda: self.patch_layer(power=self.power.value()))
        self.passes.editingFinished.connect(lambda: self.patch_layer(passes=self.passes.value()))
        form.addRow("Speed", self.speed)
        form.addRow("Power", self.power)
        form.addRow("Passes", self.passes)
        self.visible_layer = QCheckBox("Visible")
        self.output_layer = QCheckBox("Output enabled")
        self.visible_layer.toggled.connect(lambda value: self.patch_layer(visible=value))
        self.output_layer.toggled.connect(lambda value: self.patch_layer(output=value))
        form.addRow(self.visible_layer, self.output_layer)
        self.materials = QComboBox()
        self.materials.addItem("Choose retained material preset…", None)
        self.materials.activated.connect(self.apply_material)
        form.addRow("Material", self.materials)
        assign = QPushButton("Move selection to this layer")
        assign.clicked.connect(self.assign_layer)
        form.addRow(assign)
        layout.addLayout(form)
        self._dock("Layers && laser settings", "layersDock", widget)

    def _machine(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        title = QLabel("SIMULATED MACHINE")
        title.setStyleSheet("color: #c0392b; font-weight: bold")
        layout.addWidget(title)
        label = QLabel("No physical device is opened. Native serial and Bluetooth controls await safety-preflight migration.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.profile_label = QLabel("400 × 400 mm · bottom-left origin")
        layout.addWidget(self.profile_label)
        profile_button = QPushButton("Machine profile…")
        profile_button.clicked.connect(self.edit_profile)
        layout.addWidget(profile_button)
        self.simulate_button = QPushButton("Validate && run in simulator")
        self.simulate_button.clicked.connect(self.simulate)
        layout.addWidget(self.simulate_button)
        self.job_info = QLabel("No compiled job")
        self.job_info.setWordWrap(True)
        layout.addWidget(self.job_info)
        self._dock("Machine && job", "machine", widget, Qt.DockWidgetArea.BottomDockWidgetArea)

    def _hello(self, result):
        if result.get("protocolVersion") != 1:
            self._error("startup", "Incompatible application core protocol.")
            return
        self.core.request("catalogs", callback=self._catalogs)
        self.new_project()

    def _catalogs(self, result):
        self.catalogs = result
        for material in result.get("materials", []):
            label = f"{material.get('material')} · {material.get('thicknessMm', '?')} mm · {material.get('operation', '')}"
            self.materials.addItem(label, material["id"])

    def new_project(self):
        self.path = None
        self.core.request("new", callback=lambda _: self._restore_profile())

    def _restore_profile(self):
        if self.profile:
            self.core.request("setProfile", {"profile": self.profile})
        self.dirty = False
        self._title()
        QTimer.singleShot(0, self.view.fit_bed)
        if self.smoke:
            QTimer.singleShot(150, self._smoke_done)

    def _smoke_done(self):
        if self.screenshot:
            if not self.grab().save(self.screenshot):
                QApplication.instance().exit(2)
                return
        self.core.close()
        QApplication.instance().quit()

    def _response(self, method, result):
        if isinstance(result, dict) and "project" in result:
            previous_ids = {o["id"] for o in self.snapshot["project"]["objects"]} if self.snapshot else set()
            selection = self.view.selected_ids()
            profile_changed_geometry = method == "setProfile" and self.snapshot is not None and self.snapshot["project"]["objects"] != result["project"]["objects"]
            self.snapshot = result
            self.preview_generation += 1
            self.profile = result.get("profile", self.profile)
            self.view.set_document(result["project"], self.profile)
            added = [o["id"] for o in result["project"]["objects"] if o["id"] not in previous_ids]
            self.view.set_selected(added if method in {"createShape", "duplicate", "addPaths", "addImage", "importDxf"} else selection)
            self.previewing = False
            self.actions["preview"].setChecked(False)
            self.view.set_preview(None)
            self.actions["undo"].setEnabled(result.get("canUndo", False))
            self.actions["redo"].setEnabled(result.get("canRedo", False))
            row = self.layer_list.currentRow()
            self.loading_fields = True
            self.layer_list.clear()
            for layer in result["project"]["layers"]:
                item = QListWidgetItem(f"{'●' if layer['visible'] else '○'} {layer['name']}  ·  {layer['mode']}")
                item.setForeground(Qt.GlobalColor.darkRed if layer["output"] else Qt.GlobalColor.gray)
                self.layer_list.addItem(item)
            self.layer_list.setCurrentRow(min(max(0, row), self.layer_list.count() - 1))
            self.loading_fields = False
            self.update_layer_fields()
            self.update_properties()
            if profile_changed_geometry:
                self.dirty = True
                self.edit_generation += 1
            if method in MUTATIONS:
                self.revision += 1
                self.dirty = True
            elif method in {"new", "load"}:
                self.revision += 1
                self.dirty = False
            self.profile_label.setText(f"{self.profile.get('name', 'GRBL')} · {self.profile.get('bedWidth', 400):g} × {self.profile.get('bedHeight', 400):g} mm · origin {self.profile.get('originCorner', 'bl')}")
            self._title()
        self.statusBar().showMessage(f"{method} complete", 2500)

    def _title(self):
        name = self.path.name if self.path else "Untitled"
        self.setWindowTitle(f"{'*' if self.dirty else ''}{name} — LaserForge Native Preview {__version__}")

    def _error(self, method, message):
        self.statusBar().showMessage(f"{method}: {message}")
        self.simulate_button.setEnabled(True)
        if self.smoke:
            print(f"{method}: {message}", flush=True)
            QApplication.instance().exit(1)
        else:
            QMessageBox.warning(self, "LaserForge", f"{method}: {message}")

    def command(self, method, params=None):
        if method == "createShape":
            params = dict(params or {})
            layer = self.current_layer()
            if layer:
                params["layerId"] = layer["id"]
        if method in MUTATIONS:
            self.edit_generation += 1
            self.dirty = True
            self._title()
        self.core.request(method, params or {})

    def selected_command(self, method, **params):
        ids = self.view.selected_ids()
        if ids:
            self.command(method, {"ids": ids, **params})

    def select_all(self):
        if self.snapshot:
            self.view.set_selected([o["id"] for o in self.snapshot["project"]["objects"] if not o.get("locked")])

    def current_layer(self):
        row = self.layer_list.currentRow()
        layers = self.snapshot["project"]["layers"] if self.snapshot else []
        return layers[row] if 0 <= row < len(layers) else None

    def update_layer_fields(self, *_):
        if self.loading_fields:
            return
        layer = self.current_layer()
        self.loading_fields = True
        for field in [self.layer_name, self.layer_mode, self.speed, self.power, self.passes, self.visible_layer, self.output_layer, self.materials]:
            field.setEnabled(layer is not None)
        if layer:
            self.layer_name.setText(layer["name"])
            self.layer_mode.setCurrentText(layer["mode"])
            self.speed.setValue(layer["speed"])
            self.power.setValue(layer["power"])
            self.passes.setValue(layer["passes"])
            self.visible_layer.setChecked(layer["visible"])
            self.output_layer.setChecked(layer["output"])
        self.loading_fields = False

    def patch_layer(self, **patch):
        layer = self.current_layer()
        if layer and not self.loading_fields and any(layer.get(key) != value for key, value in patch.items()):
            self.command("updateLayer", {"id": layer["id"], "patch": patch})

    def move_layer(self, delta):
        row = self.layer_list.currentRow()
        if 0 <= row + delta < self.layer_list.count():
            self.command("moveLayer", {"from": row, "to": row + delta})
            self.layer_list.setCurrentRow(row + delta)

    def apply_material(self, index):
        layer = self.current_layer()
        preset = self.materials.itemData(index)
        if layer and preset:
            self.command("applyMaterial", {"layerId": layer["id"], "presetId": preset})

    def assign_layer(self):
        layer = self.current_layer()
        if layer:
            for object_id in self.view.selected_ids():
                self.command("updateObject", {"id": object_id, "patch": {"layerId": layer["id"]}})

    def update_properties(self, *_):
        bounds = self.view.selection_bounds()
        self.loading_fields = True
        self.selection_info.setText(f"{len(self.view.selected_ids())} selected")
        for field in self.fields.values():
            field.setEnabled(bounds is not None)
        if bounds is not None:
            for key, value in {"x": bounds.left(), "y": bounds.top(), "width": bounds.width(), "height": bounds.height()}.items():
                self.fields[key].setValue(value)
        self.loading_fields = False

    def change_dimension(self, key):
        if self.loading_fields:
            return
        bounds = self.view.selection_bounds()
        if bounds is None:
            return
        value = self.fields[key].value()
        matrix = [1, 0, 0, 1, 0, 0]
        if key == "x":
            matrix[4] = value - bounds.left()
        elif key == "y":
            matrix[5] = value - bounds.top()
        else:
            old = bounds.width() if key == "width" else bounds.height()
            if old <= 0:
                return
            scale = value / old
            sx = scale if key == "width" or self.aspect.isChecked() else 1
            sy = scale if key == "height" or self.aspect.isChecked() else 1
            matrix = [sx, 0, 0, sy, bounds.left() * (1 - sx), bounds.top() * (1 - sy)]
        if matrix != [1, 0, 0, 1, 0, 0]:
            self.selected_command("transform", matrix=matrix)

    def rotate_selection(self):
        bounds = self.view.selection_bounds()
        if bounds is None:
            return
        radians = math.radians(self.rotation.value())
        c, s = math.cos(radians), math.sin(radians)
        x, y = bounds.center().x(), bounds.center().y()
        self.selected_command("transform", matrix=[c, s, -s, c, x - c*x + s*y, y - s*x - c*y])
        self.rotation.setValue(0)

    def align(self, mode):
        ids = self.view.selected_ids()
        if len(ids) < 2:
            return
        # Qt's exact cached path bounds supply measurements; core applies all matrices.
        boxes = [(object_id, self.view.object_bounds(object_id)) for object_id in ids]
        boxes = [(i, b) for i, b in boxes if b is not None]
        if len(boxes) < 2:
            return
        union = self.view.selection_bounds()
        horizontal = mode.endswith("X")
        if mode.startswith("distribute"):
            boxes.sort(key=lambda pair: pair[1].center().x() if horizontal else pair[1].center().y())
            centers = [b.center().x() if horizontal else b.center().y() for _, b in boxes]
            step = (centers[-1] - centers[0]) / (len(centers) - 1)
        for index, (object_id, box) in enumerate(boxes):
            dx = dy = 0.
            if mode == "left": dx = union.left() - box.left()
            elif mode == "right": dx = union.right() - box.right()
            elif mode == "top": dy = union.bottom() - box.bottom()
            elif mode == "bottom": dy = union.top() - box.top()
            elif mode == "centerX": dx = union.center().x() - box.center().x()
            elif mode == "centerY": dy = union.center().y() - box.center().y()
            elif horizontal: dx = centers[0] + step*index - box.center().x()
            else: dy = centers[0] + step*index - box.center().y()
            if dx or dy:
                self.command("transform", {"ids": [object_id], "matrix": [1, 0, 0, 1, dx, dy]})

    def _flush_editors(self):
        focus = QApplication.focusWidget()
        if focus is not None and self.isAncestorOf(focus):
            focus.clearFocus()  # editingFinished is synchronous; edits queue before save/close.

    def _discard_then(self, continuation):
        self._flush_editors()
        if not self.dirty:
            continuation()
            return
        answer = QMessageBox.question(self, "Unsaved project", "Save your changes before continuing?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            self.save_project(after=continuation)
        elif answer == QMessageBox.StandardButton.Discard:
            continuation()

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open LaserForge project", "", "LaserForge project (*.olaser);;All files (*)")
        if path:
            self._discard_then(lambda: self.load_path(path))

    def load_path(self, path):
        try:
            data = base64.b64encode(read_project(path)).decode()
        except (OSError, ValueError) as error:
            self._error("open", str(error))
            return
        def opened(_):
            self.path = Path(path)
            self._restore_profile()
        self.core.request("load", {"data": data}, opened)

    def save_project(self, checked=False, *, save_as=False, after=None):
        self._flush_editors()
        destination = self.path
        if destination is None or save_as:
            path, _ = QFileDialog.getSaveFileName(self, "Save LaserForge project", str(destination or "Untitled.olaser"), "LaserForge project (*.olaser)")
            if not path:
                return
            destination = Path(path)
            if not destination.suffix:
                destination = destination.with_suffix(".olaser")
        generation = self.edit_generation
        def saved(result):
            try:
                atomic_write(destination, base64.b64decode(result["data"], validate=True))
            except (OSError, ValueError) as error:
                self._error("save", str(error))
                return
            self.path = destination
            if self.edit_generation == generation:
                self.dirty = False
            self._title()
            if after and not self.dirty:
                after()
        self.core.request("save", callback=saved)

    def import_art(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import art", "", "DXF and raster images (*.dxf *.png *.jpg *.jpeg *.bmp *.webp);;All files (*)")
        if not path:
            return
        try:
            data = read_project(path)
            if Path(path).suffix.lower() == ".dxf":
                self.command("importDxf", {"source": data.decode("utf-8"), "name": Path(path).stem})
                return
            image = QImage.fromData(data)
            if image.isNull():
                raise ValueError("Unsupported image. SVG, G-code document imports and font editing are still available in the legacy app.")
            self.command("addImage", {"data": base64.b64encode(data).decode(), "mime": mimetypes.guess_type(path)[0] or "application/octet-stream", "name": Path(path).name, "widthPx": image.width(), "heightPx": image.height()})
        except (OSError, ValueError) as error:
            self._error("import", str(error))

    def _compile_params(self):
        rasters = {}
        if self.snapshot:
            for asset_id, asset in self.snapshot["project"].get("assets", {}).items():
                image = QImage.fromData(base64.b64decode(asset["data"]))
                if not image.isNull():
                    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
                    # RGBA8888 rows are tightly packed (4 bytes/pixel).
                    rasters[asset_id] = {"width": image.width(), "height": image.height(), "data": base64.b64encode(bytes(image.constBits())).decode()}
        return {"profile": self.profile, "rasters": rasters}

    def _show_plan(self, plan):
        stats = plan["stats"]
        warnings = "\n".join(w["message"] for w in plan["warnings"])
        self.job_info.setText(f"{stats['lineCount']} lines · {stats['burnDistance']:.1f} mm burn · estimated {stats['estimatedSeconds']:.1f} s" + (f"\n{warnings}" if warnings else ""))
        return not any(w["blocking"] for w in plan["warnings"])

    def toggle_preview(self, checked=False):
        self.preview_generation += 1
        generation = self.preview_generation
        if not checked:
            self.view.set_preview(None)
            self.previewing = False
            return
        def compiled(plan):
            if generation != self.preview_generation or not self.actions["preview"].isChecked():
                return
            self._show_plan(plan)
            self.view.set_preview(plan)
            self.previewing = True
        self.core.request("compile", self._compile_params(), compiled)

    def export_job(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export G-code", "job.gcode", "G-code (*.gcode)")
        if not path:
            return
        def compiled(plan):
            if not self._show_plan(plan):
                self._error("export", "Blocking CAM warnings must be resolved before export. See Machine && job.")
                return
            try:
                atomic_write(path, ("\n".join(plan["gcode"]) + "\n").encode())
            except OSError as error:
                self._error("export", str(error))
        self.core.request("compile", self._compile_params(), compiled)

    def simulate(self):
        self.simulate_button.setEnabled(False)
        def finished(result):
            self.simulate_button.setEnabled(True)
            self.job_info.setText("Simulation: " + json.dumps(result, ensure_ascii=False))
        self.core.request("simulate", self._compile_params(), finished)

    def toggle_grid(self, checked):
        self.view.set_grid(checked, self.settings.value("gridSpacing", 10., type=float))
        self.settings.setValue("gridVisible", checked)

    def preferences(self):
        spacing, ok = QInputDialog.getDouble(self, "Preferences", "Grid spacing (physical mm)", self.settings.value("gridSpacing", 10., type=float), .1, 1000, 3)
        if ok:
            self.settings.setValue("gridSpacing", spacing)
            self.view.set_grid(self.actions["grid"].isChecked(), spacing)

    def edit_profile(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Machine profile · simulation only")
        form = QFormLayout(dialog)
        name = QLineEdit(self.profile.get("name", "Generic GRBL laser"))
        width, height = spin(.1), spin(.1)
        width.setValue(self.profile.get("bedWidth", 400))
        height.setValue(self.profile.get("bedHeight", 400))
        corner = QComboBox()
        corner.addItems(["bl", "tl", "tr", "br"])
        corner.setCurrentText(self.profile.get("originCorner", "bl"))
        max_s = spin(1, 1_000_000, "")
        max_s.setValue(self.profile.get("maxS", 1000))
        for label, field in [("Name", name), ("Bed width", width), ("Bed height", height), ("Origin corner", corner), ("Maximum S", max_s)]:
            form.addRow(label, field)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec():
            profile = {**self.profile, "name": name.text(), "bedWidth": width.value(), "bedHeight": height.value(), "originCorner": corner.currentText(), "maxS": max_s.value()}
            def applied(result):
                self.settings.setValue("machineProfile", result["profile"])
                self.view.fit_bed()
            self.core.request("setProfile", {"profile": profile}, applied)

    def show_help(self):
        QMessageBox.information(self, "Native migration status", "Native preview: vectors and cached text outlines, images, rectangles/ellipses, selection, transforms, layers, undo/redo, DXF, .olaser files, G-code preview/export and simulation.\n\nV Select · H Pan · R Rectangle · E Ellipse · M Measure · wheel Zoom · middle/Space drag Pan\nCtrl+N/O/S New/Open/Save · Ctrl+Z Undo · Ctrl+Shift+Z/Ctrl+Y Redo · Ctrl+D Duplicate · Delete · Ctrl+0 Fit · Shift+2 Fit selection · P Preview\n\nStill use the browser application for pen/node/text editing, SVG and G-code document imports, tracing, advanced laser/accessory controls, printing and automatic updates. Hardware is disabled in this preview. See docs/native/migration.md and validation.md.")

    def show_updates(self):
        QMessageBox.information(self, "Native update channel", "This experimental native build does not self-update yet. The existing browser/portable update channel remains unchanged. Native releases require separate signed manifests, staging and rollback before automatic updates are enabled. Projects and preferences are stored outside the installation.")

    def about(self):
        QMessageBox.about(self, "About LaserForge", f"LaserForge Native Preview {__version__}\nQt Widgets · PySide6 · retained libopenlaser core\nMIT — Copyright © 2026 Anam Ahmed\nLaserForge contributors / gnomecatstudios\n\nMigration is in progress; this is not a production hardware controller.")

    def closeEvent(self, event):
        self._flush_editors()
        if self.dirty and not self.smoke:
            event.ignore()
            self._discard_then(lambda: self._close_clean())
            return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.core.close()
        event.accept()

    def _close_clean(self):
        self.dirty = False
        self.close()
