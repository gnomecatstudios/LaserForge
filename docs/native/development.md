# Native development

The native application is an experimental migration alongside the browser app. It uses Qt Widgets
and QGraphicsView, never QWebEngine, Electron or a primary webview. Python is the desktop runtime;
Node.js 24+ executes the retained TypeScript library. Do not connect a real laser through this
preview; it has simulation-only machine endpoints.

## Install and run

Requires Python 3.11+ (3.12 tested), Node.js 24+, Corepack/pnpm 10.24.0, and a desktop environment.
From the repository root:

```sh
corepack pnpm install --frozen-lockfile
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e native
corepack pnpm native:bridge
python -m laserforge_native
```

On Windows use `py -3.12 -m venv .venv` then `.venv\Scripts\Activate.ps1`; other commands are the same.
Run Python commands in the activated environment. `LASERFORGE_NODE` may point to a Node executable
if Node is not on PATH. Source changes to the bridge/core require rerunning `pnpm native:bridge`.
No Python port of CAM or project serialization is used.

## Tests

```sh
corepack pnpm typecheck
corepack pnpm lint
corepack pnpm test
corepack pnpm build
corepack pnpm lib:build
python -m unittest discover -s portable -p 'test_*.py'
python scripts/verify-portable-parity.py
python scripts/verify-portable-branding.py
QT_QPA_PLATFORM=offscreen python -m unittest discover -s native/tests -v
QT_QPA_PLATFORM=offscreen python -m laserforge_native --smoke-test --screenshot native-preview.png
```

PowerShell: `$env:QT_QPA_PLATFORM = 'offscreen'` before the last two commands. Native integration tests
need a built bridge and Node. They use temporary settings/projects and the original simulated GRBL
connection. They do not discover serial ports, transmit to USB/BLE, or activate hardware. The CLI
smoke test starts Qt and the core, creates a new document, renders, then exits. Exit 0 means that
limited check passed; it does not prove production readiness.

## Code boundaries

| Location | Responsibility |
| --- | --- |
| `packages/libopenlaser/src/project` | Canonical document, undo/redo, schema and original serializer |
| `packages/libopenlaser/src/geometry` | Original physical-coordinate math |
| `packages/libopenlaser/src/cam` | Original deterministic job compiler/encoders |
| `packages/libopenlaser/src/machine` | Retained protocol, streaming, safety and simulator logic |
| `native/bridge/service.ts` | Version-1 command boundary, in-memory document, validation |
| `native/bridge/server.ts` | Ordered private JSON-lines process protocol, no listening socket |
| `native/laserforge_native/bridge.py` | QProcess asynchronous requests, bounded buffers, failure handling |
| `native/laserforge_native/window.py` | Menus, dialogs, properties, layers, profile, preview and simulation |
| `native/laserforge_native/viewport.py` | QPainter paths/images, indexed scene, handles, grid/rulers and input |
| `native/laserforge_native/files.py` | Opaque file reads and same-filesystem atomic project writes |
| `native/laserforge_native/plugins.py` | Metadata-only API/version/dependency/permission foundation |

Protocol requests are `{id, method, params}`, responses `{id, result}` or `{id, error:{message}}`.
`hello` advertises API 1 and `simulation-only`. Mutations return `{project, profile, canUndo, canRedo}`;
project assets have base64 `data` on IPC and original Blob bytes in the core. File contents are
passed as bytes, with no sidecar filesystem or shell endpoint. Messages are bounded at 128 MiB;
source file inputs at 64 MiB. Core failures surface in the native UI and never silently restart
with an empty document. This stage has no crash-recovery/autosave feature.

Qt menus use QKeySequence StandardKeys and portable Ctrl sequences (Qt maps these to Command on
macOS). V/H/R/E/M select tools, P toggles preview, arrow keys nudge 1 mm, Shift arrows 10 mm,
Delete removes selection, Ctrl+D duplicates, Ctrl+0 fits bed, Shift+2 fits selection. Focused input
fields retain text-editing keys. Unported shortcuts and menus remain in the browser implementation.

## Rendering and coordinates

One scene unit is one millimetre. Objects carry the original six-value affine transform, paths
retain cubic control points, and images invert bitmap rows into Y-up object space. Display mapping
handles all four machine corners. The original `reorient()` normalizes projects on new/load/profile
changes and undo/redo. Cosmetic pens and handle sizes are excluded from dimension fields. Grid and
object alignment snapping is applied in bed millimetres; cursor snapping tolerances are converted
from logical pixels. QGraphicsScene BSP indexing and viewport culling, reusable QPainterPath
geometry, QImage caches and minimal viewport updates are enabled. OpenGL remains deferred.

## Settings and data

QSettings organization `LaserForge`, application `NativePreview` stores native window layout,
grid settings and the current machine profile in the OS user settings location. It does not read
or overwrite the browser's IndexedDB. Projects remain wherever the user saves them. Native packages
are separate from browser updates. Browser profiles/preferences and full settings migration remain
future work; export projects from the browser explicitly before opening them in Qt.

## Troubleshooting

* Missing core bridge: run `pnpm native:bridge` and confirm `native/bridge/dist/server.mjs` exists.
* Core not starting: check Node 24+ or `LASERFORGE_NODE`. Frozen packages should use bundled Node.
* Qt platform plugin error on Linux: install the runtime libraries listed in the distribution guide;
  use `QT_DEBUG_PLUGINS=1` for diagnostics. `offscreen` is for automated checks, not interactive use.
* Missing text: cached outlines are used without fetching fonts. Re-outline/edit in the browser for now.
* Slow large projects: see measured CPU-render results; raster preparation and snapshot transfer are
  not yet optimized. Do not infer screen/output size from display DPI.
* Native update request: automatic updates are not enabled. Do not apply legacy browser ZIPs over a
  Qt installation. Keep projects and settings outside the install directory.

See [validation](validation.md) before treating any platform or feature as supported.
