<script lang="ts">
  import { Popover } from 'bits-ui';
  import MousePointer2 from '@lucide/svelte/icons/mouse-pointer-2';
  import Spline from '@lucide/svelte/icons/spline';
  import PenTool from '@lucide/svelte/icons/pen-tool';
  import Combine from '@lucide/svelte/icons/combine';
  import { uniteSelection } from '../unite';
  import { apply as transformPoint, type PathData, type Vec2 } from 'libopenlaser/geometry';
  import type { VectorObject } from 'libopenlaser/project';

  let simplifyOpen = $state(false);
  let tolerance = $state(0.1);
  const vectors = $derived(editor.project?.objects.filter(
    (o): o is VectorObject => editor.selection.has(o.id) && o.kind === 'vector' && o.visible && !o.locked,
  ) ?? []);

  // RDP on straight runs in bed coordinates. Existing cubic segments remain exact.
  function simplifyPath(path: PathData, object: VectorObject): PathData {
    if (path.closed || path.segments.some((s) => s.type === 'C') || path.segments.length < 2) return path;
    const points = [path.start, ...path.segments.map((s) => s.to)];
    const world = points.map((p) => transformPoint(object.transform, p));
    const keep = new Set([0, points.length - 1]);
    const distance = (p: Vec2, a: Vec2, b: Vec2) => {
      const dx = b.x - a.x, dy = b.y - a.y;
      const length = dx * dx + dy * dy;
      const t = length ? Math.max(0, Math.min(1, ((p.x-a.x)*dx+(p.y-a.y)*dy)/length)) : 0;
      return Math.hypot(p.x-a.x-t*dx, p.y-a.y-t*dy);
    };
    // Preserve sharp corners (turns of 45 degrees or more).
    for (let i = 1; i < world.length - 1; i++) {
      const a = world[i-1], b = world[i], c = world[i+1];
      const ux = b.x-a.x, uy = b.y-a.y, vx = c.x-b.x, vy = c.y-b.y;
      const length = Math.hypot(ux,uy)*Math.hypot(vx,vy);
      if (length && (ux*vx+uy*vy)/length <= Math.SQRT1_2) keep.add(i);
    }
    const anchors = [...keep].sort((a,b) => a-b);
    const stack: [number, number][] = anchors.slice(1).map((end,i) => [anchors[i],end]);
    while (stack.length) {
      const [first,last] = stack.pop()!;
      let max = tolerance, index = -1;
      for (let i=first+1;i<last;i++) {
        const d = distance(world[i],world[first],world[last]);
        if (d > max) { max=d; index=i; }
      }
      if (index >= 0) { keep.add(index); stack.push([first,index],[index,last]); }
    }
    if (keep.size === points.length) return path;
    return { ...path, segments: points.slice(1).flatMap((to,i) => keep.has(i+1) ? [{type:'L' as const,to}] : []) };
  }
  const simplified = $derived(vectors.map((o) => ({ ...o, paths: o.paths.map((p) => simplifyPath(p,o)) })));
  const before = $derived(vectors.reduce((n,o) => n+o.paths.reduce((m,p)=>m+p.segments.length+1,0),0));
  const after = $derived(simplified.reduce((n,o) => n+o.paths.reduce((m,p)=>m+p.segments.length+1,0),0));
  function applySimplification() {
    if (after >= before || !Number.isFinite(tolerance) || tolerance <= 0) return;
    const replacements = new Map(simplified.filter((o,i) => o.paths.some((p,j) => p !== vectors[i].paths[j])).map((o) => [o.id,{...o,shape:undefined}]));
    editor.commit((p) => ({...p, objects:p.objects.map((o) => replacements.get(o.id) ?? o)}));
    simplifyOpen = false;
  }
  import Hand from '@lucide/svelte/icons/hand';
  import Square from '@lucide/svelte/icons/square';
  import Circle from '@lucide/svelte/icons/circle';
  import Type from '@lucide/svelte/icons/type';
  import Ruler from '@lucide/svelte/icons/ruler';
  import ImagePlus from '@lucide/svelte/icons/image-plus';
  import * as actions from '../actions';
  import type { Component } from 'svelte';
  import { isShapeKind, shapeDef } from 'libopenlaser/shapes';
  import { formatCombo } from '../lib/keys';
  import { editor, type Tool } from '../state/editor.svelte';
  import ShapeGlyph from '../inspector/ShapeGlyph.svelte';
  import ShapePicker from '../inspector/ShapePicker.svelte';
  import OutlineTool from './OutlineTool.svelte';

  type Entry =
    | { id: Tool; label: string; key: string; icon: Component; design: boolean }
    | 'divider'
    | 'shapes'
    | 'image'
    | 'outline';

  const tools: Entry[] = [
    { id: 'select', label: 'Select', key: 'V', icon: MousePointer2, design: true },
    { id: 'node', label: 'Nodes', key: 'N', icon: Spline, design: true },
    { id: 'pen', label: 'Draw path', key: 'B', icon: PenTool, design: true },
    { id: 'pan', label: 'Pan', key: 'H', icon: Hand, design: false },
    'divider',
    { id: 'rect', label: 'Rectangle', key: 'R', icon: Square, design: true },
    { id: 'ellipse', label: 'Ellipse', key: 'E', icon: Circle, design: true },
    'shapes',
    { id: 'text', label: 'Text', key: 'T', icon: Type, design: true },
    'image',
    'divider',
    'outline',
    { id: 'measure', label: 'Measure', key: 'M', icon: Ruler, design: false },
  ];

  const designing = $derived(editor.view === 'design' && editor.project !== null);
  const shapeKind = $derived(isShapeKind(editor.shapeKind) ? editor.shapeKind : 'star');
  let pickerOpen = $state(false);
