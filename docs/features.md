# Current features and future work

Baseline: **Laser Forge v0.2.7**, published November 15, 2026 (Pacific time).
This inventory describes current source. Arc text, rotated engraving, Bézier simplification
and linked guide updates are source additions; portable downloads remain at the baseline
until the next verified four-platform release.

## Available now

| Area                      | Features in source                                                                                                                                                                                                                | Boundaries                                                                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Application and platforms | Browser-based Canvas renderer; offline PWA; portable launchers and update popup; light/dark themes                                                                                                                                | Portable targets: Windows x64, Linux x64, Raspberry Pi ARM64 and ARM32. Machine access depends on browser APIs.                                                                  |
| Import                    | SVG, DXF, raster images, drag-and-drop; existing G-code sender                                                                                                                                                                    | SVG text should be converted to paths before import. DXF text and hatches require outlines.                                                                                      |
| Drawing and vectors       | Rectangles, ellipses, parametric shape library, pen paths, node and Bézier-handle editing, node insertion, polyline and Bézier simplification, selection outline                                                                  | Compatible Bézier segments merge within the requested tolerance. Open paths remain open.                                                                                         |
| Canvas editing            | Cut, Copy, Paste, Duplicate, Delete; selection-aware right-click menu; keyboard navigation and shortcuts                                                                                                                          | Paste uses the editor clipboard. Locked operands cannot be changed by Boolean actions.                                                                                           |
| Boolean geometry          | Union, Subtract, Intersect, Exclude (XOR); multiple operands, transformed paths, compound holes and disconnected regions                                                                                                          | Requires at least two visible, unlocked, closed vector objects. Subtract uses selection order: the first object is the base. Empty results remove operands in one undoable edit. |
| Text                      | In-place text editing; Google, uploaded and installed fonts; complex-script shaping; text-to-paths; editable text on a linked path; signed arc text slider                                                                        | Text-to-paths needs complete outlines. New path text follows guide edits; deleting a guide retains the last baseline. Old snapshots remain compatible.                           |
| Placement and layout      | Numeric position, dimensions and angle; anchor picker; smart guides; measurement; alignment and distribution; rectangular and circular arrays                                                                                     | Alignment can target selection bounds, the last-selected object or the bed.                                                                                                      |
| Layers and CAM            | Line cutting/scoring, fill engraving, image engraving, speed/power/passes, kerf, cross-hatch, overscan, material presets, image tracing and dithering                                                                             | Image rotation is supported; raster scan direction is relative to the image. Test material settings on scrap.                                                                    |
| Preview and output        | Burn/travel preview, playback and scrubbing, time estimates, G-code export, Ruida .rd export, 1:1 vector printing                                                                                                                 | Ruida support is file export; direct live Ruida control is not implemented. Estimates depend on machine settings.                                                                |
| Machines and jobs         | GRBL-family Web Serial control, virtual machine, machine detection/presets, LaserPecker connections, rotary/slide setup, laser-source selection, framing, pause/resume/stop, overrides, jog/home, console, device settings backup | LaserPecker capabilities vary by model and connection. Bluetooth and LP2/LP3 USB line layers engrave rather than cut.                                                            |
| Project and recovery      | .olaser projects with assets, autosave/session restore, undo/redo, machine profiles, preflight and alarm help                                                                                                                     | Browser autosave and font storage belong to that browser/profile.                                                                                                                |

## New in v0.2.7

- Canvas context menu with Cut, Copy, Paste, Duplicate, Boolean and Delete.
- Subtract, Intersect and Exclude (XOR), alongside the existing Union tool.
- First-selected subtraction base, named in the submenu tooltip.
- Shared geometry validation, preserved layers/properties, and atomic undo/redo,
  including empty Boolean results.
- Central shortcuts shown in the menu and shortcut help:

| Union        | Subtract     | Intersect    | Exclude      |
| ------------ | ------------ | ------------ | ------------ |
| Ctrl+Shift+U | Ctrl+Shift+D | Ctrl+Shift+I | Ctrl+Shift+X |

Path simplification, text-to-paths, alignment/distribution, arrays and text-on-path
were already available before v0.2.7. They are current features, not future plans.
This inventory update also adds their missing registry/tour coverage.

## Updates and verification still needed

These are follow-ups, not missing Boolean features.

| Follow-up                          | Status / next action                                                                                                                                                                                                                                             |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| npm library publication            | libopenlaser 0.1.3 publication failed with registry E404/permissions. An npm package owner must configure publishing access/trusted publishing for this repository, then rerun the existing publish workflow. Portable v0.2.7 already embeds the updated source. |
| Real-machine and target validation | Run the [manual hardware checklist](progress.md#manual-test-checklist-real-grbl-laser) and native launch/update checks on all four supported platforms. Automated packaging checks do not establish physical-machine behavior.                                   |
| Tour and feature inventory         | This source update registers six previously omitted capabilities and refreshes the tour. The tour copy will reach portable users in the next verified four-platform release.                                                                                     |
| Documentation maintenance          | Keep this inventory, the README, feature registry and tour aligned when features ship. Older packaging decisions are historical; use the current README for downloads and platform support.                                                                      |

## Proposed future work

No approved, scheduled product roadmap or open GitHub issues were found during this
review. The following proposals address observed limitations; they are not delivery
commitments. Priority is suggested, with no assigned release dates.

| Suggested priority | Proposal                     | What would need implementation and validation                                                                                            |
| ------------------ | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Explore            | Direct Ruida machine control | A separate transport/protocol integration, connection lifecycle and physical hardware validation. Existing .rd export remains available. |

No native desktop renderer work or additional platform targets are included here.

## Verification baseline

For the v0.2.7 implementation: 1,067 unit tests and 16 relevant Playwright tests
passed; type checks, lint, production/library builds and portable parity/branding
checks passed. Portable Python tests ran 23 tests with one platform-specific skip.
All four public platform ZIPs and the source archive passed SHA-256 verification.
See the [release](https://github.com/gnomecatstudios/LaserForge/releases/tag/v0.2.7)
and [implementation commit](https://github.com/gnomecatstudios/LaserForge/commit/9206a40).
