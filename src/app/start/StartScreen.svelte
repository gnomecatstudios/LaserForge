<script lang="ts">
  import ConnectButton from '../connect/ConnectButton.svelte';
  import Cpu from '@lucide/svelte/icons/cpu';
  import Plus from '@lucide/svelte/icons/plus';
  import Download from '@lucide/svelte/icons/download';
  import FileCode from '@lucide/svelte/icons/file-code';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import Moon from '@lucide/svelte/icons/moon';
  import Sun from '@lucide/svelte/icons/sun';
  import CircleHelp from '@lucide/svelte/icons/circle-help';
  import Info from '@lucide/svelte/icons/info';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import FolderOpen from '@lucide/svelte/icons/folder-open';
  import Logo from '$lib/ui/Logo.svelte';
  import SafetyStrip from './SafetyStrip.svelte';
  import GithubMark from '$lib/ui/GithubMark.svelte';
  import ErrorBoundary from '$lib/ui/ErrorBoundary.svelte';
  import { REPO_URL } from '$lib/config/app';
  import { isWebSerialSupported } from 'libopenlaser/machine';
  import { relativeTime } from '../lib/format';
  import { preferences } from '../state/preferences.svelte';
  import { profiles } from '../state/profiles.svelte';
  import { route } from '../state/route.svelte';
  import { session } from '../state/session.svelte';
  import { ui } from '../state/ui.svelte';
  import ConnectHelpButton from '../connect/ConnectHelpButton.svelte';
  import * as actions from '../actions';
  import { sections } from '../state/sections.svelte';
  import { sidebar } from '../state/workspace.svelte';

  /** Show connection progress and setup when connecting from the welcome page. */
  function startConnected() {
    actions.ensureDocument();
    sidebar.showMachine();
  }

  const serial = isWebSerialSupported();
  const theme = $derived(preferences.value.theme === 'dark' ? 'dark' : 'light');
  const profile = $derived(profiles.active);
  const ORIGINS = { bl: 'Bottom left', tl: 'Top left', tr: 'Top right', br: 'Bottom right' } as const;

  function toggleTheme() {
    void preferences.update({ theme: theme === 'dark' ? 'light' : 'dark' });
  }
</script>

