import { IDENTITY, flattenPaths, union, type PathData } from 'libopenlaser/geometry';
import { addObjects, removeObjects, makeId, type VectorObject } from 'libopenlaser/project';
import { editor } from './state/editor.svelte';

export function unitePaths(objects: VectorObject[]): PathData[] {
  // Resolve each object's holes separately before combining overlapping objects.
  const rings = objects.flatMap((o) =>
    union(
      flattenPaths(o.paths, o.transform)
        .filter((p) => p.closed)
        .map((p) => p.points),
      'evenodd',
    ),
  );
  return union(rings, 'nonzero').map((points) => ({
    start: points[0],
    segments: points.slice(1).map((to) => ({ type: 'L', to })),
    closed: true,
  }));
}
export function uniteSelection() {
  const objects =
    editor.project?.objects.filter(
      (o): o is VectorObject => editor.selection.has(o.id) && o.kind === 'vector' && !o.locked && o.visible,
    ) ?? [];
  if (objects.length < 2 || objects.some((o) => o.paths.some((p) => !p.closed))) return;
  const paths = unitePaths(objects);
  if (!paths.length) return;
  const object: VectorObject = {
    ...objects[0],
    id: makeId(),
    name: 'United shape',
    paths,
    transform: IDENTITY,
    shape: undefined,
  };
  editor.commit((p) => addObjects(removeObjects(p, new Set(objects.map((o) => o.id))), [object]));
  editor.select([object.id]);
  editor.tool = 'node';
}
