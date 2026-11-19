import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { importFile, newProject, prepare } from './helpers';

test.beforeEach(async ({ page }) => prepare(page));

test('Bitmap mode shows the original beside the processed engraving and edits its settings', async ({
  page,
}) => {
  await newProject(page);
  await page.getByTestId('view-bitmap').click();
  await expect(page.getByTestId('bitmap-import')).toBeVisible();

  await page.getByTestId('view-design').click();
  await importFile(page, 'logo.png');
  await page.getByTestId('view-bitmap').click();

  const view = page.getByTestId('bitmap-view');
  await expect(view.getByRole('img', { name: /Original/ })).toBeVisible();
  const processed = page.getByTestId('bitmap-processed');
  await expect(processed).toBeVisible();
  await expect
    .poll(() => processed.evaluate((c: HTMLCanvasElement) => c.width), { timeout: 15_000 })
    .toBeGreaterThan(1);

  await page.getByTestId('bitmap-algorithm').selectOption('atkinson');
  await page.getByTestId('bitmap-compare-processed').click();
  await expect(view.getByRole('img', { name: /Original/ })).toBeHidden();

  // The setting lives on the layer, so Design mode sees the same choice.
  await page.getByTestId('view-design').click();
  await expect(page.getByTestId('tool-select')).toBeEnabled();
});

test('G-code export lives in the toolbar and the menu', async ({ page }) => {
  await newProject(page);
  await importFile(page, 'logo.png');
  await expect(page.getByTestId('export-gcode')).toHaveAttribute('aria-label', /Export G-code/);

  await page.getByTestId('app-menu').click();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByTestId('menu-export').click(),
  ]);
  expect(readFileSync(await download.path(), 'utf8').length).toBeGreaterThan(0);
});
