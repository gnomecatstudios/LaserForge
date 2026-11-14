# Runtime notices

LaserForge and libopenlaser: MIT, copyright 2026 Anam Ahmed. Copies are included.

The distribution uses dynamically loaded Qt 6 / PySide6 libraries under their
applicable LGPLv3/GPLv3 or commercial terms, and Shiboken6. License texts from the
installed Python wheels are copied into `notices/`. Qt source and license details:
https://www.qt.io/licensing/open-source-lgpl-obligations and https://code.qt.io/.
The onedir format preserves shared libraries; do not replace it with a locked or
single-executable distribution without reviewing the applicable obligations.
Qt 6.8.3 LGPL/GPL/exception texts are supplied in `Qt-LGPL-GPL/` because the
PySide6 6.8.3 wheels do not carry those texts. They are copied unmodified from
https://github.com/qt/qtbase/tree/v6.8.3/LICENSES.

Node.js includes its MIT license and third-party notices in `Node-LICENSE.txt`.
The build records the exact Node version and retrieves its corresponding upstream
LICENSE if a local license is unavailable. Source: https://github.com/nodejs/node.

The libopenlaser JavaScript bridge bundles its existing dependencies. Their
installed license files are copied from node_modules; `runtime-versions.json`
records the runtime versions. These include Clipper, HarfBuzz, OpenType.js,
fflate and nanoid according to the checked-in package lock. Keep all notices when
redistributing the application.

Review notices against the actual distributable before a public release. This
experimental packaging recipe does not constitute a completed license review.
