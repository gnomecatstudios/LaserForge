# Native validation and remaining work

Status on 2026-11-14: **working experimental native editor, not a completed migration**.
Work is on `feature/native-desktop-migration`; main and the existing browser application are retained.
No physical laser was activated or connected during validation. No merge or production release
has been performed. Cross-platform packaging recipes are not cross-platform validation.

## Implemented and exercised

* Qt 6.8.3 Widgets window, native menus/file dialogs, docks and QSettings; existing red icon.
* QGraphicsView/Scene/QPainterPath viewport with canonical cubic vector and cached text outlines,
  raster images, layer visibility/order, indexed scene selection and cached geometry/images.
* Millimetre coordinates and affine transforms, all four machine origins, original core corner
  reorientation, display-independent CAM, cursor zoom, pan, grid, rulers and object/grid snapping.
* Rectangles/ellipses, selection/multiselection/marquee, drag, resize/rotate handles, editable
  X/Y/W/H fields and clickable dimension labels, alignment/distribution, context menus and nudges.
* Retained core history, project serializer/deserializer and migrations, `.olaser` ZIP and legacy
  JSON compatibility, asset round trips, DXF import and Qt-decoded image import using original bitmap bytes, embedded DPI/254 DPI fallback and bed fitting.
* Original machine/material catalogs behind the bridge, native layer settings/material picker,
  basic current-profile editing, G-code toolpath preview/export and safe GRBL simulation.
* Versioned, validated plugin metadata, dependencies and enable/disable preference foundation.
  Plugin code execution and hardware capabilities are not enabled.
* Separate native distribution recipe with bundled Python/Qt/Node, icon and dependency notices.

## Automated checks observed in this workspace

Linux x86_64, Python 3.12.14, Node 24.22.1, PySide6 6.8.3; headless Qt `offscreen`.

| Check | Result |
| --- | --- |
| Before native changes: existing Vitest suite | 120 files / 1,036 tests passed |
| With native bridge tests | 121 files / 1,051 tests passed (15 bridge tests) |
| Native Python/Qt suite | 39 passed after Windows/Mint/Pi scope update: 17 viewport, 10 plugin, 7 desktop integration, 1 atomic-file test, 4 packaging-target tests |
| TypeScript/Svelte check | 0 errors, 0 warnings |
| Existing browser Playwright subset | 37/37 passed: design 14, files 4, layout 6, simulated machine 8, updates 5 |
| ESLint | Passed |
| Browser production/PWA build | Passed; existing large-chunk and browser-externalization advisories |
| Library build/declarations | Passed from package working directory |
| Legacy portable Python tests | 23 run, 1 skipped (macOS), no failures |
| Existing portable branding checks | Passed for five checked archives (four runtime targets plus source) |
| Existing portable payload parity | **Failed:** tracked Windows ZIP does not contain current `og-image.png`; existing release payload is stale relative to source build |
| Go updater suite | Passed: 4 top-level tests plus 7 unsafe-path subtests using verified temporary Go 1.27.4 linux/amd64 |
| Native source CLI smoke | Passed, native window screenshot rendered |
| Linux frozen/extracted package smoke | Passed with PATH lacking Python/Node; bundled runtime and bridge used |
| Windows, Linux Mint and Raspberry Pi desktop/device tests | Not run; generic Linux container smoke is not Mint/Pi validation |

The parity failure is not concealed or fixed by rewriting shipped archives: browser sources,
public assets, library sources and legacy portable packaging remain unchanged from the audited
baseline. Legacy release artifacts need an intentional rebuild and all four-target validation
before their next publication. Nothing in this migration publishes or replaces those archives.
Go tests used a byte-identical copy of launcher sources plus production web assets in a temporary directory; no launcher files were changed.
The stale skipped macOS test in `portable/test_package.py` refers to a removed legacy function;
it is unrelated to the active Windows/Mint/Pi native target matrix; macOS is excluded.

The native bridge tests compare actual direct-core vector/raster job plans and G-code with bridge
results, exercise original ZIP/legacy JSON/assets/text outlines and DXF units, transforms/history/
materials/profiles, origin-corner round trips, malformed boundary inputs, and the unchanged GRBL
connection/runner on the original simulator. Native desktop tests exercise the real Qt shell and
bundled bridge together: dimension edits, undo, preview, file save/reopen, simulator, raster CAM,
alignment, layer assignment, pending edits, focused-editor save, packaged icon lookup and preview cancellation.

Compatibility coverage uses generated documents serialized by the original library and the
existing SVG/DXF/raster/golden fixtures. No user/customer `.olaser` project corpus was supplied;
representative real-world regression projects remain a release gate. No claim is made that every
legacy feature has been exercised in Qt or that all browser E2E scenarios have passed.

## Local Linux build artifact