<div class="start" data-theme={theme} data-testid="start-screen">
  <header class="top">
    <Logo size={32} fontSize={19} />
    <nav aria-label="Main">
      <button type="button" class="icon-btn" aria-label="Help" title="Help" onclick={() => route.go('help')}
        ><CircleHelp size={18} /></button
      >
      <button
        type="button"
        class="icon-btn"
        aria-label="About"
        title="About"
        onclick={() => route.go('about')}><Info size={18} /></button
      >
      <a
        class="icon-btn"
        href={REPO_URL}
        target="_blank"
        rel="noopener"
        aria-label="Source code on GitHub"
        title="GitHub"><GithubMark /></a
      >
      <button
        type="button"
        class="icon-btn framed"
        aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        onclick={toggleTheme}
      >
        {#if theme === 'dark'}<Sun size={18} />{:else}<Moon size={18} />{/if}
      </button>
    </nav>
  </header>

  <main class="main">
    <section class="lead">
      <div class="hero">
        <h1>Make something<br />with your laser.</h1>
        <p>
          Create your design, preview the toolpath, then run your laser.<br />Your projects stay in this
          browser.
        </p>
      </div>

      <div class="ctas">
        <button
          type="button"
          class="btn big signal"
          onclick={() => actions.newProject()}
          data-testid="new-project"
        >
          <Plus size={22} />New project
        </button>
        <button type="button" class="btn big secondary" onclick={() => actions.openFile()}
          ><FolderOpen size={22} />Open file…</button
        >
      </div>

      <ol class="workflow" aria-label="From design to finished job">
        <li>
          <span class="step-number">1</span>
          <div>
            <h2>Design</h2>
            <p>Import art or add text and shapes</p>
          </div>
        </li>
        <li>
          <span class="step-number">2</span>
          <div>
            <h2>Preview</h2>
            <p>Check layers and toolpaths</p>
          </div>
        </li>
        <li>
          <span class="step-number">3</span>
          <div>
            <h2>Run</h2>
            <p>Connect, frame and start</p>
          </div>
        </li>
      </ol>

      <div class="file-actions">
        <button type="button" class="file-action" onclick={() => actions.importArt()}>
          <Download size={26} />
          <span class="action-copy"
            ><span class="action-title">Import art</span><span class="action-sub">SVG, DXF and images</span
            ></span
          >
          <ChevronRight size={20} />
        </button>
        <button type="button" class="file-action" onclick={() => actions.openGcodeFile()}>
          <FileCode size={26} />
          <span class="action-copy"
            ><span class="action-title">Send G-code</span><span class="action-sub"
              >.gcode, .nc, .ngc files</span
            ></span
          >
          <ChevronRight size={20} />
        </button>
      </div>

      <SafetyStrip />
    </section>

    <aside class="side">
      <ErrorBoundary name="Recent projects">
        <div class="panel recents">
          <div class="panel-head">
            <h2>Recent projects</h2>
          </div>
          {#if session.recents.length === 0}
            <p class="empty">Projects you open or create show up here.</p>
          {:else}
            <ul>
              {#each session.recents.slice(0, 6) as recent (recent.id)}
                <li class="recent">
                  <button type="button" class="recent-open" onclick={() => actions.openRecent(recent.id)}>
                    <!-- eslint-disable-next-line svelte/no-at-html-tags -- Thumbnail SVG built by thumbnail.ts with escaped values. -->
                    <span class="thumb">{@html recent.thumbnail}</span>
                    <span class="recent-text">
                      <span class="recent-name">{recent.name}</span>
                      <span class="recent-meta"
                        >{recent.layerCount}
                        {recent.layerCount === 1 ? 'layer' : 'layers'} · edited {relativeTime(
                          recent.updatedAt,
                        )}</span
                      >
                    </span>
                    <ChevronRight size={16} />
                  </button>
                  <button
                    type="button"
                    class="icon-btn sm forget"
                    aria-label="Remove {recent.name} from recent projects"
                    onclick={() => session.forget(recent.id)}
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </ErrorBoundary>

      <div class="panel machine" data-theme="dark">
        <div class="panel-head">
          <h2>Machine profile</h2>
          <button type="button" class="btn small ghost" onclick={() => (ui.profilesOpen = true)}
            >Change</button
          >
        </div>
        <dl class="specs">
          <div>
            <dt>Model</dt>
            <dd>{profile.name}</dd>
          </div>
          <div>
            <dt>Bed</dt>
            <dd class="mono">{profile.bedWidth} × {profile.bedHeight} mm</dd>
          </div>
          <div>
            <dt>Origin</dt>
            <dd>{ORIGINS[profile.originCorner]}</dd>
          </div>
        </dl>
        <div class="rule"></div>
        <div class="machine-actions">
          <ConnectButton size="big" testid="start-connect" before={startConnected} />
          <button
            type="button"
            class="btn big virtual"
            onclick={() => {
              sections.set('machine', false);
              void actions.startWithVirtualMachine();
            }}
            data-testid="try-virtual"
          >
            <Cpu size={18} />Try the virtual machine
          </button>
        </div>
        <div class="connection-help">
          <span class="serial-pill" class:missing={!serial} data-testid="serial-pill">
            <span class="dot"></span>{serial
              ? 'Web Serial available'
              : 'Machine control needs Chrome or Edge'}
          </span>
          <ConnectHelpButton />
        </div>
      </div>
    </aside>
  </main>

  <footer class="foot">
    <span>Free and open source · Runs on Chrome, Edge, Opera and Brave</span>
    <span class="foot-links">
      <button type="button" class="link" onclick={() => route.go('help')}>Help</button>
      <button type="button" class="link" onclick={() => route.go('about')}>About</button>
      <button type="button" class="link" onclick={() => (ui.tourOpen = true)}>Tour</button>
      <span class="mono">Offline ready</span>
    </span>
  </footer>
</div>

<style>
  .start {
    min-height: 100%;
    display: flex;
    flex-direction: column;
    background: var(--ol-bg);
    color: var(--ol-text);
  }

  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 20px clamp(16px, 4vw, 48px);
  }

  nav {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .icon-btn.framed {
    width: 40px;
    height: 40px;
    border: 1px solid var(--ol-border);
    background: var(--ol-surface);
    border-radius: var(--ol-radius-md);
  }

  .main {
    flex-grow: 1;
    width: 100%;
    max-width: 1392px;
    margin: 0 auto;
    padding: 24px clamp(16px, 4vw, 48px) 48px;
    display: grid;
    grid-template-columns: minmax(0, 1.7fr) minmax(340px, 1fr);
    gap: 48px;
    align-items: start;
  }

  .lead {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 28px;
  }

  .hero {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-top: 12px;
  }

  .serial-pill {
    display: inline-flex;
    align-self: flex-start;
    align-items: center;
    gap: 8px;
    min-height: 24px;
    font-size: var(--ol-fs-sm);
    color: var(--ol-text-muted);
  }

  .serial-pill .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--ol-go);
  }

  .serial-pill.missing {
    color: var(--ol-hold);
  }

  .serial-pill.missing .dot {
    background: var(--ol-hold);
  }

  h1 {
    font-size: clamp(44px, 6vw, 76px);
    line-height: 1.02;
    font-weight: 600;
    letter-spacing: -0.05em;
  }

  .hero p {
    font-size: 22px;
    line-height: 1.45;
    font-weight: 500;
    color: var(--ol-text-muted);
    max-width: 720px;
  }

  .ctas {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }

  .ctas .btn {
    height: 60px;
    min-width: 256px;
    font-size: 20px;
  }

  .ctas .btn.signal {
    min-width: 296px;
  }

  .btn.secondary {
    background: var(--ol-surface);
    border-color: var(--ol-border-strong);
  }

  .workflow {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 28px;
    list-style: none;
    margin: 4px 0;
    padding: 0;
  }

  .workflow li {
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: 14px;
  }

  .workflow li:not(:last-child)::after {
    position: absolute;
    content: '';
    top: 18px;
    right: -16px;
    width: 24px;
    height: 1px;
    background: var(--ol-border-strong);
  }

  .step-number {
    display: inline-flex;
    flex: 0 0 36px;
    height: 36px;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--ol-signal);
    border-radius: 50%;
    color: var(--ol-signal);
    font-size: var(--ol-fs-xl);
    font-weight: 500;
  }

  .workflow h2 {
    margin: 3px 0 4px;
    font-size: 21px;
  }

  .workflow p {
    margin: 0;
    padding-right: 10px;
    font-size: var(--ol-fs-lg);
    line-height: 1.5;
    color: var(--ol-text-muted);
  }

  .file-actions {
    display: flex;
    flex-direction: column;
    border-top: 1px solid var(--ol-border-strong);
  }

  .file-action {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 16px;
    border: 0;
    border-bottom: 1px solid var(--ol-border-strong);
    background: transparent;
    text-align: left;
    color: var(--ol-text);
  }

  .file-action:hover {
    background: var(--ol-surface-2);
  }

  .file-action > :global(svg:first-child) {
    flex-shrink: 0;
    color: var(--ol-signal);
  }

  .file-action > :global(svg:last-child) {
    color: var(--ol-text-muted);
  }

  .action-copy {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .action-title {
    font-size: 20px;
    font-weight: 600;
  }

  .action-sub {
    font-size: var(--ol-fs-lg);
    color: var(--ol-text-muted);
  }

  .side {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 22px;
  }

  .panel {
    border-radius: var(--ol-radius-xl);
    padding: 22px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    background: var(--ol-surface);
    border: 1px solid var(--ol-border);
    color: var(--ol-text);
  }

  .panel-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  h2 {
    font-size: 22px;
    font-weight: 600;
  }

  .link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 0;
    background: none;
    padding: 0;
    color: var(--ol-signal);
    font-size: var(--ol-fs-md);
  }

  .link:hover {
    text-decoration: underline;
  }

  .empty {
    color: var(--ol-text-muted);
    font-size: 16px;
  }

  ul {
    list-style: none;
    margin: 0 -10px;
    padding: 0;
  }

  .recent {
    position: relative;
    display: flex;
    align-items: center;
  }

  .recent-open {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px;
    border-radius: 12px;
    border: 0;
    background: transparent;
    color: var(--ol-text);
    text-align: left;
  }

  .recent-open:hover {
    background: var(--ol-surface-2);
  }

  .thumb {
    width: 64px;
    height: 64px;
    border-radius: var(--ol-radius-md);
    overflow: hidden;
    flex-shrink: 0;
    display: flex;
  }

  .thumb :global(svg) {
    width: 100%;
    height: 100%;
  }

  .recent-text {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .recent-name {
    font-size: var(--ol-fs-lg);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .recent-meta {
    color: var(--ol-text-muted);
  }

  .forget {
    position: absolute;
    right: 34px;
    opacity: 0;
  }

  .recent:hover .forget,
  .forget:focus-visible {
    opacity: 1;
  }

  .specs {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
    margin: 0;
  }

  .specs div {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  dt {
    color: var(--ol-text-muted);
    font-size: var(--ol-fs-lg);
  }

  dd {
    margin: 0;
    font-weight: 500;
    font-size: 18px;
    overflow-wrap: anywhere;
  }

  .machine-actions {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .machine-actions :global(.split) {
    display: flex;
  }

  .machine-actions :global(.btn.big) {
    font-size: 18px;
  }

  .virtual {
    background: var(--ol-start-bg);
    color: var(--ol-start-text);
    border-color: var(--ol-start-bg);
  }

  .connection-help {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .connection-help :global(.help) {
    justify-content: flex-start;
    padding-left: 0;
    height: 28px;
  }

  .rule {
    height: 1px;
    background: var(--ol-border);
  }

  .foot {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
    padding: 18px clamp(16px, 4vw, 48px);
    border-top: 1px solid var(--ol-border);
    color: var(--ol-text-muted);
  }

  .foot-links {
    display: flex;
    gap: 16px;
    align-items: center;
  }

  .foot .link {
    color: var(--ol-text-muted);
  }

  @media (max-width: 1100px) {
    .main {
      gap: 28px;
      grid-template-columns: minmax(0, 1.5fr) minmax(300px, 1fr);
    }

    h1 {
      font-size: clamp(44px, 5.4vw, 60px);
    }

    .hero p {
      font-size: var(--ol-fs-xl);
    }

    .ctas .btn,
    .ctas .btn.signal {
      min-width: 180px;
      font-size: 17px;
    }

    .workflow {
      gap: 16px;
    }

    .workflow li {
      gap: 8px;
    }

    .workflow li::after {
      display: none;
    }

    .step-number {
      flex-basis: 28px;
      height: 28px;
      font-size: var(--ol-fs-lg);
    }

    .workflow h2 {
      font-size: 18px;
    }

    .workflow p {
      padding-right: 0;
      font-size: var(--ol-fs-sm);
    }
  }

  @media (max-width: 850px) {
    .main {
      grid-template-columns: minmax(0, 1fr);
    }

    .side {
      width: 100%;
    }

    .hero {
      padding-top: 0;
    }

    h1 {
      font-size: clamp(40px, 8vw, 64px);
    }

    .workflow p {
      font-size: var(--ol-fs-lg);
    }
  }

  @media (max-width: 480px) {
    .top {
      gap: 8px;
      padding-top: 16px;
      padding-bottom: 16px;
    }

    nav {
      gap: 0;
    }

    .main {
      padding-top: 12px;
      padding-bottom: 28px;
    }

    .lead {
      gap: 24px;
    }

    .ctas {
      gap: 10px;
    }

    .ctas .btn,
    .ctas .btn.signal {
      flex: 1 1 140px;
      min-width: 0;
      height: 52px;
      padding: 0 12px;
    }

    .workflow {
      gap: 14px;
      grid-template-columns: minmax(0, 1fr);
    }

    .workflow li {
      gap: 12px;
    }

    .workflow h2 {
      margin-top: 2px;
    }

    .file-action {
      padding: 14px 8px;
      gap: 16px;
    }

    .panel {
      padding: 18px;
    }

    .forget {
      opacity: 1;
    }
  }
</style>
