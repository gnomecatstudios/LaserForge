<script lang="ts">
  /**
   * Separate tab of Bitmap mode: key colors out of an image (a backdrop, a sky, one object among
   * several) and move them to a layer of their own, erase them, or keep only them. Repeating it
   * peels a picture into foreground, midground and background layers that stack back together.
   */
  import Layers from '@lucide/svelte/icons/layers';
  import Eraser from '@lucide/svelte/icons/eraser';
  import Crop from '@lucide/svelte/icons/crop';
  import ScanSearch from '@lucide/svelte/icons/scan-search';
  import X from '@lucide/svelte/icons/x';
  import NumberField from '$lib/ui/NumberField.svelte';
  import Toggle from '$lib/ui/Toggle.svelte';
  import { toast } from '$lib/ui/toasts.svelte';
  import { reportError } from '$lib/ui/errors';
  import { makeId } from 'libopenlaser/project';
  import type { ImageObject, Layer } from 'libopenlaser/project';
  import { editor } from '../state/editor.svelte';
  import { separateInWorker } from '../lib/cam-client';
  import { placeSeparation, type SeparateMode } from '../lib/separate-place';
  import { keySwatch, type Separation, type SeparationShow } from './separation.svelte';

  let { separation, image, share }: { separation: Separation; image: ImageObject; share: number } = $props();

  const asset = $derived(editor.project?.assets[image.assetId]);
  const ready = $derived(!separation.empty && share > 0 && !separation.busy && !image.locked);
  const percent = $derived(share > 0 && share < 0.001 ? '<0.1' : (share * 100).toFixed(share < 0.1 ? 1 : 0));

  const SHOW: Array<[SeparationShow, string]> = [
    ['highlight', 'Highlight'],
    ['selection', 'Selection'],
    ['rest', 'Rest'],
  ];

  function newLayer(source: Layer): Layer {
    const fresh = editor.makeLayer('image');
    // Same engraving settings as the image's layer; its own name and color to tell them apart.
    return { ...source, id: fresh.id, name: fresh.name, color: fresh.color };
  }

  async function apply(mode: SeparateMode) {
    if (!asset || !ready) return;
    const assetId = asset.id;
    const imageId = image.id;
    separation.busy = true;
    try {
      const result = await separateInWorker({
        assetId,
        blob: asset.data,
        selection: $state.snapshot(separation.selection),
        regions: separation.regions && mode !== 'remove',
      });
      const now = editor.project?.objects.find((o) => o.id === imageId);
      if (!now || now.kind !== 'image' || now.assetId !== assetId) {
        toast.warning('The image changed while it was being separated. Try again.');
        return;
      }
      if (result.pieces.length === 0) {
        toast.info('Nothing in the image matches the picked colors.');
        return;
      }
      if (mode === 'keep' && !result.rest) {
        toast.info('The selection already covers the whole image.');
        return;
      }
      let outcome: ReturnType<typeof placeSeparation> | null = null;
      editor.commit((p) => {
        outcome = placeSeparation(p, imageId, result, mode, makeId, newLayer);
        return outcome.project;
      });
      editor.sealHistory();
      separation.clear();
      const done = outcome as ReturnType<typeof placeSeparation> | null;
      if (!done) return;
      if (mode === 'layer') {
        const layer = editor.project?.layers.find((l) => l.id === done.layerId);
        const count = done.pieceIds.length;
        toast.success(
          `Moved ${count > 1 ? `${count} objects` : 'the selection'} to “${layer?.name ?? 'a new layer'}”.`,
        );
        // Stay on what is left, ready to peel the next layer off it.
        editor.select(done.restId ? [done.restId] : done.pieceIds);
      } else if (mode === 'remove') {
        toast.success(done.restId ? 'Erased the selection.' : 'Erased the whole image.');
        if (done.restId) editor.select([done.restId]);
      } else {
        editor.select(done.pieceIds);
      }
    } catch (error) {
      reportError(error, 'Separate colors');
    } finally {
      separation.busy = false;
    }
  }
</script>

