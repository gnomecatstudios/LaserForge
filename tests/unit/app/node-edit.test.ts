import { describe, it, expect } from 'vitest';
import { moveNode, pathNodes } from '../../../src/app/canvas/node-edit';
import type { PathData } from 'libopenlaser/geometry';
const path: PathData = {
  start: { x: 0, y: 0 },
  closed: true,
  segments: [
    { type: 'C', c1: { x: 1, y: 0 }, c2: { x: 4, y: 5 }, to: { x: 5, y: 5 } },
    { type: 'C', c1: { x: 6, y: 5 }, c2: { x: 0, y: 1 }, to: { x: 0, y: 0 } },
  ],
};
describe('node editing', () => {
  it('deduplicates the closing anchor and exposes cubic handles', () => {
    expect(pathNodes([path]).filter((n) => !n.control)).toHaveLength(2);
    expect(pathNodes([path]).filter((n) => n.control)).toHaveLength(4);
  });
  it('moves the closing anchor and both adjacent handles without mutating the source', () => {
    const [next] = moveNode([path], { path: 0, index: -1 }, { x: 2, y: 3 });
    expect(next.start).toEqual({ x: 2, y: 3 });
    expect(next.segments[1].to).toEqual(next.start);
    expect(next.segments[0]).toMatchObject({ c1: { x: 3, y: 3 } });
    expect(next.segments[1]).toMatchObject({ c2: { x: 2, y: 4 } });
    expect(path.start).toEqual({ x: 0, y: 0 });
  });
  it('moves a curve handle independently', () => {
    const [next] = moveNode([path], { path: 0, index: 0, control: 'c1' }, { x: 8, y: 9 });
    expect(next.segments[0]).toMatchObject({ c1: { x: 8, y: 9 }, c2: { x: 4, y: 5 }, to: { x: 5, y: 5 } });
  });
});

import { insertNode } from '../../../src/app/canvas/node-edit';
import { cubicPoint } from 'libopenlaser/geometry';
it('splits cubic curves exactly without changing their geometry', () => {
  const [next] = insertNode([path], 0, 0, 0.4);
  expect(next.segments).toHaveLength(3);
  const left = next.segments[0],
    right = next.segments[1],
    original = path.segments[0];
  if (left.type !== 'C' || right.type !== 'C' || original.type !== 'C')
    throw new Error('Expected cubic segments');
  for (let i = 0; i <= 20; i++) {
    const t = i / 20;
    const expected = cubicPoint(path.start, original.c1, original.c2, original.to, t);
    const actual =
      t <= 0.4
        ? cubicPoint(path.start, left.c1, left.c2, left.to, t / 0.4)
        : cubicPoint(left.to, right.c1, right.c2, right.to, (t - 0.4) / 0.6);
    expect(actual.x).toBeCloseTo(expected.x, 10);
    expect(actual.y).toBeCloseTo(expected.y, 10);
  }
});
it('splits implicit closing lines and refuses endpoint duplicates', () => {
  const p: PathData = {
    start: { x: 0, y: 0 },
    closed: true,
    segments: [
      { type: 'L', to: { x: 10, y: 0 } },
      { type: 'L', to: { x: 10, y: 10 } },
    ],
  };
  const paths = [p];
  expect(insertNode(paths, 0, 2, 0.5)[0].segments[2].to).toEqual({ x: 5, y: 5 });
  expect(insertNode(paths, 0, 0, 0)).toBe(paths);
  expect(p.segments).toHaveLength(2);
});
