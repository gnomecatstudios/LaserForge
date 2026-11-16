<script lang="ts">
  import type { Snippet } from 'svelte';
  import { ContextMenu } from 'bits-ui';
  import Scissors from '@lucide/svelte/icons/scissors';
  import Copy from '@lucide/svelte/icons/copy';
  import ClipboardPaste from '@lucide/svelte/icons/clipboard-paste';
  import CopyPlus from '@lucide/svelte/icons/copy-plus';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import ChevronRight from '@lucide/svelte/icons/chevron-right';
  import Combine from '@lucide/svelte/icons/combine';
  import { editor } from '../state/editor.svelte';
  import * as actions from '../edit-actions';
  import { BOOLEAN_COMMANDS } from '../shortcuts';
  import { formatCombo } from '../lib/keys';
  import { booleanSelection, booleanSelectionIssue } from '../unite';
  import BooleanIcon from './BooleanIcon.svelte';

  let {
    children,
    disabled,
    oncontextmenu,
  }: { children: Snippet; disabled: boolean; oncontextmenu: (event: MouseEvent) => void } = $props();
  let open = $state(false);
  const selected = $derived(editor.project?.objects.filter((o) => editor.selection.has(o.id)) ?? []);
  const editable = $derived(selected.length > 0 && selected.every((o) => !o.locked));
  const issue = $derived(open ? booleanSelectionIssue() : null);
  const base = $derived(
    editor.project?.objects.find((o) => o.id === [...editor.selection][0])?.name ?? 'first selected object',
  );
  const edits = [
    { label: 'Cut', key: 'Mod+X', icon: Scissors, run: actions.cutSelection, editable: true },
    { label: 'Copy', key: 'Mod+C', icon: Copy, run: actions.copySelection, editable: false },
    { label: 'Paste', key: 'Mod+V', icon: ClipboardPaste, run: actions.paste, editable: false },
    { label: 'Duplicate', key: 'Mod+D', icon: CopyPlus, run: actions.duplicateSelection, editable: false },
  ];
</script>

<ContextMenu.Root bind:open>
  <ContextMenu.Trigger {disabled} {oncontextmenu} style="display: contents;">
    {@render children()}
  </ContextMenu.Trigger>
  <ContextMenu.Portal>
    <ContextMenu.Content
      class="ol-menu canvas-menu"
      data-canvas-menu
      collisionPadding={8}
      preventScroll={false}
      onCloseAutoFocus={() =>
        document.querySelector<HTMLCanvasElement>('[data-testid="bed-canvas"]')?.focus()}
    >
      {#each edits as edit (edit.label)}
        <ContextMenu.Item
          class="ol-menu-item"
          disabled={edit.label === 'Paste'
            ? !actions.canPaste()
            : edit.editable
              ? !editable
              : !selected.length}
          onSelect={edit.run}
        >
          <edit.icon size={15} /><span>{edit.label}</span><span class="ol-menu-keys mono"
            >{formatCombo(edit.key)}</span
          >
        </ContextMenu.Item>
      {/each}
      <ContextMenu.Separator class="ol-menu-sep" />
      <ContextMenu.Sub>
        <ContextMenu.SubTrigger
          class="ol-menu-item"
          disabled={!!issue}
          title={issue ?? `Subtract uses ${base} as the base (first selected).`}
        >
          <Combine size={15} /><span>Boolean</span><ChevronRight size={15} />
        </ContextMenu.SubTrigger>
        <ContextMenu.Portal>
          <ContextMenu.SubContent class="ol-menu canvas-menu" data-canvas-menu collisionPadding={8}>
            {#each BOOLEAN_COMMANDS as command (command.operation)}
              <ContextMenu.Item
                class="ol-menu-item"
                onSelect={() => booleanSelection(command.operation)}
                title={command.operation === 'subtract'
                  ? `Base: ${base}. All later selections are subtracted from it.`
                  : undefined}
              >
                <BooleanIcon operation={command.operation} /><span>{command.label}</span><span
                  class="ol-menu-keys mono">{formatCombo(command.keys)}</span
                >
              </ContextMenu.Item>
            {/each}
          </ContextMenu.SubContent>
        </ContextMenu.Portal>
      </ContextMenu.Sub>
      <ContextMenu.Separator class="ol-menu-sep" />
      <ContextMenu.Item class="ol-menu-item" disabled={!editable} onSelect={actions.deleteSelection}>
        <Trash2 size={15} /><span>Delete</span><span class="ol-menu-keys mono">{formatCombo('Delete')}</span>
      </ContextMenu.Item>
    </ContextMenu.Content>
  </ContextMenu.Portal>
</ContextMenu.Root>

<style>
  :global(.canvas-menu) {
    max-width: calc(100vw - 16px);
    max-height: var(--bits-context-menu-content-available-height, calc(100vh - 16px));
    overflow-y: auto;
  }
  :global(.canvas-menu .ol-menu-item) {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  :global(.canvas-menu .ol-menu-item > span:first-of-type) {
    flex: 1;
  }
</style>
