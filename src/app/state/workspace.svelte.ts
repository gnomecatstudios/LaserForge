import { sections } from './sections.svelte';
import { editor } from './editor.svelte';

export type SidebarPanel = 'design' | 'machine';

/** The sidebar follows the task being worked on without changing the design/preview canvas. */
class Sidebar {
  current = $state<SidebarPanel>('design');
  /** Preserve explicit navigation when connecting creates a project just before Workspace mounts. */
  requestedProjectId: string | null = null;

  showDesign(): void {
    this.current = 'design';
  }

  showMachine(): void {
    this.requestedProjectId = editor.project?.id ?? null;
    sections.set('machine', true);
    this.current = 'machine';
  }

  select(panel: SidebarPanel): void {
    if (panel === 'machine') this.showMachine();
    else this.showDesign();
  }
}

export const sidebar = new Sidebar();
