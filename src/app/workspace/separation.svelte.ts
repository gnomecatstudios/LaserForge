/**
 * Color separation state for Bitmap mode: the colors picked on the image, how they match, and a
 * small decoded copy of the image to preview the selection on. Shared by the image canvas (where
 * colors are picked) and the Separate panel (where the selection is tuned and applied).
 */
import {
  colorAt,
  downscaleRaster,
  edgeSelection,
  oklabImage,
  selectionWeights,
  selectedShare,
  spectrumKey,
} from 'libopenlaser/cam';
import type { ColorKey, ColorSelection, KeyPoint, RasterSource, Rgb } from 'libopenlaser/cam';
import { decodeImage } from 'libopenlaser/import';

/** Pixels in the interactive preview; the full image is only processed when a change is applied. */
export const PREVIEW_PIXELS = 1_000_000;
/** Seeds kept per drag: enough to cover a long stroke across an area. */
const SEEDS_PER_DRAG = 32;

export type SeparationShow = 'highlight' | 'selection' | 'rest';

export const DEFAULT_TOLERANCE = 15;
export const DEFAULT_SOFTNESS = 10;

export class Separation {
  keys = $state<ColorKey[]>([]);
  /** Where each pick was made, for "Connected areas only". */
  seeds = $state<KeyPoint[]>([]);
  tolerance = $state(DEFAULT_TOLERANCE);
  softness = $state(DEFAULT_SOFTNESS);
  connected = $state(false);
  invert = $state(false);
  regions = $state(false);
  show = $state<SeparationShow>('highlight');
  /** A full-size separation is running. */
  busy = $state(false);

  /** The asset the preview below was decoded from. */
  assetId = $state<string | null>(null);
  preview = $state.raw<RasterSource | null>(null);
  private lab: Float32Array | null = null;
  /** "Connected areas only" was switched on by Select background, not by hand. */
  private autoConnected = false;
  private loading: string | null = null;

  get selection(): ColorSelection {
    return {
      keys: this.keys.map((k) => ({ stops: k.stops.map((s) => [s[0], s[1], s[2]] as Rgb) })),
      tolerance: this.tolerance,
      softness: this.softness,
      seeds: this.connected ? this.seeds.map((p) => ({ x: p.x, y: p.y })) : null,
      invert: this.invert,
    };
  }

  /** Nothing would be selected. */
  get empty(): boolean {
    return this.keys.length === 0 && !this.invert;
  }

  /** Decodes a small copy of the asset for previews; a newer request wins. */
  async load(assetId: string, blob: Blob): Promise<void> {
    if (this.assetId === assetId || this.loading === assetId) return;
    this.loading = assetId;
    const decoded = await decodeImage(blob);
    if (this.loading !== assetId) return;
    this.loading = null;
    this.preview = downscaleRaster(decoded, PREVIEW_PIXELS);
    this.lab = null;
    this.assetId = assetId;
  }

  unload(): void {
    this.loading = null;
    this.assetId = null;
    this.preview = null;
    this.lab = null;
  }

  /** Selection strength per preview pixel, 0..255 (all zero when nothing is picked). */
  weights(): Uint8ClampedArray | null {
    const source = this.preview;
    if (!source) return null;
    const selection = this.selection;
    if (selection.keys.length === 0 && !selection.invert)
      return new Uint8ClampedArray(source.width * source.height);
    this.lab ??= oklabImage(source);
    return selectionWeights(source, selection, this.lab);
  }

  share(weights: Uint8ClampedArray | null): number {
    return this.preview && weights ? selectedShare(this.preview, weights) : 0;
  }

  /**
   * Adds a pick from a click (one point) or a drag (the points along it). A drag keys the whole
   * spectrum of colors it crossed.
   */
  pick(points: KeyPoint[]): boolean {
    const source = this.preview;
    if (!source || points.length === 0) return false;
    const colors = points.map((p) => colorAt(source, p)).filter((c): c is Rgb => c !== null);
    const key = colors.length === 1 ? { stops: colors } : spectrumKey(colors);
    if (!key) return false;
    this.keys = [...this.keys, key];
    const step = Math.max(1, Math.ceil(points.length / SEEDS_PER_DRAG));
    this.seeds = [...this.seeds, ...points.filter((_, i) => i % step === 0 || i === points.length - 1)];
    return true;
  }

  removeKey(index: number): void {
    this.keys = this.keys.filter((_, i) => i !== index);
    if (this.keys.length === 0) this.seeds = [];
  }

  /** Keys the main colors around the image's edge, limited to the areas touching it. */
  selectBackground(): boolean {
    if (!this.preview) return false;
    const auto = edgeSelection(this.preview);
    if (auto.keys.length === 0) return false;
    this.keys = auto.keys;
    this.seeds = auto.seeds ?? [];
    if (!this.connected) this.autoConnected = true;
    this.connected = true;
    this.invert = false;
    return true;
  }

  /** Forgets the picks, keeping how they match. */
  clear(): void {
    this.keys = [];
    this.seeds = [];
    this.invert = false;
    if (this.autoConnected) this.connected = false;
    this.autoConnected = false;
  }

  setConnected(on: boolean): void {
    this.connected = on;
    this.autoConnected = false;
  }
}

/** CSS color for a key's swatch: a flat color, or a gradient through a spectrum's stops. */
export function keySwatch(key: ColorKey): string {
  const css = (c: Rgb) => `rgb(${c[0]} ${c[1]} ${c[2]})`;
  return key.stops.length === 1
    ? css(key.stops[0])
    : `linear-gradient(90deg, ${key.stops.map(css).join(', ')})`;
}
