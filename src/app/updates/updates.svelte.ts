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
  native = $state(false);
  nativeStatus = $state('idle');
  nativeError = $state('');
  nativeVersion = $state('');
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
    try {
      await refreshNativeUpdate();
    } catch {
      /* Older launchers use manual downloads. */
    }
    await checkForUpdates(false);
  } catch {
    // Normal for the web edition, older launchers, and an offline machine.
  }
}

let nativeToken = '';

async function refreshNativeUpdate(): Promise<void> {
  const response = await fetch('/api/portable-update', {
    cache: 'no-store',
    signal: AbortSignal.timeout(5_000),
  });
  if (!response.ok) throw new Error('Native updater unavailable');
  const data: unknown = await response.json();
  if (
    !data ||
    typeof data !== 'object' ||
    !('token' in data) ||
    typeof data.token !== 'string' ||
    !('status' in data) ||
    typeof data.status !== 'string'
  )
    throw new Error('Invalid updater response');
  nativeToken = data.token;
  updates.native = true;
  updates.nativeStatus = data.status;
  updates.nativeError = 'error' in data && typeof data.error === 'string' ? data.error : '';
  updates.nativeVersion = 'version' in data && typeof data.version === 'string' ? data.version : '';
}

export async function runNativeUpdate(action: 'download' | 'install'): Promise<void> {
  if (connectedSession() || !updates.native || ['downloading', 'restarting'].includes(updates.nativeStatus))
    return;
  if (
    action === 'install' &&
    !window.confirm('Save your project before continuing. Install the update and restart Laser Forge now?')
  )
    return;
  updates.nativeError = '';
  updates.nativeStatus = action === 'install' ? 'restarting' : 'downloading';
  try {
    const response = await fetch('/api/portable-update?action=' + action, {
      method: 'POST',
      headers: { 'X-LaserForge-Update': nativeToken },
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) throw new Error(await response.text());
    if (action === 'install') {
      // The helper releases the old server, installs, and launches the new app.
      // Keep this tab available if the OS blocks restarting or the network is offline.
      updates.nativeStatus = 'restarting';
      return;
    }
    do {
      await new Promise((resolve) => setTimeout(resolve, 1_000));
      await refreshNativeUpdate();
    } while (updates.nativeStatus === 'downloading');
  } catch (error) {
    updates.nativeStatus = 'error';
    updates.nativeError = error instanceof Error ? error.message : 'Update failed. Try again.';
  }
}
