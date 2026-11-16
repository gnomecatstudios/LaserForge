import {
  booleanObjects,
  booleanPaths,
  makeId,
  type BooleanOperation,
  type VectorObject,
} from 'libopenlaser/project';
import { toast } from '$lib/ui/toasts.svelte';
import { editor } from './state/editor.svelte';

export function unitePaths(objects: VectorObject[]) {
  return booleanPaths(objects, 'union');
}

export function booleanSelectionIssue(): string | null {
  const project = editor.project;
  if (!project || editor.selection.size < 2) return 'Select at least two closed vector objects.';
  try {
    booleanPaths(
      [...editor.selection].map((id) => project.objects.find((o) => o.id === id)!),
      'union',
    );
    if (
      [...editor.selection].some(
        (id) =>
          !project.layers.find((l) => l.id === project.objects.find((o) => o.id === id)?.layerId)?.visible,
      )
    )
      return 'Selected objects must belong to visible layers.';
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : 'Invalid vector geometry.';
  }
}

export function booleanSelection(operation: BooleanOperation): boolean {
  if (!editor.project) return false;
  try {
    const result = booleanObjects(editor.project, [...editor.selection], operation, makeId());
    editor.commit(() => result.project);
    editor.select(result.object ? [result.object.id] : []);
    editor.tool = 'select';
    if (!result.object)
      toast.info('The Boolean result is empty; the selected operands were removed. Undo restores them.');
    return true;
  } catch (error) {
    toast.warning(error instanceof Error ? error.message : 'Unable to calculate Boolean geometry.');
    return false;
  }
}
export function uniteSelection() {
  if (booleanSelection('union') && editor.selection.size) editor.tool = 'node';
}
