import type { PathData, Vec2 } from 'libopenlaser/geometry';

export interface NodeRef {
  path: number;
  index: number;
  control?: 'c1' | 'c2';
}

export function pathNodes(paths: PathData[]): (NodeRef & { point: Vec2 })[] {
  return paths.flatMap((p, path) => {
    const nodes: (NodeRef & { point: Vec2 })[] = [{ path, index: -1, point: p.start }];
    p.segments.forEach((s, index) => {
      const closing =
        p.closed && index === p.segments.length - 1 && s.to.x === p.start.x && s.to.y === p.start.y;
      if (!closing) nodes.push({ path, index, point: s.to });
      if (s.type === 'C') {
        nodes.push({ path, index, control: 'c1', point: s.c1 }, { path, index, control: 'c2', point: s.c2 });
      }
    });
    return nodes;
  });
}

/** Move an anchor with its adjacent handles; preserve explicit closing endpoints. */
export function moveNode(paths: PathData[], node: NodeRef, to: Vec2): PathData[] {
  return paths.map((original, i) => {
    if (i !== node.path) return original;
    const p = { ...original, segments: original.segments.map((segment) => ({ ...segment })) };
    const s = p.segments[node.index];
    if (node.control) {
      if (s?.type === 'C') s[node.control] = to;
      return p;
    }
    const before = node.index === -1 ? p.start : s.to;
    const delta = { x: to.x - before.x, y: to.y - before.y };
    const shift = (v: Vec2) => ({ x: v.x + delta.x, y: v.y + delta.y });
    const last = p.segments.at(-1);
    const closes = p.closed && last?.to.x === p.start.x && last?.to.y === p.start.y;
    if (node.index === -1) {
      if (closes && last) {
        last.to = to;
        if (last.type === 'C') last.c2 = shift(last.c2);
      }
      p.start = to;
    } else {
      s.to = to;
      if (s.type === 'C') s.c2 = shift(s.c2);
    }
    const next = p.segments[node.index + 1];
    if (next?.type === 'C') next.c1 = shift(next.c1);
    return p;
  });
}
