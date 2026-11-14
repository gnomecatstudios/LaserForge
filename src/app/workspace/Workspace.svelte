<script lang="ts">
  import FileCode from '@lucide/svelte/icons/file-code';
  import X from '@lucide/svelte/icons/x';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import ArrowRight from '@lucide/svelte/icons/arrow-right';
  import Upload from '@lucide/svelte/icons/upload';
  import { sidebar, type SidebarPanel } from '../state/workspace.svelte';
  import { currentBed } from '../state/work-area';
  import ErrorBoundary from '$lib/ui/ErrorBoundary.svelte';
  import CanvasView from '../canvas/CanvasView.svelte';
  import { count } from '../lib/format';
  import { editor } from '../state/editor.svelte';
  import { preview } from '../state/preview.svelte';
  import * as actions from '../actions';
  import TopBar from './TopBar.svelte';
  import ToolRail from './ToolRail.svelte';
  import SelectionBar from './SelectionBar.svelte';
  import PreviewBar from './PreviewBar.svelte';
  import LayersPanel from './LayersPanel.svelte';
  import LayoutPanel from './LayoutPanel.svelte';
  import SelectionInspector from '../inspector/SelectionInspector.svelte';
  import { textOutlines } from '../state/text.svelte';
  import MachinePanel from '../machine/MachinePanel.svelte';
  import ConsolePanel from '../machine/ConsolePanel.svelte';
  import { connectedAdapter, shownAdapter } from '../machines/registry';
  import StatusBar from './StatusBar.svelte';
  import { untrack } from 'svelte';
  import { reorient } from 'libopenlaser/project';
  import { profiles } from '../state/profiles.svelte';
  import { fitToBed, type Area } from 'libopenlaser/project';
  import { workArea } from 'libopenlaser/project';
  import { toast } from '$lib/ui/toasts.svelte';

  // The design keeps reading the right way up when the machine's home corner changes (switching
  // machines, editing the profile). A project without a recorded corner is taken as laid out for
  // the machine it is open on now: nothing moves, the corner is recorded.
  $effect(() => {
    const project = editor.project;
    if (!project || !profiles.loaded) return;
    const to = profiles.active.originCorner;
    if (project.designCorner === to) return;
    untrack(() => editor.commit((p) => reorient(p, to), { record: false }));
  });

  // Switching to a machine with a smaller work area brings what fitted on the old one along,
  // scaled down if it has to be. Fitting an accessory changes the area without refitting.
  let laidOut: { key: string; area: Area } | null = null;
  $effect(() => {
    const project = editor.project;
    if (!project || !profiles.loaded) return;
    const p = profiles.active;
    const key = `${p.id} ${p.bedWidth} ${p.bedHeight}`;
    const area = workArea(p, project.jobSettings);
    const before = laidOut;
    laidOut = { key, area };
    if (!before || before.key === key) return;
    untrack(() => {
      const fitted = fitToBed(project, before.area, area);
      if (!fitted) return;
      editor.commit(() => fitted);
      editor.sealHistory();
      toast.info('Design resized to fit the work area.');
    });
  });

  // Text from opened projects gets its outlines as soon as its fonts are reachable.
  $effect(() => {
    if (editor.project) textOutlines.ensureAll(editor.project);
  });

  // Keep the compiled job fresh while Preview is visible.
  $effect(() => {
    if (editor.view === 'preview' && editor.project) {
      void preview.stale;
      preview.schedule();
    }
  });

  let previousProjectId: string | null = null;
  $effect(() => {
    const id = editor.project?.id ?? null;
    if (id === previousProjectId) return;
    previousProjectId = id;
    if (id && sidebar.requestedProjectId !== id) untrack(() => sidebar.showDesign());
  });

  $effect(() => {
    const selection = editor.selection;
    const view = editor.view;
    if (view === 'design' && selection.size > 0) untrack(() => sidebar.showDesign());
  });

  $effect(() => {
    const tool = editor.tool;
    if (editor.view === 'design' && ['rect', 'ellipse', 'shape', 'text', 'pen', 'node'].includes(tool)) {
      untrack(() => sidebar.showDesign());
    }
  });

  $effect(() => {
    if (editor.gcode) untrack(() => sidebar.showMachine());
  });

  const bounds = $derived(editor.gcode?.moves.bounds);
  const live = $derived(connectedAdapter());
  const area = $derived(currentBed());
  const adapter = $derived(shownAdapter());
  const panel = $derived(editor.gcode ? 'machine' : sidebar.current);
  const running = $derived(live?.live.session.jobActive ?? false);
  const empty = $derived((editor.project?.objects.length ?? 0) === 0);

  function tabKeydown(event: KeyboardEvent, current: SidebarPanel) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next =
      event.key === 'Home'
        ? 'design'
        : event.key === 'End'
          ? 'machine'
          : current === 'design'
            ? 'machine'
            : 'design';
    sidebar.select(next);
    document.getElementById(`sidebar-${next}`)?.focus();
  }
