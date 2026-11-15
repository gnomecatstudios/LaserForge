/** Private protocol v1 adapter. The existing library remains the canonical document/CAM engine. */
import { Buffer } from 'node:buffer';
import { multiply, translation } from '../../packages/libopenlaser/src/geometry/mat2d';
import { simplifyPath } from '../../packages/libopenlaser/src/geometry/simplify';
import { compileJob } from '../../packages/libopenlaser/src/cam/compile';
import type { RasterSource } from '../../packages/libopenlaser/src/cam/types';
import { defaultImageSize, readImageDpi, sniffImageMime } from '../../packages/libopenlaser/src/import/image';
import { importDxf, DXF_UNITS, type DxfUnit } from '../../packages/libopenlaser/src/import/dxf';
import { buildProjectObjectsFromSvg } from '../../packages/libopenlaser/src/import/svg/to-project';
import { GrblConnection } from '../../packages/libopenlaser/src/machine/grbl/connection';
import { virtualGrblTransport } from '../../packages/libopenlaser/src/machine/simulator/virtual-machine';
import { VirtualScheduler } from '../../packages/libopenlaser/src/machine/virtual-scheduler';
import { createProject, defaultMachineProfile } from '../../packages/libopenlaser/src/project/factory';
import { workArea } from '../../packages/libopenlaser/src/project/accessories';
import { History } from '../../packages/libopenlaser/src/project/history';
import { makeId } from '../../packages/libopenlaser/src/project/ids';
import { MACHINE_PRESETS } from '../../packages/libopenlaser/src/project/machine-presets';
import { MATERIAL_PRESETS, presetLayerPatch } from '../../packages/libopenlaser/src/project/materials';
import { defaultLayer } from '../../packages/libopenlaser/src/project/layer-defaults';
import * as ops from '../../packages/libopenlaser/src/project/operations';
import { reorient } from '../../packages/libopenlaser/src/project/orientation';
import { deserializeProject, serializeProject } from '../../packages/libopenlaser/src/project/serialize';
import { ellipsePath, rectanglePath } from '../../packages/libopenlaser/src/project/shapes';
import type {
  Asset,
  Layer,
  LayerMode,
  MachineProfile,
  Mat2D,
  PathData,
  Project,
  SceneObject,
} from '../../packages/libopenlaser/src/project/types';

export const PROTOCOL_VERSION = 1;
export const MAX_MESSAGE_BYTES = 128 * 1024 * 1024;
const METHODS = [
  'hello',
  'new',
  'snapshot',
  'load',
  'save',
  'copy',
  'paste',
  'simplify',
  'createShape',
  'addPaths',
  'addImage',
  'transform',
  'delete',
  'duplicate',
  'reorder',
  'undo',
  'redo',
  'addLayer',
  'updateLayer',
  'moveLayer',
  'updateObject',
  'importDxf',
  'compile',
  'simulate',
  'catalogs',
  'applyMaterial',
  'setProfile',
  'setJobSettings',
] as const;

type RecordValue = Record<string, unknown>;
export interface Request {
  id: string | number;
  method: string;
  params?: unknown;
}
export type Response =
  | { id: string | number | null; result: unknown }
  | { id: string | number | null; error: { message: string } };

