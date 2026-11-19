import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';
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

/** Clicks the original at a point given as a share of the image's width and height. */
async function clickImage(page: Page, x: number, y: number): Promise<void> {
  const canvas = page.getByTestId('bitmap-original');
  const box = (await canvas.boundingBox())!;
  const size = await canvas.evaluate((c: HTMLCanvasElement) => ({ w: c.width, h: c.height }));
  const scale = Math.min(box.width / size.w, box.height / size.h);
  const left = box.x + (box.width - size.w * scale) / 2;
  const top = box.y + (box.height - size.h * scale) / 2;
  await page.mouse.click(left + x * size.w * scale, top + y * size.h * scale);
}

/** The preview pixel at a share of the image, as drawn (transparent areas show the checkerboard). */
function pixelAt(page: Page, x: number, y: number): Promise<number[]> {
  return page
    .getByTestId('bitmap-original')
    .evaluate(
      (c: HTMLCanvasElement, [px, py]) => [
        ...c.getContext('2d')!.getImageData(Math.floor(px * c.width), Math.floor(py * c.height), 1, 1).data,
      ],
      [x, y],
    );
}

test('Separate keys colors out of an image onto stacked layers', async ({ page }) => {
  await newProject(page);
  await importFile(page, 'layered.png');
  await page.getByTestId('view-bitmap').click();
  await page.getByTestId('bitmap-tab-separate').click();
  await expect(page.getByTestId('separate-panel')).toBeVisible();
  await expect.poll(() => pixelAt(page, 0.02, 0.02)).toEqual([0, 200, 0, 255]);

  // The backdrop, shadow included, is found from the edges and erased to transparency.
  await page.getByTestId('separate-background').click();
  await expect(page.getByTestId('separate-keys').getByRole('listitem')).toHaveCount(2);
  await expect(page.getByTestId('separate-share')).toContainText('% of the image selected');
  await page.getByTestId('separate-remove').click();
  await expect(page.getByText('Erased the selection.')).toBeVisible();
  await expect(page.getByTestId('layer-row')).toHaveCount(1);
  await expect(page.getByTestId('separate-keys')).toBeHidden();
  // Select background limited picks to the edge; applying it lets the next pick reach everywhere.
  await expect(page.getByRole('switch', { name: 'Connected areas only' })).not.toBeChecked();

  // The rest is cropped to the subjects: its corner is now the blue midground.
  await expect.poll(() => pixelAt(page, 0.02, 0.02)).toEqual([30, 40, 210, 255]);

  // The foreground: two separate red subjects, each its own object on a new layer.
  await clickImage(page, 0.2, 0.6);
  await page.getByText('One object per area').click();
  await page.getByTestId('separate-layer').click();
  await expect(page.getByText(/Moved 2 objects to/)).toBeVisible();
  await expect(page.getByTestId('layer-row')).toHaveCount(2);
  await expect(page.getByTestId('layer-row').nth(1).getByTestId('object-row')).toHaveCount(2);

  // Where the subjects were, the midground image is now transparent.
  await expect
    .poll(async () => {
      const [r, g, b] = await pixelAt(page, 0.2, 0.6);
      return r === g && g === b;
    })
    .toBe(true);

  // Undo puts the subjects back into the one image.
  await page.keyboard.press('ControlOrMeta+z');
  await expect(page.getByTestId('layer-row')).toHaveCount(1);
});
