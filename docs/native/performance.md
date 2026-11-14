# Native renderer performance work

These harnesses establish repeatable measurements, not a claim that the migration improves
application performance. They exercise the existing renderer directly and the native viewport
directly with the same deterministic schema-1 project. They do not start a machine or alter user
preferences.

## Reproduce

From the repository root, install development dependencies and PySide6 as documented in the
native setup guide, then generate the shared workloads:

```sh
python native/benchmarks/fixture.py --objects 1000 > /tmp/laserforge-1000.json
python native/benchmarks/fixture.py --objects 10000 > /tmp/laserforge-10000.json
pnpm dev --host 127.0.0.1
```

In another terminal:

```sh
CHROMIUM_PATH=/usr/bin/chromium node native/benchmarks/browser.mjs /tmp/laserforge-1000.json
QT_QPA_PLATFORM=offscreen python native/benchmarks/native.py /tmp/laserforge-1000.json
CHROMIUM_PATH=/usr/bin/chromium node native/benchmarks/browser.mjs /tmp/laserforge-10000.json
QT_QPA_PLATFORM=offscreen python native/benchmarks/native.py /tmp/laserforge-10000.json
```

Omit `CHROMIUM_PATH` to use a Playwright-installed Chromium. Windows PowerShell users should set
environment variables using `$env:NAME = 'value'` and choose a local fixture path. Fixture generation
requires only Python's standard library. It lays out closed, non-overlapping rectangles on a
400 × 400 mm bed with a fixed red line layer. Generated projects contain no random IDs, dates or
external assets. Use a fresh process for each workload.

The browser harness imports the actual `src/app/canvas/scene-render.ts`, `hit-test.ts` and viewport
functions through Vite. It runs five warmups followed by 30 redraw, zoom/pan redraw and selection-miss
samples at 1440 × 900, device pixel ratio 1. Canvas readback forces drawing completion. The Qt
harness paints the actual QGraphicsView into a CPU QImage of the same size after five warmups,
then measures 30 samples. Qt retains its standard scene index; browser hit-testing follows the
existing renderer's candidate scan. A deliberate miss near the viewport corner exposes lookup
cost without selecting arbitrary tiny objects.

## What these numbers mean

* Redraw is CPU wall time through a drawing completion boundary. It excludes event-loop scheduling,
  input latency, compositor presentation and display scanout.
* Zoom/pan samples redraw after small alternating view changes. Browser zoom anchors at viewport
  center; Qt uses its native zoom helper. This is a workload comparison, not pixel-identical frames.
* Scene construction and first draw differ: Qt creates scene items, browser creates Path2D lazily.
  They must be reported separately rather than described as equivalent startup measurements.
* Harness startup excludes parts of shell and runtime launch overhead and includes development
  module loading. It is **not full LaserForge application startup**.
* Native RSS is current resident memory of the isolated Qt benchmark process on Linux. Browser JS
  heap is a different metric and must not be compared as total idle application memory. Neither
  includes a native Node sidecar or the complete app.
* No GPU utilization or hardware-acceleration advantage is measured. Offscreen rendering is not a
  desktop GPU benchmark. CPU utilization, input-to-presentation latency and full application idle
  memory need OS profiling on real supported hardware.
* Raster engraving preview and full native job-preview migration remain incomplete, so no raster
  preview speed comparison is claimed. Add equivalent raster workloads only when both paths execute
  the same preview pipeline.

## Baseline regression checks

On the Linux development container on 2026-11-14, Node 24.22.1 and the frozen pnpm lockfile:

| Check | Observed result |
| --- | --- |
| Existing `pnpm test` | 120 files, 1,036 tests passed; 57.20 s |
| Existing `pnpm typecheck` | 0 errors, 0 warnings |
| Existing `pnpm build` | Passed; Vite/PWA output generated; existing large-chunk advisory |

These baseline counts precede the added native bridge tests. Keep later suite totals separate.
No Windows, macOS or Raspberry Pi performance measurements were made in this container.

After the native additions, the existing browser Playwright subset passed **37/37 tests**
in 132.13 seconds (0 skipped, 0 flaky): `design.spec.ts` (14), `files.spec.ts` (4),
`layout.spec.ts` (6), `machine.spec.ts` (8), and `updates.spec.ts` (5). It used the
production Vite/PWA build on port 5191, installed Chromium 156, two workers, and a
temporary external configuration selecting `/usr/bin/chromium`. The repository's
Playwright configuration and browser application source were unchanged. Machine cases
used existing virtual connections; no physical device was opened. This subset validates
continued browser operation, not complete native feature parity or all browser scenarios.

## Initial measured renderer comparison

Run on 2026-11-14 in a shared Linux x86_64 container (kernel 6.18.57, glibc 2.41,
Intel Xeon Platinum 8573C virtual CPU), Python 3.12.14, PySide6 6.8.3, Node 24.22.1,
headless system Chromium 156.0.8078.79. No dedicated CPU affinity, GPU access or isolated
performance runner was used. Other migration work was running in the same environment.
Treat the samples as initial diagnostics and rerun on desktop hardware before making
release performance decisions.

| Objects | Renderer | Redraw median / p95 (ms) | Zoom/pan redraw median / p95 (ms) | Selection miss median / p95 (ms) |
| --- | --- | --- | --- | --- |
| 1,000 | Existing Canvas 2D | 9.60 / 15.50 | 9.10 / 14.50 | 13.30 / 15.40 |
| 1,000 | Native Qt CPU | 15.59 / 24.68 | 15.23 / 21.74 | 0.010 / 0.015 |
| 10,000 | Existing Canvas 2D | 46.40 / 104.60 | 47.80 / 98.20 | 62.50 / 137.70 |
| 10,000 | Native Qt CPU | 132.09 / 159.01 | 131.63 / 164.93 | 0.015 / 0.028 |

The initial native implementation redraws more slowly in this CPU workload. The scene's
indexed miss lookup is substantially cheaper than the existing full candidate scan, but this
does not measure a full selection interaction or prove a general rendering improvement.
Profile Python per-item paint callbacks, path batching and viewport caching before considering
OpenGL. Preserve accurate physical geometry and editing behavior through any optimization.

Native scene construction plus first draw measured 60.13 ms (1k) and 574.09 ms (10k). Browser
first draw measured 19.20 ms and 85.10 ms, excluding fixture transfer and project setup. These
startup paths do different work. Harness startup was 234.46/802.77 ms for Qt and
1,515.13/996.08 ms for Chromium, **not application launch times**. Native benchmark RSS was
82,976,768 / 179,007,488 bytes; browser JS heap was 16,011,435 / 73,951,647 bytes. Do not
compare these as application memory usage.

Raw observations are retained in `native/benchmarks/results/laserforge-{browser,native}-{1000,10000}.json`.
The generated workload SHA-256 values (including the generator's trailing newline) were:

```text
1000:  95246a2bc554235d90fa60f03e8237fec84da8f9e52b654ebc9cbd17ea224535
10000: b6245de0c87301677d657913072d519197cbb5871e29bbd23ed18ad5d9878de5
```

## Remaining benchmark coverage

Before replacing the browser release, collect full cold/warm application startup and total process
tree idle memory; physical-device zoom/pan input latency; mixed large path/text/image projects;
hit and miss selection; raster engraving preview; CPU and GPU profiles; high-DPI (1×/1.5×/2×)
behavior. Record OS, CPU/GPU, driver, renderer backend, power mode, dependency versions, sample
counts, median/p95, workload hash and whether all data was cached. Use identical project/settings
fixtures and preserve raw outputs. Do not infer production support from this offscreen harness.
