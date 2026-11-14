"""Asynchronous private process boundary. No browser, socket server or hardware endpoint."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Callable

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

MAX_MESSAGE = 128 * 1024 * 1024


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def bridge_path() -> Path:
    root = resource_root()
    return root / "bridge" / ("server.mjs" if getattr(sys, "frozen", False) else "dist/server.mjs")


def node_path() -> str:
    explicit = os.environ.get("LASERFORGE_NODE")
    if explicit:
        return explicit
    bundled = resource_root() / "runtime" / ("node.exe" if sys.platform == "win32" else "node")
    return str(bundled) if bundled.is_file() else shutil.which("node") or "node"


class CoreProcess(QObject):
    """Ordered async RPC; callbacks always run on Qt's GUI thread.

    A lost core is fatal to this session, never silently restarted with an empty
    document. Timed-out requests terminate the process because state is uncertain.
    """
    response = Signal(str, object)
    failed = Signal(str, str)
    started = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(self._stderr)
        self.process.started.connect(self.started)
        self.process.errorOccurred.connect(lambda _: self._fail_all(self.process.errorString()))
        self.process.finished.connect(lambda *_: self._fail_all("Application core stopped. Save recovery requires restarting LaserForge."))
        self.buffer = bytearray()
        self.diagnostics = ""
        self.sequence = 0
        self.pending: dict[int, tuple[str, Callable | None, QTimer]] = {}
        self.closing = False

    def start(self):
        path = bridge_path()
        if not path.is_file():
            QTimer.singleShot(0, lambda: self.failed.emit("startup", "Missing core bridge. Run pnpm native:bridge first."))
            return
        self.process.start(node_path(), [str(path)])

    def request(self, method: str, params: dict | None = None, callback: Callable | None = None) -> int:
        if self.process.state() != QProcess.ProcessState.Running:
            self.failed.emit(method, "Application core is not running.")
            return -1
        self.sequence += 1
        token = self.sequence
        payload = json.dumps({"id": token, "method": method, "params": params or {}}, allow_nan=False, separators=(",", ":")).encode() + b"\n"
        if len(payload) > MAX_MESSAGE:
            self.failed.emit(method, "Request exceeds the 128 MiB IPC limit.")
            return -1
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._abort("Core request timed out; restart to avoid uncertain project state."))
        self.pending[token] = (method, callback, timer)
        timer.start(120_000)
        if self.process.write(payload) < 0:
            self._abort("Could not send request to application core.")
        return token

    def _stderr(self):
        self.diagnostics = (self.diagnostics + bytes(self.process.readAllStandardError()).decode(errors="replace"))[-8192:]

    def _read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b"\n" in self.buffer:
            line, _, rest = self.buffer.partition(b"\n")
            self.buffer = bytearray(rest)
            if len(line) > MAX_MESSAGE:
                self._abort("Core response exceeds IPC limit.")
                return
            try:
                message = json.loads(line)
                pending = self.pending.pop(message.get("id"), None)
                if pending is None:
                    raise ValueError("Unknown core response identifier")
                method, callback, timer = pending
                timer.stop()
                timer.deleteLater()
                if "error" in message:
                    self.failed.emit(method, message["error"].get("message", "Core operation failed"))
                else:
                    result = message["result"]
                    self.response.emit(method, result)
                    if callback:
                        callback(result)
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                self._abort(f"Invalid application core response: {error}")
                return
        if len(self.buffer) > MAX_MESSAGE:
            self._abort("Core response exceeds IPC limit.")

    def _abort(self, reason: str):
        self._fail_all(reason)
        self.process.kill()

    def _fail_all(self, reason: str):
        pending, self.pending = self.pending, {}
        for method, _, timer in pending.values():
            timer.stop()
            timer.deleteLater()
            if not self.closing:
                self.failed.emit(method, reason)
        if not pending and not self.closing:
            self.failed.emit("core", reason)

    def close(self):
        self.closing = True
        for _, _, timer in self.pending.values():
            timer.stop()
        self.pending.clear()
        self.process.closeWriteChannel()
        # QProcess shutdown is bounded; no hardware session exists in this stage.
        if not self.process.waitForFinished(1000):
            self.process.kill()
            self.process.waitForFinished(1000)
