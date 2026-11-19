<script lang="ts">
  /**
   * The original image over a transparency checkerboard. With picking on, a click keys the color
   * under the pointer and a drag keys the whole range of colors it crosses; the current selection
   * is shown as a highlight, on its own, or cut out of the rest. Picks follow the panel's
   * Add/Subtract switch; Alt picks as subtract and Shift as add, for that pick only.
   */
  import type { KeyMode, KeyPoint } from 'libopenlaser/cam';
  import type { Separation } from './separation.svelte';

  let {
    separation,
    name,
    picking,
    onshare,
  }: {
    separation: Separation;
    name: string;
    /** Clicks pick colors. */
    picking: boolean;
    /** Share of the image selected, 0..1, whenever it changes. */
    onshare?: (share: number) => void;
  } = $props();

  let canvas = $state<HTMLCanvasElement | null>(null);
  const weights = $derived(separation.weights());

  $effect(() => onshare?.(separation.share(weights)));

  /** Highlight for selected pixels: a vivid magenta that reads on photos of any color. */
  const MARK = [255, 0, 170];
  const MARK_STRENGTH = 0.6;

  $effect(() => {
    const target = canvas;
    const source = separation.preview;
    const w = weights;
    if (!target || !source || !w) return;
    const { width, height, data } = source;
    target.width = width;
    target.height = height;
    const show = picking ? separation.show : 'highlight';
    const out = new Uint8ClampedArray(width * height * 4);
    const cell = Math.max(4, Math.round(Math.min(width, height) / 40));
    for (let y = 0, i = 0; y < height; y++) {
      const row = Math.floor(y / cell);
      for (let x = 0; x < width; x++, i++) {
        const p = i * 4;
        const checker = (Math.floor(x / cell) + row) & 1 ? 204 : 245;
        const weight = w[i] / 255;
        let a = data[p + 3] / 255;
        if (show === 'selection') a *= weight;
        else if (show === 'rest') a *= 1 - weight;
        let r = data[p] * a + checker * (1 - a);
        let g = data[p + 1] * a + checker * (1 - a);
        let b = data[p + 2] * a + checker * (1 - a);
        if (show === 'highlight' && weight > 0) {
          const m = MARK_STRENGTH * weight;
          r = r * (1 - m) + MARK[0] * m;
          g = g * (1 - m) + MARK[1] * m;
          b = b * (1 - m) + MARK[2] * m;
        }
        out[p] = r;
        out[p + 1] = g;
        out[p + 2] = b;
        out[p + 3] = 255;
      }
    }
    target.getContext('2d')?.putImageData(new ImageData(out, width, height), 0, 0);
  });

  /** Pointer → image point (0..1), allowing for the letterboxing of `object-fit: contain`. */
  function toImage(event: PointerEvent): KeyPoint | null {
    const source = separation.preview;
    if (!canvas || !source) return null;
    const rect = canvas.getBoundingClientRect();
    const scale = Math.min(rect.width / source.width, rect.height / source.height);
    const w = source.width * scale;
    const h = source.height * scale;
    const x = (event.clientX - rect.left - (rect.width - w) / 2) / w;
    const y = (event.clientY - rect.top - (rect.height - h) / 2) / h;
    return x >= 0 && x <= 1 && y >= 0 && y <= 1 ? { x: Math.min(x, 0.9999), y: Math.min(y, 0.9999) } : null;
  }

  let stroke: KeyPoint[] | null = null;
  let strokeMode: KeyMode = 'add';

  /** Modifiers held now, so the cursor shows the mode the next pick will use. */
  let modifiers = $state({ alt: false, shift: false });
  const modeFor = (m: { altKey: boolean; shiftKey: boolean }): KeyMode =>
    m.shiftKey ? 'add' : m.altKey ? 'subtract' : separation.mode;
  const cursorMode = $derived(modeFor({ altKey: modifiers.alt, shiftKey: modifiers.shift }));
  const track = (event: KeyboardEvent | PointerEvent) =>
    (modifiers = { alt: event.altKey, shift: event.shiftKey });

  function down(event: PointerEvent) {
    if (!picking || event.button !== 0) return;
    const point = toImage(event);
    if (!point) return;
    // Alt-click would otherwise focus the browser menu on some systems.
    if (event.altKey) event.preventDefault();
    stroke = [point];
    strokeMode = modeFor(event);
    canvas?.setPointerCapture(event.pointerId);
  }

  function move(event: PointerEvent) {
    track(event);
    if (!stroke) return;
    const point = toImage(event);
    if (point) stroke.push(point);
  }

  function up() {
    if (!stroke) return;
    const points = stroke;
    stroke = null;
    // A small wobble during a click is still a click.
    const first = points[0];
    const moved = points.some((p) => Math.hypot(p.x - first.x, p.y - first.y) > 0.01);
    separation.pick(moved ? points : [first], strokeMode);
  }
</script>

<svelte:window onkeydown={track} onkeyup={track} onblur={() => (modifiers = { alt: false, shift: false })} />

<div class="original" role="img" aria-label="Original {name}">
  <canvas
    bind:this={canvas}
    class:picking
    class:subtract={picking && cursorMode === 'subtract'}
    data-pick-mode={picking ? cursorMode : undefined}
    onpointerdown={down}
    onpointermove={move}
    onpointerup={up}
    onpointercancel={() => (stroke = null)}
    data-testid="bitmap-original"
  ></canvas>
</div>

<style>
  .original {
    width: 100%;
    height: 100%;
    min-height: 0;
    display: flex;
  }

  canvas {
    max-width: 100%;
    max-height: 100%;
    width: 100%;
    height: 100%;
    object-fit: contain;
    touch-action: none;
  }

  canvas.picking {
    cursor: crosshair;
  }

  /* A crosshair with a minus badge: picks take colors away from the selection. */
  canvas.picking.subtract {
    cursor:
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24'%3E%3Cg stroke-linecap='square'%3E%3Cpath d='M9 1v6M9 11v6M1 9h6M11 9h6' stroke='white' stroke-width='3'/%3E%3Cpath d='M9 1v6M9 11v6M1 9h6M11 9h6' stroke='black' stroke-width='1'/%3E%3C/g%3E%3Crect x='13' y='16' width='10' height='5' rx='1' fill='white'/%3E%3Crect x='14' y='17.5' width='8' height='2' fill='rgb(200,30,30)'/%3E%3C/svg%3E")
        9 9,
      crosshair;
  }
</style>