</script>

<nav class="rail" aria-label="Tools">
  {#each tools as tool, i (i)}
    {#if tool === 'divider'}
      <div class="rule"></div>
    {:else if tool === 'image'}
      <button
        type="button"
        class="icon-btn tool"
        aria-label="Image: SVG, DXF, PNG, JPEG, WebP, AVIF, BMP, GIF ({formatCombo('Mod+I')})"
        disabled={!designing}
        onclick={() => actions.importArt()}
        data-testid="tool-image"><ImagePlus size={18} /></button
      >
    {:else if tool === 'outline'}
      <OutlineTool disabled={!designing} />
    {:else if tool === 'shapes'}
      <Popover.Root bind:open={pickerOpen}>
        <Popover.Trigger
          class="icon-btn tool"
          aria-label="Shapes: {shapeDef(shapeKind).label} ({formatCombo('S')})"
          aria-pressed={editor.tool === 'shape'}
          disabled={!designing}
          onclick={() => (editor.tool = 'shape')}
          data-testid="tool-shape"
        >
          <ShapeGlyph kind={shapeKind} size={20} />
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content class="ol-menu" side="right" align="start" sideOffset={8}>
            <ShapePicker
              value={shapeKind}
              onpick={(kind) => {
                editor.shapeKind = kind;
                editor.tool = 'shape';
                pickerOpen = false;
              }}
            />
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
    {:else}
      <button
        type="button"
        class="icon-btn tool"
        aria-label="{tool.label} ({formatCombo(tool.key)})"
        aria-pressed={editor.tool === tool.id}
        disabled={tool.design && !designing}
        onclick={() => (editor.tool = tool.id)}
        data-testid="tool-{tool.id}"
      >
        <tool.icon size={18} />
      </button>
    {/if}
  {/each}
  <button
    type="button"
    class="icon-btn tool"
    aria-label="Unite closed shapes"
    data-testid="tool-unite"
    disabled={!designing ||
      (editor.project?.objects.filter((o) => editor.selection.has(o.id)).length ?? 0) < 2 ||
      !!editor.project?.objects.some(
        (o) =>
          editor.selection.has(o.id) &&
          (o.kind !== 'vector' || o.locked || !o.visible || o.paths.some((p) => !p.closed)),
      )}
    onclick={uniteSelection}><Combine size={18} /></button
  >
  <Popover.Root bind:open={simplifyOpen}>
    <Popover.Trigger class="icon-btn tool" aria-label="Simplify path" disabled={!designing || !vectors.length} data-testid="tool-simplify">
      <Spline size={18} />
    </Popover.Trigger>
    <Popover.Portal>
      <Popover.Content class="ol-menu simplify-menu" side="right" align="start" sideOffset={8}>
        <strong>Simplify path</strong>
        <label for="simplify-tolerance">Tolerance (mm): {tolerance.toFixed(2)}</label>
        <input id="simplify-tolerance" type="range" min="0.01" max="1" step="0.01" bind:value={tolerance} />
        <span>Nodes: {before} → {after}</span>
        <span>Open straight-segment paths only. Closed paths and Bézier curves are preserved unchanged.</span>
        <button type="button" class="btn" onclick={() => (simplifyOpen = false)}>Cancel</button>
        <button type="button" class="btn start" disabled={after >= before} onclick={applySimplification}>Apply simplification</button>
      </Popover.Content>
    </Popover.Portal>
  </Popover.Root>
</nav>

<style>
  :global(.simplify-menu) { width: 260px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .rail {
    width: var(--ol-toolrail-w);
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 10px 0;
    border-right: 1px solid var(--ol-border);
    background: var(--ol-surface);
  }

  .rail :global(.tool) {
    width: 40px;
    height: 40px;
  }

  .rule {
    width: 24px;
    height: 1px;
    background: var(--ol-border);
    margin: 6px 0;
  }
</style>
