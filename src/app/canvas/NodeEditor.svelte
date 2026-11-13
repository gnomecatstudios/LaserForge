<script lang="ts">
  import { apply, invert } from 'libopenlaser/geometry';
  import type { Vec2 } from 'libopenlaser/geometry';
  import { updateObject, type VectorObject } from 'libopenlaser/project';
  import { editor } from '../state/editor.svelte';
  import { canvas } from '../state/canvas.svelte';
  import { bedToScreen, screenToBed, type BedFrame } from './viewport';
  import { moveNode, pathNodes, type NodeRef } from './node-edit';
  let { bed }: { bed: BedFrame } = $props();
  let host: HTMLDivElement;
  const objects = $derived(
    editor.tool === 'node' && editor.view === 'design'
      ? (editor.project?.objects.filter(
          (o): o is VectorObject =>
            o.kind === 'vector' &&
            !o.locked &&
            o.visible &&
            editor.selection.has(o.id) &&
            editor.project!.layers.some((l) => l.id === o.layerId && l.visible),
        ) ?? [])
      : [],
  );
  let drag: { object: VectorObject; node: NodeRef; pointer: number } | null = null;
  function screen(object: VectorObject, point: Vec2) {
    return bedToScreen(canvas.view, bed, apply(object.transform, point));
  }
  function move(event: PointerEvent) {
    if (!drag || drag.pointer !== event.pointerId) return;
    const inverse = invert(drag.object.transform);
    if (!inverse) return;
    const r = host.getBoundingClientRect();
    const point = apply(
      inverse,
      screenToBed(canvas.view, bed, { x: event.clientX - r.left, y: event.clientY - r.top }),
    );
    const { object, node } = drag;
    editor.commit(
      (p) => updateObject(p, object.id, { paths: moveNode(object.paths, node, point), shape: undefined }),
      { coalesce: 'node-drag' },
    );
  }
  function end() {
    drag = null;
    editor.sealHistory();
  }
</script>

<div class="nodes" bind:this={host}>
  {#each objects as object (object.id)}
    <svg aria-hidden="true">
      {#each object.paths as path, pi (pi)}
        {#each path.segments as segment, i (i)}
          {#if segment.type === 'C'}
            {@const a = screen(object, i ? path.segments[i - 1].to : path.start)}
            {@const b = screen(object, segment.c1)}
            {@const c = screen(object, segment.c2)}
            {@const d = screen(object, segment.to)}
            <path d="M{a.x},{a.y} L{b.x},{b.y} M{c.x},{c.y} L{d.x},{d.y}" />
          {/if}
        {/each}
      {/each}
    </svg>
    {#each pathNodes(object.paths) as node (`${node.path}:${node.index}:${node.control ?? 'anchor'}`)}
      {@const at = screen(object, node.point)}
      <button
        type="button"
        class:control={!!node.control}
        style:left="{at.x}px"
        style:top="{at.y}px"
        aria-label="{node.control ? 'Curve handle' : 'Path node'} {node.path + 1}:{node.index + 2}"
        data-testid={node.control ? 'curve-handle' : 'path-node'}
        onpointerdown={(event) => {
          if (event.button !== 0) return;
          event.stopPropagation();
          event.currentTarget.setPointerCapture(event.pointerId);
          editor.sealHistory();
          drag = { object, node, pointer: event.pointerId };
        }}
        onpointermove={move}
        onpointerup={end}
        onpointercancel={end}
        onlostpointercapture={end}
      ></button>
    {/each}
  {/each}
  {#if editor.tool === 'node' && editor.view === 'design'}
    <p>Select a vector, then drag its nodes or curve handles.</p>
  {/if}
</div>

<style>
  .nodes {
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
  }
  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
  path {
    fill: none;
    stroke: var(--ol-signal);
    stroke-width: 1;
  }
  button {
    position: absolute;
    width: 12px;
    height: 12px;
    padding: 0;
    transform: translate(-50%, -50%);
    border: 2px solid var(--ol-signal);
    background: var(--ol-surface);
    pointer-events: auto;
    cursor: move;
    touch-action: none;
  }
  button.control {
    border-radius: 50%;
    width: 10px;
    height: 10px;
  }
  p {
    position: absolute;
    max-width: calc(100% - 32px);
    bottom: 12px;
    left: 16px;
    color: var(--ol-text-dim);
    background: var(--ol-surface);
    padding: 6px 10px;
    border-radius: var(--ol-radius-md);
  }
</style>
