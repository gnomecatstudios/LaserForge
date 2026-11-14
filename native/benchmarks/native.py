"""CPU/offscreen native viewport benchmark; not a full application startup measurement."""
import argparse
import json
import os
import platform
from pathlib import Path
import statistics
import sys
import time

STARTED = time.perf_counter()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6 import __version__ as qt_binding_version
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication
from laserforge_native.viewport import DesignView


def summarize(samples):
    ordered = sorted(samples)
    return {"median_ms": statistics.median(ordered),
            "p95_ms": ordered[min(len(ordered) - 1, int(len(ordered) * .95))],
            "samples": len(ordered)}


def current_rss():
    try:
        # Linux current RSS, not peak; other platforms deliberately report unavailable.
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except OSError:
        pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--iterations", type=int, default=30)
    args = parser.parse_args()
    project = json.loads(args.fixture.read_text())
    app = QApplication([])
    view = DesignView()
    view.resize(1440, 900)
    view.show()
    app.processEvents()
    profile = {"bedWidth": 400, "bedHeight": 400, "originCorner": "bl"}
    load_start = time.perf_counter()
    view.set_document(project, profile)
    view.fit_bed()
    app.processEvents()
    image = QImage(1440, 900, QImage.Format.Format_ARGB32_Premultiplied)

    def draw():
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        view.render(painter)
        painter.end()

    draw()
    scene_load_first_draw_ms = (time.perf_counter() - load_start) * 1000
    harness_startup_ms = (time.perf_counter() - STARTED) * 1000
    for _ in range(5):
        draw()
    redraw, zoom_pan, selection = [], [], []
    for index in range(args.iterations):
        started = time.perf_counter()
        draw()
        redraw.append((time.perf_counter() - started) * 1000)
        view.zoom_by(.98 if index % 2 else 1 / .98)
        bar = view.horizontalScrollBar()
        bar.setValue(bar.value() + (-3 if index % 2 else 3))
        started = time.perf_counter()
        draw()
        zoom_pan.append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        view.itemAt(QPoint(1, 1))
        selection.append((time.perf_counter() - started) * 1000)
    print(json.dumps({
        "renderer": "Qt QGraphicsView/QPainter CPU offscreen", "objects": len(project["objects"]),
        "scene_load_first_draw_ms": scene_load_first_draw_ms,
        "harness_startup_ms": harness_startup_ms, "redraw": summarize(redraw),
        "zoom_pan_redraw": summarize(zoom_pan), "selection_miss": summarize(selection),
        "viewport": {"width": 1440, "height": 900}, "device_pixel_ratio": view.devicePixelRatioF(),
        "rss_bytes": current_rss(), "platform": platform.platform(),
        "pyside6": qt_binding_version, "python": platform.python_version(),
    }, indent=2))
    view.close()


if __name__ == "__main__":
    main()