<div class="separate" data-testid="separate-panel">
  <p class="muted small">
    Click the image to pick a color. Drag across a gradient to pick its whole range. Pick as many as you need.
  </p>

  <div class="row">
    <button
      type="button"
      class="btn ghost"
      onclick={() => separation.selectBackground() || toast.info('No background color found at the edges.')}
      disabled={!separation.preview}
      data-testid="separate-background"
    >
      <ScanSearch size={15} />Select background
    </button>
    {#if separation.keys.length > 0}
      <button type="button" class="btn ghost" onclick={() => separation.clear()} data-testid="separate-clear">
        Clear
      </button>
    {/if}
  </div>

  {#if separation.keys.length > 0}
    <ul class="keys" aria-label="Picked colors" data-testid="separate-keys">
      {#each separation.keys as key, i (i)}
        <li>
          <span class="swatch" class:range={key.stops.length > 1} style:background={keySwatch(key)}></span>
          <span class="small muted"
            >{key.stops.length > 1 ? `Range · ${key.stops.length} colors` : 'Color'}</span
          >
          <button
            type="button"
            class="icon-btn sm"
            aria-label="Remove picked color {i + 1}"
            onclick={() => separation.removeKey(i)}><X size={14} /></button
          >
        </li>
      {/each}
    </ul>
  {/if}

  <NumberField
    label="Tolerance"
    hint="How different a color can be from a pick and still be selected"
    value={separation.tolerance}
    min={0}
    max={100}
    onchange={(v) => (separation.tolerance = v)}
    testid="separate-tolerance"
  />
  <NumberField
    label="Edge softness"
    hint="Blends the border of the selection, so cut-out edges stay smooth"
    value={separation.softness}
    min={0}
    max={100}
    onchange={(v) => (separation.softness = v)}
  />
  <div class="toggles">
    <Toggle
      label="Connected areas only"
      hint="Only areas joined to where you clicked. The same color elsewhere in the picture stays"
      checked={separation.connected}
      onchange={(c) => separation.setConnected(c)}
    />
    <Toggle
      label="Invert"
      hint="Select everything except the picked colors"
      checked={separation.invert}
      onchange={(c) => (separation.invert = c)}
    />
    <Toggle
      label="One object per area"
      hint="Each separate patch of the selection becomes its own object, so several subjects can be moved apart"
      checked={separation.regions}
      onchange={(c) => (separation.regions = c)}
    />
  </div>

  <div class="segmented small" role="group" aria-label="Show">
    {#each SHOW as [id, label] (id)}
      <button
        type="button"
        aria-pressed={separation.show === id}
        onclick={() => (separation.show = id)}
        data-testid="separate-show-{id}">{label}</button
      >
    {/each}
  </div>

  <p class="small mono muted" data-testid="separate-share">
    {separation.empty ? 'Nothing selected' : `${percent}% of the image selected`}
  </p>
  {#if image.locked}
    <p class="note">“{image.name}” is locked. Unlock it in the Layers panel to change it.</p>
  {/if}

  <button
    type="button"
    class="btn start"
    disabled={!ready}
    onclick={() => apply('layer')}
    data-testid="separate-layer"
  >
    <Layers size={15} />{separation.busy ? 'Separating…' : 'Move to new layer'}
  </button>
  <div class="row">
    <button
      type="button"
      class="btn ghost"
      disabled={!ready}
      onclick={() => apply('remove')}
      title="Make the selected pixels transparent"
      data-testid="separate-remove"
    >
      <Eraser size={15} />Erase
    </button>
    <button
      type="button"
      class="btn ghost"
      disabled={!ready}
      onclick={() => apply('keep')}
      title="Make everything except the selection transparent"
      data-testid="separate-keep"
    >
      <Crop size={15} />Keep only
    </button>
  </div>
</div>

<style>
  .separate {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .row {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .row .btn {
    flex: 1;
  }

  .keys {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .keys li {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .keys .small {
    flex: 1;
  }

  .swatch {
    width: 22px;
    height: 16px;
    flex-shrink: 0;
    border-radius: var(--ol-radius-sm);
    border: 1px solid var(--ol-border);
  }

  .swatch.range {
    width: 44px;
  }

  .toggles {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .small {
    font-size: var(--ol-fs-sm);
  }

  .note {
    margin: 0;
    font-size: var(--ol-fs-sm);
    color: var(--ol-hold);
  }

  p {
    margin: 0;
  }
</style>