</script>

<div class="workspace" class:has-controls={!!live?.controls} data-testid="workspace">
  <ErrorBoundary name="Top bar" compact><TopBar /></ErrorBoundary>
  <div class="body">
    <ErrorBoundary name="Tools" compact><ToolRail /></ErrorBoundary>
    <main class="center">
      {#if editor.project && editor.view === 'design'}
        <ErrorBoundary name="Selection bar" compact><SelectionBar /></ErrorBoundary>
      {/if}
      <ErrorBoundary name="Canvas"><CanvasView /></ErrorBoundary>
      {#if editor.view === 'preview' || editor.gcode}
        <ErrorBoundary name="Preview" compact><PreviewBar /></ErrorBoundary>
      {/if}
    </main>
    <aside class="side" aria-label="Project and machine settings">
      <button
        type="button"
        class="machine-summary"
        onclick={() => sidebar.showMachine()}
        aria-label="Open machine controls for {profiles.active.name}"
        data-testid="machine-summary"
      >
        <span class="summary-text">
          <strong>{profiles.active.name}</strong>
          <span class="summary-meta mono">
            {Math.round(area.width)} × {Math.round(area.height)} mm
            {#if adapter.badge}<adapter.badge />{:else}<span>{adapter.label}</span>{/if}
          </span>
        </span>
        <ChevronRight size={16} />
      </button>
      {#if editor.project}
        <div class="sidebar-tabs" role="tablist" aria-label="Sidebar">
          <button
            type="button"
            role="tab"
            id="sidebar-design"
            aria-selected={panel === 'design'}
            aria-controls="workspace-design-panel"
            tabindex={panel === 'design' ? 0 : -1}
            onclick={() => sidebar.showDesign()}
            onkeydown={(event) => tabKeydown(event, 'design')}
            data-testid="sidebar-design">Design</button
          >
          <button
            type="button"
            role="tab"
            id="sidebar-machine"
            aria-selected={panel === 'machine'}
            aria-controls="workspace-machine-panel"
            tabindex={panel === 'machine' ? 0 : -1}
            onclick={() => sidebar.showMachine()}
            onkeydown={(event) => tabKeydown(event, 'machine')}
            data-testid="sidebar-machine">Machine</button
          >
        </div>
      {/if}
      <div class="side-scroll">
        {#if editor.project}
          <div
            id="workspace-design-panel"
            role="tabpanel"
            aria-labelledby="sidebar-design"
            hidden={panel !== 'design'}
            tabindex="0"
          >
            {#if empty}
              <div class="design-intro">
                <h2>Your design</h2>
                <p>Add artwork, then set how each layer burns.</p>
              </div>
            {/if}
            <ErrorBoundary name="Inspector"><SelectionInspector /></ErrorBoundary>
            <ErrorBoundary name="Layers"><LayersPanel /></ErrorBoundary>
            {#if empty}
              <div class="import-action">
                <button type="button" class="btn" onclick={() => actions.importArt()}>
                  <Upload size={16} />Import artwork
                </button>
              </div>
            {/if}
            <ErrorBoundary name="Layout"><LayoutPanel /></ErrorBoundary>
          </div>
        {/if}
        <div
          id="workspace-machine-panel"
          role="tabpanel"
          aria-label={editor.project ? undefined : 'Machine controls'}
          aria-labelledby={editor.project ? 'sidebar-machine' : undefined}
          hidden={panel !== 'machine'}
          tabindex="0"
        >
          <ErrorBoundary name="Machine"><MachinePanel showBadge={false} /></ErrorBoundary>
          {#if editor.gcode}
            <section class="gcode-card" aria-label="G-code file">
              <FileCode size={18} />
              <div class="gcode-text">
                <span class="gcode-name">{editor.gcode.name}</span>
                <span class="mono muted small">
                  {count(editor.gcode.lines.length)} lines{#if bounds}
                    · {Math.round(bounds.maxX - bounds.minX)} × {Math.round(bounds.maxY - bounds.minY)} mm{/if}
                </span>
              </div>
              <button
                type="button"
                class="icon-btn sm"
                aria-label="Close G-code file"
                onclick={() => actions.closeDocument()}><X size={16} /></button
              >
            </section>
          {/if}
        </div>
      </div>
      {#if editor.project && editor.view === 'design' && !running}
        <div class="preview-next">
          <p>
            {empty ? 'Add artwork to preview your job.' : 'Review the toolpath before running your laser.'}
          </p>
          <button
            type="button"
            class="btn start cta"
            disabled={empty}
            onclick={() => (editor.view = 'preview')}
            data-testid="preview-job">Preview job<ArrowRight size={16} /></button
          >
        </div>
      {/if}
      {#if live?.controls}
        <ErrorBoundary name="Job controls" compact><live.controls /></ErrorBoundary>
      {/if}
      {#if shownAdapter().capabilities.console}
        <ErrorBoundary name="Console" compact><ConsolePanel /></ErrorBoundary>
      {/if}
    </aside>
  </div>
  <footer class="foot">
    <ErrorBoundary name="Status bar" compact><StatusBar /></ErrorBoundary>
  </footer>
</div>

<style>
  .workspace {
    height: 100%;
    display: flex;
    flex-direction: column;
    background: var(--ol-bg);
    min-width: 0;
  }

  .body {
    flex-grow: 1;
    display: flex;
    min-height: 0;
  }

  .center {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .side {
    width: 360px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    border-left: 1px solid var(--ol-border);
    background: var(--ol-surface);
    min-height: 0;
  }

  .side-scroll {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .machine-summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    text-align: left;
    margin: 16px 16px 4px;
    padding: 12px;
    border: 1px solid var(--ol-border);
    border-radius: var(--ol-radius-md);
    background: var(--ol-surface);
    flex-shrink: 0;
  }

  .machine-summary:hover {
    border-color: var(--ol-border-strong);
    background: var(--ol-surface-2);
  }

  .summary-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
    gap: 5px;
  }

  .summary-text strong {
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .summary-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    color: var(--ol-text-muted);
    font-size: var(--ol-fs-xs);
  }

  .sidebar-tabs {
    display: flex;
    flex-shrink: 0;
    margin: 4px 16px 0;
    border-bottom: 1px solid var(--ol-border);
  }

  .sidebar-tabs button {
    flex: 1;
    padding: 16px 12px 12px;
    border: 0;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    background: transparent;
    color: var(--ol-text-muted);
    font-weight: 600;
  }

  .sidebar-tabs button[aria-selected='true'] {
    color: var(--ol-text);
    border-bottom-color: var(--ol-signal);
  }

  .sidebar-tabs button:hover {
    color: var(--ol-text);
    background: var(--ol-surface-2);
  }

  .side-scroll > [hidden] {
    display: none;
  }

  .design-intro {
    margin: 0 16px;
    padding: 20px 0;
    border-bottom: 1px solid var(--ol-border);
  }

  .design-intro h2 {
    font-size: var(--ol-fs-xl);
    font-weight: 600;
    margin-bottom: 6px;
    letter-spacing: -0.025em;
  }

  .design-intro p,
  .preview-next p {
    color: var(--ol-text-muted);
    line-height: 1.5;
  }

  .import-action {
    padding: 0 16px 16px;
  }

  .import-action .btn {
    width: 100%;
  }

  .preview-next {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    border-top: 1px solid var(--ol-border);
  }

  .preview-next .btn {
    width: 100%;
  }

  .gcode-card {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 16px;
    padding: 10px 12px;
    border-radius: var(--ol-radius-md);
    border: 1px solid var(--ol-border);
    background: var(--ol-bg);
  }

  .gcode-text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .gcode-name {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .small {
    font-size: var(--ol-fs-xs);
  }

  .foot {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    border-top: 1px solid var(--ol-border);
    background: var(--ol-surface);
  }
  @media (max-width: 1100px) {
    .side {
      width: 320px;
    }
  }

  @media (max-width: 700px) {
    .workspace {
      height: auto;
      min-height: 100%;
      overflow-x: clip;
    }

    .body {
      display: grid;
      grid-template-columns: var(--ol-toolrail-w) minmax(0, 1fr);
      grid-template-rows: minmax(440px, 65vh) auto;
    }

    .center {
      min-height: 440px;
    }

    .body :global(.rail) {
      max-height: 65vh;
      min-height: 440px;
      overflow-y: auto;
    }

    .side {
      grid-column: 1 / -1;
      width: 100%;
      border-left: 0;
      border-top: 1px solid var(--ol-border);
    }

    .side-scroll {
      overflow: visible;
      flex: none;
    }

    .workspace.has-controls {
      padding-bottom: calc(72px + env(safe-area-inset-bottom));
    }

    .side :global([data-testid='stop']) {
      position: fixed;
      left: 16px;
      right: 16px;
      bottom: calc(12px + env(safe-area-inset-bottom));
      width: calc(100% - 32px);
      z-index: 40;
      box-shadow:
        0 0 0 12px var(--ol-surface),
        var(--ol-shadow-pop);
    }
  }
</style>
