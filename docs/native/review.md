# Native editor review

Active branch: `native-render-version`. Native Qt editor development continues alongside the
unchanged browser release. The default browser launcher has not been switched. Do not merge as a
completed migration or publish experimental packages over the stable downloads.

## Architecture assessment and plan

The audited repository uses Svelte/TypeScript and Canvas 2D for the interface; a Go static-file
server opens an external browser for portable startup. `libopenlaser` already separates geometry,
project operations/history/serialization, CAM, controller drivers and simulators from the UI.
IndexedDB, Web Serial/Bluetooth, SVG DOM parsing and image/font loading are browser adapters.

Use PySide6 Qt Widgets/QGraphicsView/QPainterPath for every native surface and private asynchronous
Node IPC for the existing core. No browser or local web server is needed for native startup.
Physical coordinates remain in millimetres, independent of Qt display transforms. Keep adapting
browser boundaries, then port the remaining tools/panels and full safety preflight before exposing
hardware. Build/test Windows and compatible Linux/Pi targets on those environments before claiming
support. The detailed architecture and original audit are in [migration.md](migration.md).

## Feature inventory verified against source

| Existing functionality / evidence | Native state |
| --- | --- |
| Rectangles/ellipses, cubic paths; canvas/tools.ts and project/shapes.ts | Native drawing, cached cubic geometry and handles |
| Selection/multiselection/marquee, transform/resize/rotate; canvas/handles.ts | Native implementations, physical dimension fields and clickable W/H labels |
| Layers, order, visibility, undo/redo; project/operations.ts and history.ts | Original core retained, native basic controls |
| Zoom/pan, rulers/grid, object/grid snapping; canvas/viewport.ts and guides.ts | Native viewport; offscreen scales 1/1.5/2 tested |
| Clipboard, context actions and shortcuts; edit-actions.ts and shortcuts.ts | Native object copy/cut/paste with layers/assets; supported commands use native menus and keys |
| File drops; workspace/DropZone.svelte | Single local project/DXF/raster drop; unsupported formats reported |
| Simplification; workspace/ToolRail.svelte and geometry/simplify.ts | Original transformed-mm algorithm, native tolerance dialog and undo; preview remains missing |
| Text/font/path layout; text-actions.ts, libopenlaser/fonts | Saved outlines display/burn; native text/font editing and text-on-path controls missing |
| Pen/node editing, outline/union, tracing and parametric catalog | Browser implementations retained; native controls still missing |
| Fillets and chamfers | No named fillet/chamfer editing implementation found by case-insensitive source/test search. Rounded-rectangle path generation exists; imported curves remain exact. No arbitrary corner tool claimed. |
| Existing .olaser ZIP/JSON and assets; project/serialize.ts | Original serialization retained; native save/reopen and clipboard round trips tested |
| SVG/DXF/raster/G-code inputs, print and controller exports | DXF/raster native adapters exist; SVG/G-code document import, print and RD/LaserPecker UI remain missing |
| Settings/machine/material profiles | Core catalogs retained; basic native settings separate from browser IndexedDB. Full settings migration missing; browser data untouched |
| Device connection/preflight/stop; machine.svelte.ts and libopenlaser/machine | Legacy controls preserved, native simulator only. Real transport/preflight/stop UI migration remains essential |
| Portable updates | Legacy updater retained/tested; native update channel incomplete |

## Editing-stage validation

Regression tests cover clipboard assets/fresh IDs/layer preservation and atomic undo, simplification
against the original algorithm, actual Qt keyboard/context actions, dropped-project save/reopen,
and physical rendering at multiple display scales. Test only simulated devices. Core compilation,
serialization and expensive simplification run outside the GUI process. Large file reads, image
decode and base64 preparation still have GUI-thread costs; background adapters remain necessary.

The Linux container package can be smoke-tested; it is not Mint/Pi hardware validation. Windows and
Pi packaging, AppImage, missing tools, native updates, real-world project corpus and hardware safety
integration remain open. See [validation.md](validation.md) for measured results and limitations.

Run from source using [development.md](development.md): install Python dependencies in a virtual
environment, `pnpm install --frozen-lockfile`, `pnpm native:bridge`, then
`python -m laserforge_native`. No default-launcher or release-publication change is included.
