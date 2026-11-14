"""Run `python -m laserforge_native` after building the core bridge."""
import argparse
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


def main():
    parser = argparse.ArgumentParser(description="LaserForge native desktop migration preview")
    parser.add_argument("--smoke-test", action="store_true", help="Initialize Qt and core, render once and exit without hardware")
    parser.add_argument("--screenshot", help="Save the native window after smoke initialization")
    args = parser.parse_args()
    if args.smoke_test and not os.environ.get("DISPLAY") and sys.platform.startswith("linux"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from .window import MainWindow
    app = QApplication(sys.argv[:1])
    app.setApplicationName("LaserForge")
    app.setOrganizationName("LaserForge")
    window = MainWindow(smoke=args.smoke_test, screenshot=args.screenshot)
    window.show()
    if args.smoke_test:
        QTimer.singleShot(30_000, lambda: app.exit(3))
    result = app.exec()
    window.core.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
