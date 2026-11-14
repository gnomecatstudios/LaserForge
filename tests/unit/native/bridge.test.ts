import { describe, expect, it } from 'vitest';
import { Buffer } from 'node:buffer';
import { NativeService } from '../../../native/bridge/service';
import { compileJob } from 'libopenlaser/cam';
import { deserializeProject } from 'libopenlaser/project';
import { rectanglePath } from 'libopenlaser/project';
import { reorient } from 'libopenlaser/project';
import type { Project, MachineProfile } from 'libopenlaser/project';
import { dxf, line } from '../../../packages/libopenlaser/test/unit/import/dxf/build';

interface Snapshot {
  project: Project;
  canUndo: boolean;
  canRedo: boolean;
  profile: MachineProfile;
}
const snapshot = async (service: NativeService, method = 'snapshot', params = {}) =>
  (await service.dispatch(method, params)) as Snapshot;
const rectangle = (service: NativeService, extra = {}) =>
  snapshot(service, 'createShape', { kind: 'rect', x: 5, y: 7, width: 20, height: 10, ...extra });

describe('native retained-core bridge', () => {
  it('advertises versioned simulator-only capabilities and rejects hardware requests', async () => {
    const service = new NativeService();
    expect(await service.dispatch('hello')).toMatchObject({
      protocolVersion: 1,
      machineMode: 'simulation-only',
    });
    expect(await service.handleRequest({ id: 1, method: 'connectHardware' })).toMatchObject({
      id: 1,
      error: { message: 'Unknown method: connectHardware' },
    });
    expect(await service.handleRequest({ method: 'snapshot' })).toHaveProperty('error');
  });

  it('round trips through the original .olaser serializer with assets', async () => {
    const service = new NativeService();
    await rectangle(service);
    await service.dispatch('addImage', {
      data: Buffer.from([0, 255, 128, 255]).toString('base64'),
      mime: 'image/png',
      name: 'pixel',
      width: 10,
      height: 15,
      widthPx: 1,
      heightPx: 1,
    });
    const original = await snapshot(service);
    const saved = (await service.dispatch('save')) as { data: string };
    const bytes = Buffer.from(saved.data, 'base64');
    expect(bytes.subarray(0, 2).toString()).toBe('PK');
    const core = await deserializeProject(bytes);
    expect(core.objects).toEqual(original.project.objects);
    expect(Object.values(core.assets)[0].data.size).toBe(4);
    await service.dispatch('new');
    const restored = await snapshot(service, 'load', saved);
    expect(restored.project).toEqual(original.project);
    expect(restored.canUndo).toBe(false);
  });

  it('opens legacy plain JSON, preserves text outlines and unknown additive fields', async () => {
    const service = new NativeService();
    const original = await rectangle(service);
    const textObject = {
      ...original.project.objects[0],
      id: 'cached-text',
      kind: 'text',
      text: 'LaserForge',
      fontFamily: 'Geist',
      fontSize: 10,
      fontWeight: 400,
      italic: false,
      align: 'left',
      lineHeight: 1.2,
      letterSpacing: 0,
      paths: [rectanglePath(20, 10)],
    };
    const project = {
      ...original.project,
      objects: [...original.project.objects, textObject],
      futureMetadata: { author: 'LaserForge' },
    };
    delete (project as Partial<Project>).assets;
    const data = Buffer.from(
      JSON.stringify({ format: 'openlaser-project', version: 1, project, assets: [] }),
    ).toString('base64');
    const loaded = await snapshot(service, 'load', { data });
    expect(loaded.project).toHaveProperty('futureMetadata.author', 'LaserForge');
    expect(loaded.project.objects).toEqual(project.objects);
    const saved = (await service.dispatch('save')) as { data: string };
    const restored = await deserializeProject(Buffer.from(saved.data, 'base64'));
    expect(restored.objects[1]).toEqual(textObject);
  });

  it('uses canonical matrices, locking, layer operations and undo/redo', async () => {
    const service = new NativeService();
    const created = await rectangle(service);
    const id = created.project.objects[0].id;
    const moved = await snapshot(service, 'transform', { ids: [id], matrix: [0, 1, -1, 0, 30, 0] });
    expect(moved.project.objects[0].transform).toEqual([0, 1, -1, 0, 23, 5]);
    expect((await snapshot(service, 'undo')).project.objects[0].transform).toEqual([1, 0, 0, 1, 5, 7]);
    expect((await snapshot(service, 'redo')).project.objects[0].transform).toEqual([0, 1, -1, 0, 23, 5]);
    await service.dispatch('updateObject', { id, patch: { locked: true } });
    const locked = await snapshot(service, 'transform', { ids: [id], matrix: [1, 0, 0, 1, 100, 100] });
    expect(locked.project.objects[0].transform).toEqual(moved.project.objects[0].transform);
    const layered = await snapshot(service, 'addLayer', { name: 'Engrave', mode: 'fill' });
    const layerId = layered.project.layers[1].id;
    await service.dispatch('updateLayer', { id: layerId, patch: { visible: false, output: false } });
    expect((await snapshot(service, 'moveLayer', { from: 1, to: 0 })).project.layers[0]).toMatchObject({
      id: layerId,
      visible: false,
      output: false,
    });
  });

  it('produces exactly the same laser job as direct original-core compilation', async () => {
    const service = new NativeService();
    const current = await rectangle(service);
    const expected = compileJob({ project: current.project, profile: current.profile, assets: new Map() });
    expect(await service.dispatch('compile')).toEqual(expected);
    await service.dispatch('transform', {
      ids: [current.project.objects[0].id],
      matrix: [1, 0, 0, 1, 10, 20],
    });
    const moved = await snapshot(service);
    expect(await service.dispatch('compile')).toEqual(
      compileJob({ project: moved.project, profile: moved.profile, assets: new Map() }),
    );
  });

  it('compiles native RGBA rasters through retained raster CAM and rejects missing pixels', async () => {
    const service = new NativeService();
    const added = await snapshot(service, 'addImage', {
      data: 'AAAA/w==',
      mime: 'image/png',
      name: 'pixel',
      width: 1,
      height: 1,
    });
    const image = added.project.objects[0];
    if (image.kind !== 'image') throw new Error('Expected image');
    expect(added.project.layers.find((layer) => layer.id === image.layerId)?.mode).toBe('image');
    await service.dispatch('updateLayer', {
      id: image.layerId,
      patch: {
        mode: 'image',
        image: {
          dpi: 25.4,
          algorithm: 'threshold',
          threshold: 128,
          brightness: 0,
          contrast: 0,
          gamma: 1,
          invert: false,
          bidirectional: true,
          overscan: 0,
          scanAngle: 0,
          passThrough: false,
        },
      },
    });
    await expect(service.dispatch('compile')).rejects.toThrow('Decoded raster required');
    const current = await snapshot(service);
    const expected = compileJob({
      project: current.project,
      profile: current.profile,
      assets: new Map([
        [image.assetId, { width: 1, height: 1, data: new Uint8ClampedArray([0, 0, 0, 255]) }],
      ]),
    });
    expect(expected.gcode.length).toBeGreaterThan(0);
    expect(
      await service.dispatch('compile', {
        rasters: { [image.assetId]: { width: 1, height: 1, data: 'AAAA/w==' } },
      }),
    ).toEqual(expected);
    await expect(
      service.dispatch('compile', {
        rasters: { [image.assetId]: { width: 2, height: 1, data: 'AAAA/w==' } },
      }),
    ).rejects.toThrow('RGBA data length');
  });

  it('creates an image layer atomically, reuses it, and refuses a line layer for images', async () => {
    const service = new NativeService();
    const initial = await snapshot(service);
    const imageParams = { data: 'AAAA/w==', mime: 'image/png', name: 'pixel', width: 1, height: 1 };
    await expect(
      service.dispatch('addImage', { ...imageParams, layerId: initial.project.layers[0].id }),
    ).rejects.toThrow('Images must be placed on an image layer');
    expect((await snapshot(service)).project).toEqual(initial.project);
    const first = await snapshot(service, 'addImage', imageParams);
    expect(first.project.layers).toHaveLength(2);
    const undone = await snapshot(service, 'undo');
    expect(undone.project.layers).toHaveLength(1);
    expect(undone.project.objects).toHaveLength(0);
    expect(Object.keys(undone.project.assets)).toHaveLength(0);
    await service.dispatch('redo');
    const second = await snapshot(service, 'addImage', imageParams);
    expect(second.project.layers).toHaveLength(2);
    expect(second.project.objects[0].layerId).toBe(second.project.objects[1].layerId);
  });

  it('rejects malformed changes without corrupting the current document', async () => {
    const service = new NativeService();
    const current = await rectangle(service);
    const id = current.project.objects[0].id;
    for (const [method, params] of [
      ['createShape', { kind: 'rect', width: -5, height: 10 }],
      ['transform', { ids: [id], matrix: [1, 0, 0, Infinity, 0, 0] }],
      ['updateLayer', { id: current.project.layers[0].id, patch: { power: 101 } }],
      ['updateObject', { id, patch: { kind: 'image' } }],
      ['addPaths', { paths: [{ ...rectanglePath(2, 3), start: { x: NaN, y: 0 } }] }],
      ['load', { data: 'bad base64' }],
    ] as const)
      await expect(service.dispatch(method, params)).rejects.toThrow();
    expect((await snapshot(service)).project).toEqual(current.project);
  });

  it('uses original machine and material catalogs, and supports job settings', async () => {
    const service = new NativeService();
    const catalogs = (await service.dispatch('catalogs')) as {
      materials: { id: string; power: number }[];
      machinePresets: unknown[];
    };
    expect(catalogs.machinePresets.length).toBeGreaterThan(0);
    const initial = await snapshot(service);
    const preset = catalogs.materials[0];
    const applied = await snapshot(service, 'applyMaterial', {
      layerId: initial.project.layers[0].id,
      presetId: preset.id,
    });
    expect(applied.project.layers[0]).toMatchObject({ materialId: preset.id, power: preset.power });
    expect(
      (await snapshot(service, 'setProfile', { profile: { bedWidth: 300, originCorner: 'tr' } })).profile,
    ).toMatchObject({ bedWidth: 300, originCorner: 'tr' });
    await expect(service.dispatch('setProfile', { profile: { framePowerPercent: 6 } })).rejects.toThrow();
    expect(
      (
        await snapshot(service, 'setJobSettings', {
          patch: { origin: 'user-origin', userOrigin: { x: 5, y: 10 } },
        })
      ).project.jobSettings,
    ).toMatchObject({ origin: 'user-origin', userOrigin: { x: 5, y: 10 } });
  });

  it('imports DXF with physical units and maintains duplicate/delete ordering history', async () => {
    const service = new NativeService();
    const imported = await snapshot(service, 'importDxf', {
      source: dxf({ units: 1, entities: [line(0, 0, 2, 0)] }),
    });
    const object = imported.project.objects[0];
    expect(object.kind).toBe('vector');
    if (object.kind !== 'vector') throw new Error('Expected vector');
    expect(object.paths[0].segments[0].to.x).toBeCloseTo(50.8);
    const duplicated = await snapshot(service, 'duplicate', { ids: [object.id] });
    expect(duplicated.project.objects).toHaveLength(2);
    const copy = duplicated.project.objects[1];
    expect(copy.id).not.toBe(object.id);
    expect(copy.transform).toEqual([1, 0, 0, 1, 5, -5]);
    expect(
      (await snapshot(service, 'reorder', { ids: [copy.id], where: 'back' })).project.objects[0].id,
    ).toBe(copy.id);
    expect((await snapshot(service, 'delete', { ids: [copy.id] })).project.objects).toHaveLength(1);
    expect((await snapshot(service, 'undo')).project.objects).toHaveLength(2);
  });

  it('runs the unchanged GRBL driver and JobRunner against only a simulated device', async () => {
    const service = new NativeService();
    await rectangle(service, { width: 2, height: 2 });
    const result = await service.dispatch('simulate');
    expect(result).toMatchObject({
      outcome: 'completed',
      simulation: true,
      progress: { phase: 'completed' },
      state: { connection: 'connected', status: 'Idle' },
    });
  });

  it('refuses to simulate jobs with blocking CAM warnings', async () => {
    const service = new NativeService();
    await expect(service.dispatch('simulate')).rejects.toThrow('Simulation blocked: Nothing to burn');
    await rectangle(service, { x: 390, y: 10, width: 20, height: 10 });
    await expect(service.dispatch('simulate')).rejects.toThrow('Simulation blocked: The job moves outside');
  });

  it('preserves the original corner reorientation on profiles, load, undo, redo and new', async () => {
    const service = new NativeService();
    const original = await snapshot(service, 'addPaths', {
      paths: [
        {
          closed: true,
          start: { x: 0, y: 0 },
          segments: [
            { type: 'L', to: { x: 20, y: 3 } },
            { type: 'L', to: { x: 5, y: 10 } },
            { type: 'L', to: { x: 0, y: 0 } },
          ],
        },
      ],
      x: 7,
      y: 13,
    });
    expect(original.project.designCorner).toBe('bl');
    const saved = (await service.dispatch('save')) as { data: string };
    const topRight = await snapshot(service, 'setProfile', { profile: { originCorner: 'tr' } });
    expect(topRight.project.objects).toEqual(reorient(original.project, 'tr').objects);
    expect(topRight.project.designCorner).toBe('tr');
    expect(await service.dispatch('compile')).toEqual(
      compileJob({ project: reorient(original.project, 'tr'), profile: topRight.profile, assets: new Map() }),
    );
    const undone = await snapshot(service, 'undo');
    expect(undone.project.designCorner).toBe('tr');
    expect(undone.project.objects).toHaveLength(0);
    const redone = await snapshot(service, 'redo');
    expect(redone.project.designCorner).toBe('tr');
    expect(redone.project.objects).toEqual(topRight.project.objects);
    const back = await snapshot(service, 'setProfile', { profile: { originCorner: 'bl' } });
    expect(back.project.objects).toEqual(original.project.objects);
    await service.dispatch('setProfile', { profile: { originCorner: 'tr' } });
    const loaded = await snapshot(service, 'load', saved);
    expect(loaded.project.objects).toEqual(reorient(original.project, 'tr').objects);
    expect((await snapshot(service, 'new')).project.designCorner).toBe('tr');
  });
});
