# Native desktop migration

Status: incremental development, **not a feature-parity replacement**. Baseline: commit
`5343a4cb7ae063df639d69e4b31562db922abec3`, version 0.2.5. The browser application and
all four existing portable targets remain available and unchanged.

## Repository audit and decision (before implementation)

| Area | Existing implementation | Decision |
| --- | --- | --- |
| Interface | Svelte 5, TypeScript, Vite 8; `src/app` | Replace incrementally with PySide6 Qt Widgets |
| Desktop runtime | Go HTTP server embeds web assets and opens external Chrome/Edge/default browser (`portable/launcher/main.go`); not an embedded webview | Add independent native launcher; retain legacy launcher |
| Viewport | Canvas 2D, Path2D cache, DOMMatrix, animation frame redraw; `src/app/canvas` | Qt QGraphicsScene/View and QPainterPath; no browser dependency |
| Geometry | `packages/libopenlaser/src/geometry`: affine matrices, cubic paths, flattening, Clipper, simplification | Retain exact TypeScript algorithms |
| Editing | Pure project operations/history, plus Svelte editor state, layout, handles, guides, pen/node/text tools | Expose pure operations through a private Node process; port UI interactions in stages |
| Files | Schema 1 `.olaser` ZIP containing `project.json` and assets; JSON/base64 alternative; migrations in project/serialize.ts | Use original serializer/deserializer; no new file format |
| Imports | SVG (DOMParser), DXF (pure), G-code (pure), images (browser decode) | Retain parsers; adapt DOM/image boundaries; report missing adapters |
| Exports/CAM | Deterministic vector/raster CAM; GRBL G-code, Ruida RD, LaserPecker encoders | Retain; compare with direct compilation and existing golden fixtures |
| Hardware | UI-free GRBL drivers, stream accounting, runner, simulator, LaserPecker virtual device; Web Serial/Bluetooth transports | Preserve all legacy code. Native simulator first; real transports only after app preflight extraction |
| Safety | JobRunner/driver safeguards plus mandatory app-layer preflight in `src/app/state/machine.svelte.ts` | Never expose hardware through an incomplete native safety path |
| Preferences | IndexedDB (`src/lib/storage`) and Svelte state; profiles/materials and backup import/export | Keep browser data; native settings in separate OS user-data location |
| Shortcuts/menus | `src/app/shortcuts.ts`, canvas/workspace menus; file/edit/view/tools, nudge, measurement editing | Port supported actions with original keys; track remaining actions explicitly |
| Updates | PWA prompt; Go and Python full-ZIP update, checksums, staging/replacement/rollback | Keep legacy update channel. Native channel needs separate format and trust model |
| Distribution | Versioned ZIPs Windows x64, Linux x64, Pi ARM64/ARM32, icons/fonts/licenses, parity checks | Add separate experimental native packages; no untested support claims |
| Tests | Vitest unit/property/golden/simulated machine tests; Playwright browser scenarios; Python portable and Go updater tests | Keep existing suites; add native IPC, file/output parity, offscreen Qt tests and benchmarks |

Root and library MIT licenses and original contributor attribution remain intact. Qt/PySide
and other bundled runtime licenses must accompany native distributions. Current native targets
are Windows x64, Linux Mint x64 and Raspberry Pi OS. macOS is excluded, consistent with the
repository's platform preference. Legacy packaging retains Windows/Linux x64 and both Pi
ARM64/ARM32 targets. Native Pi ARM64 needs compatible Qt/Python/OS builds; ARM32 remains on
the working browser package until its Qt/Node runtime blockers are resolved.

### Framework evaluation

Qt 6/PySide6 Widgets supplies native menus, file dialogs, docks, accessibility and high-DPI
coordinates on all requested desktop OSes. C++ Qt would still need a bridge or a substantial
TypeScript rewrite. Rust/egui and wxPython also need that bridge and offer less direct reuse of
the requested dock/property/graphics architecture. Electron/Tauri retain browser rendering and
do not meet the objective. Choose PySide6 plus a **headless Node sidecar**, not a JS UI engine.
Node is an explicit runtime dependency retained to avoid rewriting tested geometry/CAM/protocols.

Use one scene unit per physical millimetre. Object transforms retain `[a,b,c,d,e,f]`, Y-up bed
coordinates, machine corner mapping, layer execution order and object array z-order. Display
zoom and device pixel ratio never enter serialization or CAM input. Qt stores paths in object
space and scene items in a BSP spatial index with viewport culling. Start with QPainter raster
rendering and cached paths/images. QOpenGLWidget is deferred until measurements show benefit;
QGraphicsView alone is not a guarantee of faster rendering.

### Layer boundaries

* `libopenlaser`: canonical project state, history, geometry, serialization, CAM and protocols.
* `native/bridge`: versioned, private stdin/stdout request/response adapter; no network listener,
  no shell commands, no plugin hardware endpoint.
* `native/laserforge_native`: Qt shell/viewport and bridge client; no alternate CAM implementation.
* Native plugins: explicit manifests and capability-limited API; no direct machine access.

Core operations and native drawing can progress independently. Expensive CAM must execute outside
the GUI process; IPC must not freeze the event loop. Real serial/BLE integration is gated on
extracting all legacy safety checks, testing driver/transport behavior under faults and validating
equivalent jobs in simulation. Automated tests must never open a physical device.

## Staged delivery and merge gates

1. Audit, baseline suites, reproducible browser/native benchmark harnesses.
2. Versioned bridge to retained project/CAM operations; real `.olaser` and golden-output tests.
3. Qt shell with native menus/dialogs/docks, red logo and independent settings.
4. Physical-coordinate Qt viewport, vectors/text outlines/images, selection, zoom/pan/grid.
5. Tools, transform/property editing, undo/redo, layers, context menus; track parity gaps.
6. Simulator integration; extract preflight; native serial/BLE adapters before hardware enablement.
7. Remaining imports/text/trace/settings migration and native update implementation.
8. Plugin manifests/discovery/version/permission foundation; marketplace deferred.
9. Build and smoke test each OS/architecture; signing/notarization and AppImage evaluation.
10. Full parity scenarios, comparative performance, representative customer projects, docs.

Do not replace the browser release or merge as a completed migration until every acceptance
criterion is verified. Packaging recipes or CI matrices do not prove platform support. Test
results, benchmark conditions and incomplete features are recorded in [validation.md](validation.md).
Never reuse the legacy updater for a Qt package: its archive allowlist/128 MiB size ceiling and
browser-launching replacement behavior are incompatible. File deltas need trusted versioned
manifests, per-file hashes, safe paths, staged atomic replacement, rollback and full-package fallback;
Qt/Python runtime changes may require full updates. User data must live
outside the installation tree. Checksums alone do not authenticate a publisher.
