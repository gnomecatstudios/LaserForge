/** Anchors picked in the node editor: Delete removes them and dragging one moves them all. */
import type { Vec2 } from 'libopenlaser/geometry';
import { updateObject, type Project, type VectorObject } from 'libopenlaser/project';
import { editor } from './editor.svelte';
import { deleteNode, pathNodes, type NodeRef } from '../canvas/node-edit';

export interface PickedNode {
  objectId: string;
  node: NodeRef;
}

const same = (a: PickedNode, objectId: string, node: NodeRef) =>
  a.objectId === objectId && a.node.path === node.path && a.node.index === node.index;

/** Vectors the node tool edits: selected, unlocked and visible on a visible layer. */
export function editableVectors(): VectorObject[] {
  const project = editor.project;
  if (!project || editor.tool !== 'node' || editor.view !== 'design') return [];
  return project.objects.filter(
    (o): o is VectorObject =>
      o.kind === 'vector' &&
      !o.locked &&
      o.visible &&
      editor.selection.has(o.id) &&
      project.layers.some((l) => l.id === o.layerId && l.visible),
  );
}

class NodeSelection {
  picked = $state<PickedNode[]>([]);

  is(objectId: string, node: NodeRef): boolean {
    return !node.control && this.picked.some((p) => same(p, objectId, node));
  }

  set(picked: PickedNode[]): void {
    this.picked = picked.filter((p) => !p.node.control);
  }

  clear(): void {
    if (this.picked.length) this.picked = [];
  }

  /** Add or remove one anchor; returns whether it is now picked. */
  toggle(objectId: string, node: NodeRef): boolean {
    if (node.control) return false;
    if (this.is(objectId, node)) {
      this.picked = this.picked.filter((p) => !same(p, objectId, node));
      return false;
    }
    this.picked = [...this.picked, { objectId, node: { path: node.path, index: node.index } }];
    return true;
  }

  /** Pick every anchor of the editable vectors. */
  selectAll(): void {
    this.set(
      editableVectors().flatMap((object) =>
        pathNodes(object.paths)
          .filter((n) => !n.control)
          .map((n) => ({ objectId: object.id, node: { path: n.path, index: n.index } })),
      ),
    );
  }

  /** Pick the anchors whose screen position falls inside `box`. */
  selectInBox(
    box: { minX: number; minY: number; maxX: number; maxY: number },
    toScreen: (object: VectorObject, point: Vec2) => Vec2,
    additive: boolean,
  ): void {
    const hits = editableVectors().flatMap((object) =>
      pathNodes(object.paths)
        .filter((n) => {
          if (n.control) return false;
          const s = toScreen(object, n.point);
          return s.x >= box.minX && s.x <= box.maxX && s.y >= box.minY && s.y <= box.maxY;
        })
        .map((n) => ({ objectId: object.id, node: { path: n.path, index: n.index } })),
    );
    if (!additive) return this.set(hits);
    this.set([...this.picked, ...hits.filter((h) => !this.is(h.objectId, h.node))]);
  }

  /** Picked anchors that still exist, grouped by their editable vector. */
  targets(): { object: VectorObject; nodes: (NodeRef & { point: Vec2 })[] }[] {
    return editableVectors()
      .map((object) => ({
        object,
        nodes: pathNodes(object.paths).filter((n) => this.is(object.id, n)),
      }))
      .filter((t) => t.nodes.length);
  }

  /**
   * Delete anchors in one undo step. Each path keeps at least two anchors, so some may be
   * skipped. Returns whether anything changed.
   */
  remove(picks: { object: VectorObject; nodes: NodeRef[] }[]): boolean {
    const updates = picks
      .map(({ object, nodes }) => {
        // Delete the highest anchors first so earlier indices stay valid.
        const ordered = [...nodes].sort((a, b) => b.path - a.path || b.index - a.index);
        const paths = ordered.reduce((paths, node) => deleteNode(paths, node), object.paths);
        return { object, paths };
      })
      .filter((u) => u.paths !== u.object.paths);
    if (!updates.length) return false;
    editor.sealHistory();
    editor.commit((p: Project) =>
      updates.reduce((p, u) => updateObject(p, u.object.id, { paths: u.paths, shape: undefined }), p),
    );
    editor.sealHistory();
    this.picked = [];
    return true;
  }

  removeSelected(): boolean {
    return this.remove(this.targets());
  }
}

export const nodeSelection = new NodeSelection();
