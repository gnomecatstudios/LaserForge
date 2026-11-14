import { expect, it } from 'vitest';
import { simplifyPath, type PathData } from 'libopenlaser/geometry';
const path = (points: number[][], closed = false): PathData => ({
  closed,
  start: { x: points[0][0], y: points[0][1] },
  segments: points.slice(1).map(([x, y]) => ({ type: 'L', to: { x, y } })),
});
it('reduces noisy straight runs and preserves endpoints without mutating input', () => {
  const p = path([
    [0, 0],
    [1, 0.01],
    [2, 0],
    [3, 0],
  ]);
  const snapshot = JSON.stringify(p);
  expect(simplifyPath(p, 0.02).segments).toEqual([{ type: 'L', to: { x: 3, y: 0 } }]);
  expect(JSON.stringify(p)).toBe(snapshot);
});
it('measures tolerance after scaling to bed mm', () => {
  const p = path([
    [0, 0],
    [1, 0.01],
    [2, 0],
  ]);
  expect(simplifyPath(p, 0.02, [1, 0, 0, 10, 0, 0])).toBe(p);
});
it('simplifies closed contours without dropping corners or changing closure', () => {
  const p = path(
    [
      [0, 0],
      [5, 0],
      [10, 0],
      [10, 5],
      [10, 10],
      [5, 10],
      [0, 10],
    ],
    true,
  );
  const result = simplifyPath(p, 0.1);
  expect(result.closed).toBe(true);
  expect(result.segments).toHaveLength(3);
});
it('preserves sharp corners, curves, and invalid tolerance inputs', () => {
  const p = path([
    [0, 0],
    [1, 0],
    [1, 1],
  ]);
  expect(simplifyPath(p, 100)).toBe(p);
  for (const tolerance of [0, -1, NaN, Infinity]) expect(simplifyPath(p, tolerance)).toBe(p);
  const curve: PathData = {
    closed: false,
    start: { x: 0, y: 0 },
    segments: [
      { type: 'C', c1: { x: 1, y: 0 }, c2: { x: 2, y: 0 }, to: { x: 3, y: 0 } },
      { type: 'L', to: { x: 4, y: 0 } },
    ],
  };
  expect(simplifyPath(curve, 1)).toBe(curve);
});
it('handles explicit closing nodes and never collapses a ring', () => {
  const p = path(
    [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
      [0, 0],
    ],
    true,
  );
  expect(simplifyPath(p, 100).segments).toHaveLength(3);
});