`native/artifacts/LaserForge-Native-linux-x64-v0.2.5.tar.gz` (generated, not tracked),
121,213,900 bytes, built from final product commits `ccb7555`/`ddf8903`.
SHA-256: `3b7ddc4bb3704a9caf7a3d1c76d361bc969169a1fe945939afa47ec60ff08892`.
The extracted executable initialized and rendered offscreen with no Python/Node on PATH;
the included bridge matches the final build byte for byte, the red icon loads, runtime/license
resources are present, and QtWebEngine is absent. This validates startup in this container only.

## Measured performance

See [methodology and raw results](performance.md). In the initial shared-container CPU benchmark,
1k/10k vector redraw medians were 15.59/132.09 ms in Qt versus 9.60/46.40 ms in the existing Canvas
renderer. Qt indexed selection misses were cheaper; that is not an overall speed improvement.
Native redraw is a performance gap. Full application startup, total process-tree idle memory,
input-to-presentation latency, raster preview and CPU/GPU utilization are not yet measured.

## Incomplete features and compatibility limitations

| Area | Native limitation / migration path |
| --- | --- |
| Hardware and safety | No native serial/USB/BLE discovery or transmission, jog, framing, job cancel/stop or emergency controls. Keep legacy machine workflows. Extract all app-layer safety preflight, adapt transports, test faults/cancellation before enabling hardware. |
| Controllers | Native export/simulation currently GRBL G-code only. Existing Ruida RD and LaserPecker encode/control paths remain in browser/library; native panels/exports need adapters. |
| Text, shapes, paths | Cached text outlines render and compile unchanged; no native font loading, Unicode shaping/editor, parametric shape catalog UI, pen or node editing, tracing, boolean/outline/simplify UI. Retained algorithms are the migration path. |
| Imports/exports | No native SVG DOM adapter, G-code document import, print templates or RD/LaserPecker export UI. DXF currently uses core declared units/default mm; native unit chooser, unsupported-entity/warning dialogs and import placement parity remain. |
| Measurements | Selection dimension fields are editable; free measurement line length is read-only. |
| Layers/settings | Basic mode/speed/power/passes/material/visibility/output UI exists. Detailed fill, image dithering, air-assist/source/accessory/rotary/job-origin controls and custom material library UI remain. Project settings/unknown fields are retained by original serialization. |
| Profiles/preferences | Native current-profile/window/grid settings are separate. Browser IndexedDB/recent-file/autosave/profile/material preference migration and full preset management are incomplete. No crash recovery. |
| Machine origin | Core corner reorientation retained. Current-position export requires an explicit machine position; no live native position exists. Missing user origin is rejected. Auto-fit when switching to smaller bed is not migrated; inspect bounds and resolve blocking CAM warnings. |
| Clipboard/hotkeys | Implemented actions preserve corresponding shortcuts; copy/cut/paste, node/pen/text/trace/print and controller shortcuts/context actions remain in legacy. Qt StandardKeys/portable Ctrl strings provide native platform mapping; target-desktop keyboard testing remains. |
| Performance | Full snapshots/base64 asset transfer and synchronous Qt raster decode/RGBA preparation can freeze UI for large images. Core CAM runs outside GUI process. Add delta snapshots, bounded worker decode/cache and profile-driven render optimization. |
| File sizes | Native input capped at 64 MiB; IPC capped at 128 MiB. Larger projects need streaming/incremental asset protocol, not silent truncation. |
| Plugins | Metadata-only foundation; no extension execution host, panels/tools/import registration, package installer/updater or marketplace. Unrestricted Python cannot be treated as sandboxed; future broker must enforce capabilities out of process. |
| Updates | Existing browser/PWA/portable updates untouched. Native automatic/incremental updates, signed manifests, full fallback/rollback/startup health checks and update UI remain unimplemented. Do not use legacy updater for Qt packages. |
| Packaging | Linux tar.gz tested only in this glibc 2.41 container; Ubuntu/Mint desktop compatibility and AppImage pending. Windows portable ZIP and ARM64 build recipes unexecuted; actual Mint/Pi native validation remains. Pi ARM32 stays on the legacy browser distribution because pinned Qt/Node runtimes lack the required packages. |

## Next independently reviewable stages

1. Expand native editing/import/text/layout parity and a representative `.olaser` corpus; expose
   preserved laser/job settings through complete native panels.
2. Extract shared mandatory safety/preflight from Svelte; introduce native serial/BLE transports
   behind existing drivers; validate disconnect/hold/cancel/stop faults in simulation.
3. Optimize measured redraw and image preparation, then collect real desktop/high-DPI benchmarks.
4. Implement separate native settings migration and authenticated update/staging/rollback channel.
5. Execute target-OS CI and interactive checks, native artifact signing, AppImage work, and full
   feature/output regression matrix before a production PR/merge approval.

## Acceptance status

The native primary interface requirement is demonstrated by the experimental editor, and the
architecture, plugin metadata foundation, test harnesses and current documentation are delivered.
Full feature parity, real-world project coverage, native machine integration, validated desktop
builds on all requested platforms, native updating, and release-level performance remain open.
The migration must not be merged as complete or replace existing downloads at this stage.
