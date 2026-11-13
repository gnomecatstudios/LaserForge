import { APP_VERSION } from '$lib/config/app';
import { toast } from '$lib/ui/toasts.svelte';
import { connectedSession } from '../machines/registry';
import { fetchRelease, isNewer, isPlatform, type Platform, type Release } from './releases';

class Updates {
  open = $state(false);
  checking = $state(false);
  error = $state(false);
  release = $state.raw<Release | null>(null);
  platform = $state<Platform | ''>('');
  get available() {
    return !!this.release && isNewer(this.release.version, APP_VERSION);
  }
}
export const updates = new Updates();

export async function checkForUpdates(manual = true): Promise<void> {
  if (manual && connectedSession()) {
    toast.info('Disconnect the laser before checking for updates.');
    return;
  }
  if (manual) updates.open = true;
  if (updates.checking) return;
  updates.checking = true;
  updates.error = false;
  try {
    updates.release = await fetchRelease();
    if (updates.available) updates.open = true;
  } catch {
    updates.error = true;
  } finally {
    updates.checking = false;
  }
}

/** Native packages embed their exact architecture; browser UA strings cannot identify ARM reliably. */
export async function installUpdateChecks(): Promise<void> {
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(location.hostname)) return;
  try {
    const response = await fetch('./portable-platform.json', {
      signal: AbortSignal.timeout(3_000),
      cache: 'no-store',
    });
    if (!response.ok) return;
    const data: unknown = await response.json();
    if (!data || typeof data !== 'object' || !('platform' in data) || !isPlatform(data.platform)) return;
    updates.platform = data.platform;
    await checkForUpdates(false);
  } catch {
    // Normal for the web edition, older launchers, and an offline machine.
  }
}
