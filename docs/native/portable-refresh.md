# Portable refresh on native-render-version

Source revision: `f048312`. Version: `0.2.5` (branch refresh; not a new public release).

Rebuilt and committed under `portable/downloads`:

- Windows x64 browser portable ZIP.
- Linux x64 browser portable ZIP (Mint is a target; actual Mint desktop validation still required).
- Raspberry Pi OS ARM64 and ARM32 browser portable ZIPs.
- Portable source ZIP and regenerated `SHA256SUMS.txt`.

All four executables embed the same 36 production assets and current offline/update companions.
The original launcher remains in these ZIPs because native feature parity is incomplete.
Native code is not embedded into browser portable executables or their source ZIP.

Also rebuilt `native/artifacts/LaserForge-Native-linux-x64-v0.2.5.tar.gz` as a separate
experimental Qt application. This generated artifact is not tracked by Git. Native Windows/Pi
builds still require their target environments and are not delivered by this refresh.

Validation completed:

- Production web build and native bridge build.
- Portable parity and branding checks across every archive, including embedded Windows icon.
- ZIP integrity, SHA-256, ELF/PE architecture and embedded source-revision checks.
- 23 portable Python tests (one platform skip), plus Go updater tests.
- Extracted Linux browser portable started with `--no-browser`; served exact current HTML,
  logo and social image and correct revision without opening a browser or device.
- Extracted native Linux application started offscreen with no Python/Node on PATH; bundled
  bridge equals the latest build, and no QtWebEngine dependency is included.

No physical device was connected, moved or fired. Windows/Pi execution and Mint desktop behavior
were not tested in this Linux container. No GitHub release was published, no main merge occurred,
and installed users will not receive this same-version branch refresh through automatic updates.
Existing user projects and settings were not modified.