function record(value: unknown, name = 'params'): RecordValue {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error(`${name} must be an object`);
  return value as RecordValue;
}
function text(value: unknown, name: string): string {
  if (typeof value !== 'string') throw new Error(`${name} must be a string`);
  return value;
}
function finite(value: unknown, name: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${name} must be finite`);
  return value;
}
function positive(value: unknown, name: string): number {
  const n = finite(value, name);
  if (n <= 0) throw new Error(`${name} must be positive`);
  return n;
}
function matrix(value: unknown): Mat2D {
  if (!Array.isArray(value) || value.length !== 6) throw new Error('matrix must contain six finite numbers');
  return value.map((n) => finite(n, 'matrix component')) as Mat2D;
}
function paths(value: unknown): PathData[] {
  if (!Array.isArray(value)) throw new Error('paths must be an array');
  const point = (v: unknown) => {
    const p = record(v, 'point');
    finite(p.x, 'point.x');
    finite(p.y, 'point.y');
  };
  for (const candidate of value) {
    const path = record(candidate, 'path');
    point(path.start);
    if (typeof path.closed !== 'boolean' || !Array.isArray(path.segments)) throw new Error('Invalid path');
    for (const segment of path.segments) {
      const s = record(segment, 'segment');
      if (s.type !== 'L' && s.type !== 'C') throw new Error('Only L and C path segments are supported');
      point(s.to);
      if (s.type === 'C') {
        point(s.c1);
        point(s.c2);
      }
    }
  }
  return value as PathData[];
}
function decode(value: unknown): Buffer {
  const source = text(value, 'data');
  if (source.length > MAX_MESSAGE_BYTES) {
    throw new Error('data must be bounded, valid base64');
  }
  const bytes = Buffer.from(source, 'base64');
  if (bytes.toString('base64') !== source) throw new Error('data must be bounded, valid base64');
  return bytes;
}
function mode(value: unknown): LayerMode {
  if (value !== 'line' && value !== 'fill' && value !== 'image') throw new Error('Invalid layer mode');
  return value;
}
function validateProfile(profile: MachineProfile): MachineProfile {
  validateFiniteTree(profile);
  for (const key of ['bedWidth', 'bedHeight', 'maxS', 'baudRate', 'defaultJogSpeed', 'frameSpeed'] as const)
    positive(profile[key], key);
  if (!['bl', 'br', 'tl', 'tr'].includes(profile.originCorner))
    throw new Error('Invalid machine origin corner');
  if (!['diode', 'co2'].includes(profile.laserType)) throw new Error('Invalid laser type');
  const frame = finite(profile.framePowerPercent, 'framePowerPercent');
  if (frame < 0 || frame > 5) throw new Error('Frame power must be 0–5 percent');
  return profile;
}
function validatePatchTypes(patch: RecordValue, booleans: string[], strings: string[]): void {
  for (const key of booleans)
    if (key in patch && typeof patch[key] !== 'boolean') throw new Error(`${key} must be boolean`);
  for (const key of strings) if (key in patch) text(patch[key], key);
}
function validateFiniteTree(value: unknown): void {
  if (typeof value === 'number' && !Number.isFinite(value))
    throw new Error('Settings must contain finite numbers');
  if (Array.isArray(value)) value.forEach(validateFiniteTree);
  else if (value && typeof value === 'object') Object.values(value).forEach(validateFiniteTree);
}
function validateProject(project: Project): void {
  if (
    !Array.isArray(project.layers) ||
    !Array.isArray(project.objects) ||
    !project.assets ||
    !project.jobSettings
  ) {
    throw new Error('Invalid project structure');
  }
  const layerIds = new Set<string>();
  for (const l of project.layers) {
    text(l.id, 'layer.id');
    if (layerIds.has(l.id)) throw new Error('Duplicate layer id');
    layerIds.add(l.id);
    mode(l.mode);
    validateFiniteTree(l);
    positive(l.speed, 'layer.speed');
    if (!Number.isInteger(l.passes) || l.passes < 1)
      throw new Error('Layer passes must be a positive integer');
    for (const key of ['power', 'minPower'] as const) {
      const value = finite(l[key], key);
      if (value < 0 || value > 100) throw new Error(`Layer ${key} must be 0–100`);
    }
    if (l.fill) positive(l.fill.interval, 'fill.interval');
    if (l.image) {
      positive(l.image.dpi, 'image.dpi');
      positive(l.image.gamma, 'image.gamma');
    }
  }
  const objectIds = new Set<string>();
  for (const o of project.objects) {
    text(o.id, 'object.id');
    if (objectIds.has(o.id)) throw new Error('Duplicate object id');
    objectIds.add(o.id);
    if (!layerIds.has(o.layerId)) throw new Error('Object references an unknown layer');
    matrix(o.transform);
    if (o.kind === 'vector' || o.kind === 'text') paths(o.paths);
    else if (o.kind === 'image') {
      positive(o.width, 'width');
      positive(o.height, 'height');
    } else throw new Error('Unknown object kind');
  }
}

export class NativeService {
  private project: Project;
  private readonly history = new History<Project>();
  private profile = defaultMachineProfile();

  constructor() {
    this.project = this.emptyProject();
  }

  private emptyProject(name = 'Untitled'): Project {
    return reorient(
      ops.addLayer(createProject({ name }), defaultLayer({ id: makeId() })),
      this.profile.originCorner,
    );
  }

  private async snapshot() {
    const assets: Record<string, Omit<Asset, 'data'> & { data: string }> = {};
    for (const [id, asset] of Object.entries(this.project.assets)) {
      assets[id] = { ...asset, data: Buffer.from(await asset.data.arrayBuffer()).toString('base64') };
    }
    return {
      project: { ...this.project, assets },
      canUndo: this.history.canUndo,
      canRedo: this.history.canRedo,
      profile: this.profile,
    };
  }

  private commit(project: Project) {
    validateProject(project);
    this.history.record(this.project);
    this.project = { ...project, updatedAt: new Date().toISOString() };
    return this.snapshot();
  }

  private layerId(value?: unknown): string {
    const id = value === undefined ? this.project.layers[0]?.id : text(value, 'layerId');
    if (!id || !this.project.layers.some((l) => l.id === id)) throw new Error('Unknown layer');
    return id;
  }

  private ids(value: unknown): Set<string> {
    if (!Array.isArray(value)) throw new Error('ids must be an array');
    const ids = new Set(value.map((id) => text(id, 'id')));
    for (const id of ids)
      if (!this.project.objects.some((o) => o.id === id)) throw new Error(`Unknown object: ${id}`);
    return ids;
  }

  private baseObject(params: RecordValue, name: string, layerId?: string) {
    return {
      id: makeId(),
      layerId: layerId ?? this.layerId(params.layerId),
      name: params.name === undefined ? name : text(params.name, 'name'),
      visible: true,
      locked: false,
      transform: [1, 0, 0, 1, finite(params.x ?? 0, 'x'), finite(params.y ?? 0, 'y')] as Mat2D,
    };
  }

  private compile(params: RecordValue) {
    const profile = validateProfile(
      params.profile === undefined ? this.profile : defaultMachineProfile(record(params.profile, 'profile')),
    );
    if (profile.originCorner !== this.project.designCorner) {
      throw new Error('Apply the profile with setProfile before compiling for a different origin corner');
    }
    let machinePosition: { x: number; y: number } | undefined;
    if (params.machinePosition !== undefined) {
      const point = record(params.machinePosition, 'machinePosition');
      machinePosition = { x: finite(point.x, 'machinePosition.x'), y: finite(point.y, 'machinePosition.y') };
    }
    if (this.project.jobSettings.origin === 'current-position' && !machinePosition) {
      throw new Error(
        'Current-position jobs require an explicit machinePosition; native hardware position is unavailable',
      );
    }
    if (this.project.jobSettings.origin === 'user-origin' && !this.project.jobSettings.userOrigin) {
      throw new Error('Set a user origin before compiling a user-origin job');
    }
    if (this.project.jobSettings.origin === 'user-origin') {
      const origin = record(this.project.jobSettings.userOrigin, 'userOrigin');
      finite(origin.x, 'userOrigin.x');
      finite(origin.y, 'userOrigin.y');
    }
    const rasters = new Map<string, RasterSource>();
    for (const [id, value] of Object.entries(
      params.rasters === undefined ? {} : record(params.rasters, 'rasters'),
    )) {
      const raster = record(value, 'raster');
      const width = positive(raster.width, 'raster.width');
      const height = positive(raster.height, 'raster.height');
      const data = decode(raster.data);
      if (
        !Number.isSafeInteger(width) ||
        !Number.isSafeInteger(height) ||
        width * height * 4 !== data.length
      ) {
        throw new Error('Raster RGBA data length must equal width × height × 4');
      }
      rasters.set(id, { width, height, data: new Uint8ClampedArray(data) });
    }
    // Missing raster buffers must be explicit, never silently omit a saved engraving.
    for (const object of this.project.objects) {
      const layer = this.project.layers.find((l) => l.id === object.layerId);
      if (
        object.kind === 'image' &&
        object.visible &&
        layer?.visible &&
        layer.output &&
        !rasters.has(object.assetId)
      ) {
        throw new Error(`Decoded raster required for asset ${object.assetId}`);
      }
    }
    return { profile, job: compileJob({ project: this.project, profile, assets: rasters, machinePosition }) };
  }

  async dispatch(method: string, input: unknown = {}): Promise<unknown> {
    const p = record(input);
    switch (method) {
      case 'hello':
        return { protocolVersion: PROTOCOL_VERSION, machineMode: 'simulation-only', methods: METHODS };
      case 'catalogs':
        return { machinePresets: MACHINE_PRESETS, materials: MATERIAL_PRESETS };
      case 'setProfile': {
        const patch = record(p.profile, 'profile');
        validateFiniteTree(patch);
        validatePatchTypes(
          patch,
          ['laserModeRequired', 'supportsAirAssist', 'constantPower'],
          ['id', 'name', 'controller', 'gcodeHeader', 'gcodeFooter', 'flatModeGcode'],
        );
        const profile = validateProfile(defaultMachineProfile({ ...this.profile, ...patch }));
        const oriented = reorient(this.project, profile.originCorner);
        validateProject(oriented);
        this.profile = profile;
        if (oriented !== this.project) this.project = { ...oriented, updatedAt: new Date().toISOString() };
        return this.snapshot();
      }
      case 'applyMaterial': {
        const id = this.layerId(p.layerId);
        const preset = MATERIAL_PRESETS.find((m) => m.id === text(p.presetId, 'presetId'));
        if (!preset) throw new Error('Unknown material preset');
        const layer = this.project.layers.find((l) => l.id === id)!;
        return this.commit(ops.updateLayer(this.project, id, presetLayerPatch(layer, preset)));
      }
      case 'setJobSettings': {
        const patch = record(p.patch, 'patch');
        validatePatchTypes(patch, ['returnToOrigin', 'optimizeOrder'], []);
        if (
          Object.keys(patch).some(
            (key) =>
              ![
                'origin',
                'anchor',
                'userOrigin',
                'returnToOrigin',
                'optimizeOrder',
                'accessoryId',
                'objectDiameter',
              ].includes(key),
          )
        )
          throw new Error('Unsupported job settings patch');
        if (
          patch.origin !== undefined &&
          !['absolute', 'current-position', 'user-origin'].includes(String(patch.origin))
        )
          throw new Error('Invalid job origin');
        if (
          patch.anchor !== undefined &&
          !['tl', 't', 'tr', 'l', 'c', 'r', 'bl', 'b', 'br'].includes(String(patch.anchor))
        )
          throw new Error('Invalid job anchor');
        if (patch.userOrigin !== undefined && patch.userOrigin !== null) {
          const point = record(patch.userOrigin, 'userOrigin');
          finite(point.x, 'userOrigin.x');
          finite(point.y, 'userOrigin.y');
        }
        if (patch.objectDiameter !== undefined) positive(patch.objectDiameter, 'objectDiameter');
        return this.commit(ops.setJobSettings(this.project, patch));
      }
      case 'snapshot':
        return this.snapshot();
      case 'new':
        this.project = this.emptyProject(p.name === undefined ? 'Untitled' : text(p.name, 'name'));
        this.history.clear();
        return this.snapshot();
      case 'load': {
        const project = reorient(await deserializeProject(decode(p.data)), this.profile.originCorner);
        validateProject(project);
        this.project = project;
        this.history.clear();
        return this.snapshot();
      }
      case 'copy': {
        const ids = this.ids(p.ids);
        const objects = this.project.objects.filter((o) => ids.has(o.id));
        const layers = this.project.layers.filter((l) => objects.some((o) => o.layerId === l.id));
        const fragment = ops.removeUnusedAssets({ ...this.project, objects, layers });
        return { data: Buffer.from(await serializeProject(fragment)).toString('base64') };
      }
      case 'paste': {
        const fragment = reorient(await deserializeProject(decode(p.data)), this.profile.originCorner);
        validateProject(fragment);
        const layers = new Map(
          fragment.layers.map((l) => [
            l.id,
            this.project.layers.some(
              (existing) => existing.id === l.id && JSON.stringify(existing) === JSON.stringify(l),
            )
              ? l.id
              : makeId(),
          ]),
        );
        const assets = new Map(Object.keys(fragment.assets).map((id) => [id, makeId()]));
        for (const o of fragment.objects)
          if (o.kind === 'image' && !assets.has(o.assetId))
            throw new Error('Clipboard image asset is missing');
        const objects = fragment.objects.map((o) => ({
          ...o,
          id: makeId(),
          layerId: layers.get(o.layerId)!,
          transform: multiply(translation(5, -5), o.transform),
          ...(o.kind === 'image' ? { assetId: assets.get(o.assetId)! } : {}),
        })) as SceneObject[];
        let next = this.project;
        for (const layer of fragment.layers)
          if (!next.layers.some((l) => l.id === layers.get(layer.id)))
            next = ops.addLayer(next, { ...layer, id: layers.get(layer.id)! });
        return this.commit(
          ops.addObjects(
            next,
            objects,
            Object.values(fragment.assets).map((a) => ({ ...a, id: assets.get(a.id)! })),
          ),
        );
      }
      case 'simplify': {
        const ids = this.ids(p.ids);
        const tolerance = positive(p.tolerance, 'tolerance');
        const objects = this.project.objects.map((o) =>
          o.kind === 'vector' && ids.has(o.id) && !o.locked
            ? {
                ...o,
                paths: o.paths.map((path) => simplifyPath(path, tolerance, o.transform)),
                shape: undefined,
              }
            : o,
        );
        return this.commit({ ...this.project, objects });
      }
      case 'save':
        return { data: Buffer.from(await serializeProject(this.project)).toString('base64') };
      case 'createShape': {
        if (p.kind !== 'rect' && p.kind !== 'ellipse') throw new Error('Shape kind must be rect or ellipse');
        const width = positive(p.width, 'width');
        const height = positive(p.height, 'height');
        const path = p.kind === 'rect' ? rectanglePath(width, height) : ellipsePath(width, height);
        return this.commit(
          ops.addObjects(this.project, [
            {
              ...this.baseObject(p, p.kind === 'rect' ? 'Rectangle' : 'Ellipse'),
              kind: 'vector',
              paths: [path],
              drawn: true,
            },
          ]),
        );
      }
      case 'addPaths':
        return this.commit(
          ops.addObjects(this.project, [
            { ...this.baseObject(p, 'Path'), kind: 'vector', paths: paths(p.paths) },
          ]),
        );
      case 'addImage': {
        const bytes = decode(p.data);
        const mime = sniffImageMime(bytes) ?? text(p.mime, 'mime');
        const name = text(p.name, 'name');
        const asset: Asset = {
          id: makeId(),
          mime,
          name,
          data: new Blob([new Uint8Array(bytes)], { type: mime }),
        };
        if (p.widthPx !== undefined) asset.widthPx = positive(p.widthPx, 'widthPx');
        if (p.heightPx !== undefined) asset.heightPx = positive(p.heightPx, 'heightPx');
        let size: { width: number; height: number };
        if (p.width === undefined && p.height === undefined) {
          const width = positive(p.widthPx, 'widthPx');
          const height = positive(p.heightPx, 'heightPx');
          if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height))
            throw new Error('Pixel dimensions must be positive integers');
          size = defaultImageSize(
            { width, height },
            readImageDpi(bytes),
            workArea(this.profile, this.project.jobSettings),
          );
        } else {
          size = { width: positive(p.width, 'width'), height: positive(p.height, 'height') };
        }
        let next = this.project;
        let layer: Layer | undefined;
        if (p.layerId !== undefined) {
          const id = this.layerId(p.layerId);
          layer = this.project.layers.find((candidate) => candidate.id === id);
          if (layer?.mode !== 'image') throw new Error('Images must be placed on an image layer');
        } else {
          layer = this.project.layers.find((candidate) => candidate.mode === 'image');
          if (!layer) {
            layer = defaultLayer({ id: makeId(), mode: 'image' });
            next = ops.addLayer(next, layer);
          }
        }
        const object: SceneObject = {
          ...this.baseObject(p, name, layer.id),
          kind: 'image',
          assetId: asset.id,
          width: size.width,
          height: size.height,
        };
        return this.commit(ops.addObjects(next, [object], [asset]));
      }
      case 'transform':
        return this.commit(ops.transformObjects(this.project, this.ids(p.ids), matrix(p.matrix)));
      case 'delete':
        return this.commit(ops.removeObjects(this.project, this.ids(p.ids)));
      case 'duplicate':
        return this.commit(ops.duplicateObjects(this.project, this.ids(p.ids), makeId).project);
      case 'reorder': {
        if (p.where !== 'front' && p.where !== 'back') throw new Error('where must be front or back');
        return this.commit(ops.reorderObjects(this.project, this.ids(p.ids), p.where));
      }
      case 'undo': {
        const previous = this.history.undo(this.project);
        if (previous) this.project = reorient(previous, this.profile.originCorner);
        return this.snapshot();
      }
      case 'redo': {
        const next = this.history.redo(this.project);
        if (next) this.project = reorient(next, this.profile.originCorner);
        return this.snapshot();
      }
      case 'addLayer':
        return this.commit(
          ops.addLayer(
            this.project,
            defaultLayer({
              id: makeId(),
              ...(p.name === undefined ? {} : { name: text(p.name, 'name') }),
              ...(p.mode === undefined ? {} : { mode: mode(p.mode) }),
            }),
          ),
        );
      case 'moveLayer': {
        const from = finite(p.from, 'from');
        const to = finite(p.to, 'to');
        if (![from, to].every((n) => Number.isInteger(n) && n >= 0 && n < this.project.layers.length))
          throw new Error('Invalid layer index');
        return this.commit(ops.moveLayer(this.project, from, to));
      }
      case 'updateLayer': {
        const id = this.layerId(p.id);
        const patch = record(p.patch, 'patch');
        validatePatchTypes(
          patch,
          ['visible', 'output', 'airAssist'],
          ['name', 'color', 'laserSourceId', 'materialId'],
        );
        validateFiniteTree(patch);
        const allowed = [
          'name',
          'color',
          'visible',
          'output',
          'mode',
          'speed',
          'power',
          'minPower',
          'passes',
          'airAssist',
          'laserSourceId',
          'materialId',
          'line',
          'fill',
          'image',
        ];
        if (Object.keys(patch).some((k) => !allowed.includes(k))) throw new Error('Unsupported layer patch');
        for (const key of ['speed', 'power', 'minPower', 'passes']) if (key in patch) finite(patch[key], key);
        if ('speed' in patch) positive(patch.speed, 'speed');
        if ('passes' in patch && (!Number.isInteger(patch.passes) || Number(patch.passes) < 1))
          throw new Error('passes must be a positive integer');
        for (const key of ['power', 'minPower'])
          if (key in patch && (Number(patch[key]) < 0 || Number(patch[key]) > 100))
            throw new Error(`${key} must be 0–100`);
        return this.commit(ops.updateLayer(this.project, id, patch as Partial<Layer>));
      }
      case 'updateObject': {
        const id = text(p.id, 'id');
        const object = this.project.objects.find((o) => o.id === id);
        if (!object) throw new Error('Unknown object');
        const patch = record(p.patch, 'patch');
        validatePatchTypes(patch, ['visible', 'locked'], ['name']);
        if (
          Object.keys(patch).some((k) => !['name', 'visible', 'locked', 'transform', 'layerId'].includes(k))
        )
          throw new Error('Unsupported object patch');
        if (patch.transform !== undefined) matrix(patch.transform);
        if (patch.layerId !== undefined) this.layerId(patch.layerId);
        return this.commit(ops.updateObject(this.project, id, patch));
      }
      case 'importDxf': {
        if (p.units !== undefined && !Object.hasOwn(DXF_UNITS, text(p.units, 'units')))
          throw new Error('Invalid DXF units');
        const imported = importDxf(text(p.source, 'source'), p.units as DxfUnit | undefined);
        const result = buildProjectObjectsFromSvg(imported, this.project.layers, makeId, { name: 'DXF' });
        let next = this.project;
        for (const layer of result.layersToAdd) next = ops.addLayer(next, layer);
        return this.commit(ops.addObjects(next, result.objects, result.assets));
      }
      case 'compile':
        return this.compile(p).job;
      case 'simulate': {
        const { profile, job } = this.compile(p);
        const blocking = job.warnings.filter((warning) => warning.blocking);
        if (blocking.length)
          throw new Error(`Simulation blocked: ${blocking.map((warning) => warning.message).join('; ')}`);
        const clock = new VirtualScheduler();
        const connection = new GrblConnection({ scheduler: clock });
        try {
          await clock.runUntil(
            connection.connect(virtualGrblTransport(profile, { scheduler: clock }), profile),
            30_000,
          );
          // The virtual device starts in homing alarm, just as a real configured GRBL does.
          await clock.runUntil(connection.driver.unlock(), 5000);
          await clock.advance(250);
          const outcome = await clock.runUntil(
            connection.run({ lines: job.gcode, estimatedSeconds: job.stats.estimatedSeconds }),
            24 * 3600_000,
          );
          return {
            ...outcome,
            simulation: true,
            progress: connection.runner?.progress.get(),
            state: connection.driver.state.get(),
          };
        } finally {
          await connection.disconnect();
        }
      }
      default:
        throw new Error(`Unknown method: ${method}`);
    }
  }

  async handleRequest(value: unknown): Promise<Response> {
    let id: string | number | null = null;
    try {
      const request = record(value, 'request');
      if (
        typeof request.id !== 'string' &&
        (typeof request.id !== 'number' || !Number.isSafeInteger(request.id))
      )
        throw new Error('Request id must be a string or integer');
      id = request.id;
      const result = await this.dispatch(text(request.method, 'method'), request.params ?? {});
      return { id, result };
    } catch (error) {
      return { id, error: { message: error instanceof Error ? error.message : String(error) } };
    }
  }
}
