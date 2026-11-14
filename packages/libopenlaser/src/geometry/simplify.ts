import { apply, IDENTITY } from './mat2d';
import type { Mat2D, PathData, Vec2 } from './types';

function distance(p: Vec2, a: Vec2, b: Vec2): number {
  const dx = b.x - a.x,
    dy = b.y - a.y;
  const length = dx * dx + dy * dy;
  const t = length ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / length)) : 0;
  return Math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy);
}

/** Reduce polyline nodes within a tolerance in transformed mm. Cubic paths remain exact.
 * Endpoints, the closed seam and turns of 45 degrees or more are retained.
 * The iterative algorithm avoids recursion limits on large imported paths.
 */
export function simplifyPath(path: PathData, tolerance: number, transform: Mat2D = IDENTITY): PathData {
  if (
    !Number.isFinite(tolerance) ||
    tolerance <= 0 ||
    path.segments.length < 2 ||
    path.segments.some((s) => s.type === 'C')
  )
    return path;
  const points = [path.start, ...path.segments.map((s) => s.to)];
  const world = points.map((p) => apply(transform, p));
  if (world.some((p) => !Number.isFinite(p.x) || !Number.isFinite(p.y))) return path;
  // Normalize explicit closing endpoints, while keeping the original seam.
  if (path.closed && distance(world[world.length - 1], world[0], world[0]) < 1e-9) {
    points.pop();
    world.pop();
  }
  if (points.length < (path.closed ? 3 : 2)) return path;
  const keep = new Set([0, points.length - 1]);
  for (let i = 1; i < world.length - 1; i++) {
    const a = world[i - 1],
      b = world[i],
      c = world[i + 1];
    const ux = b.x - a.x,
      uy = b.y - a.y,
      vx = c.x - b.x,
      vy = c.y - b.y;
    const length = Math.hypot(ux, uy) * Math.hypot(vx, vy);
    if (length && (ux * vx + uy * vy) / length <= Math.SQRT1_2) keep.add(i);
  }
  if (path.closed) {
    // A second anchor splits smooth loops; never reduce a ring to a line.
    let farthest = 1;
    for (let i = 2; i < world.length; i++) {
      if (distance(world[i], world[0], world[0]) > distance(world[farthest], world[0], world[0]))
        farthest = i;
    }
    keep.add(farthest);
  }
  const anchors = [...keep].sort((a, b) => a - b);
  const stack: [number, number][] = anchors.slice(1).map((end, i) => [anchors[i], end]);
  while (stack.length) {
    const [first, last] = stack.pop()!;
    let maximum = tolerance,
      index = -1;
    for (let i = first + 1; i < last; i++) {
      const d = distance(world[i], world[first], world[last]);
      if (d > maximum) {
        maximum = d;
        index = i;
      }
    }
    if (index >= 0) {
      keep.add(index);
      stack.push([first, index], [index, last]);
    }
  }
  if (keep.size < (path.closed ? 3 : 2)) return path;
  const result = points.filter((_, i) => keep.has(i));
  if (path.closed) {
    // Reject collapsed or reversed loops even with an excessive tolerance.
    const area = (ps: Vec2[]) =>
      ps.reduce((n, p, i) => {
        const q = ps[(i + 1) % ps.length];
        return n + p.x * q.y - q.x * p.y;
      }, 0);
    if (area(result) * area(points) <= 0) return path;
  }
  if (result.length === path.segments.length + 1) return path;
  return { ...path, segments: result.slice(1).map((to) => ({ type: 'L', to })) };
}
