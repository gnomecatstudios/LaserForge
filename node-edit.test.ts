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
