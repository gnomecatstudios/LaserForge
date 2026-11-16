/** Text conversion and baseline attachment, each as one undoable operation. */
import { apply, invert, multiply } from 'libopenlaser/geometry';
import type { PathData } from 'libopenlaser/geometry';
import type { SceneObject, TextObject, VectorObject } from 'libopenlaser/project';
import { toast } from '$lib/ui/toasts.svelte';
import { editor } from './state/editor.svelte';
import { canvas } from './state/canvas.svelte';
import { textOutlines } from './state/text.svelte';

export function textAsVector(text: TextObject): VectorObject {
  return {
    id: text.id,
    kind: 'vector',
    layerId: text.layerId,
    name: text.name,
    locked: text.locked,
    visible: text.visible,
    transform: text.transform,
    paths: text.paths,
  };
}

export function convertSelectedText(): void {
  const selected = editor.project?.objects.filter((o) => editor.selection.has(o.id)) ?? [];
  const texts = selected.filter((o): o is TextObject => o.kind === 'text' && !o.locked && o.visible);
  if (!texts.length) return;
  if (texts.some((o) => textOutlines.pending.has(o.id) || !o.paths.length || o.missingGlyphs?.length)) {
    toast.warning('Wait for complete font outlines before converting text.');
    return;
  }
  const ids = new Set(texts.map((o) => o.id));
  editor.sealHistory();
  editor.commit((p) => ({
    ...p,
    objects: p.objects.map((o) => (o.kind === 'text' && ids.has(o.id) ? textAsVector(o) : o)),
  }));
  canvas.editingTextId = null;
  editor.select(ids);
  editor.tool = 'node';
}

export function canAttachTextToPath(selected: SceneObject[]): boolean {
  return (
    selected.length === 2 &&
    selected.every((o) => !o.locked && o.visible) &&
    selected.filter((o) => o.kind === 'text').length === 1 &&
    selected.some((o) => o.kind === 'vector' && o.paths.length === 1 && o.paths[0].segments.length > 0)
  );
}

export function attachTextToPath(): void {
  const selected = editor.project?.objects.filter((o) => editor.selection.has(o.id)) ?? [];
  if (!canAttachTextToPath(selected)) return;
  const text = selected.find((o): o is TextObject => o.kind === 'text')!;
  const vector = selected.find((o): o is VectorObject => o.kind === 'vector')!;
  const inverse = invert(text.transform);
  if (!inverse) return;
  const matrix = multiply(inverse, vector.transform);
  const map = (point: { x: number; y: number }) => apply(matrix, point);
  const source = vector.paths[0];
  const path: PathData = {
    ...source,
    start: map(source.start),
    segments: source.segments.map((s) =>
      s.type === 'C' ? { ...s, to: map(s.to), c1: map(s.c1), c2: map(s.c2) } : { ...s, to: map(s.to) },
    ),
  };
  textOutlines.update(text.id, {
    pathLayout: { path, guideId: vector.id, offset: 0, normalOffset: 0, reverse: false },
  });
  canvas.editingTextId = null;
  editor.select([text.id]);
  editor.tool = 'select';
}

export function detachTextFromPath(text: TextObject): void {
  // Keep the object's frame; its editable straight outlines refresh asynchronously.
  textOutlines.update(text.id, { pathLayout: undefined, arcAngle: 0 });
}
