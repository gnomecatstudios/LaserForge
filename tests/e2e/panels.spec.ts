import { expect, test } from '@playwright/test';
import { dragOnCanvas, newProject, prepare, selectMachine, selectDesign } from './helpers';

test.beforeEach(async ({ page }) => prepare(page));

test('Design prioritizes the selection before layers and remembers folded sections', async ({ page }) => {
  await newProject(page);
  await page.getByTestId('tool-text').click();
  await dragOnCanvas(page, [0.4, 0.4], [0.5, 0.5]);
  await expect(page.getByTestId('text-inspector')).toBeVisible();

  const side = page.locator('#workspace-design-panel');
  const order = await side
    .locator('[data-testid^="section-"]')
    .evaluateAll((els) => els.map((e) => e.getAttribute('data-testid')));
  expect(order).toEqual(['section-inspector', 'section-layers']);

  // Folding keeps the head, hides the rest, and is remembered after a reload.
  await page.getByTestId('section-layers').click();
  await expect(page.getByTestId('section-layers')).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByTestId('layer-settings')).toHaveCount(0);
  // Let the autosave land, so the reload reopens the project.
  await expect(page.getByText('Saved in browser')).toBeVisible({ timeout: 10_000 });
  await page.reload();
  await expect(page.getByTestId('section-layers')).toHaveAttribute('aria-expanded', 'false');
  await page.getByTestId('section-layers').click();
  await expect(page.getByTestId('layer-settings')).toBeVisible();
});

test('virtual practice starts with design and machine controls remain one tab away', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('try-virtual').click();
  await expect(page.getByTestId('workspace')).toBeVisible();
  await expect(page.getByTestId('sidebar-design')).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByTestId('stop')).toBeVisible();
  await selectMachine(page);
  await expect(page.getByTestId('section-machine')).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByTestId('change-machine')).toBeVisible();
});

test('a reload carries on in the project; a new visit starts on the welcome page', async ({
  page,
  context,
}) => {
  await newProject(page);
  await page.getByTestId('tool-rect').click();
  await dragOnCanvas(page, [0.4, 0.4], [0.5, 0.5]);
  // Let the autosave land.
  await expect(page.getByText('Saved in browser')).toBeVisible({ timeout: 10_000 });
  await page.reload();
  await expect(page.getByTestId('workspace')).toBeVisible();

  const visit = await context.newPage();
  await visit.goto('/');
  await expect(visit.getByTestId('start-screen')).toBeVisible();
  await expect(visit.locator('.recent-open')).toHaveCount(1);
});

test('sidebar navigation preserves edits and keyboard tabs expose the right controls', async ({ page }) => {
  await newProject(page);
  await expect(page.getByTestId('sidebar-design')).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByTestId('console-input')).toBeHidden();
  await expect(page.getByTestId('preview-job')).toBeDisabled();
  await page.getByTestId('empty-add-text').click();
  await expect(page.getByTestId('empty-hint')).toBeHidden();
  await expect(page.getByTestId('text-edit')).toBeFocused();
  await page.keyboard.type('Forge');
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('text-content')).toHaveValue('Forge');

  await page.getByTestId('sidebar-design').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByTestId('sidebar-machine')).toBeFocused();
  await expect(page.getByTestId('connect-virtual')).toBeVisible();
  await expect(page.getByTestId('text-inspector')).toBeHidden();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByTestId('text-content')).toHaveValue('Forge');
  await expect(page.getByTestId('section-layers')).toBeVisible();
  await expect(page.getByTestId('status-bar')).toContainText('1 object');

  await selectMachine(page);
  await page.getByTestId('sidebar-machine').press('Home');
  await expect(page.getByTestId('sidebar-design')).toBeFocused();
  await selectDesign(page);
  await expect(page.getByTestId('text-content')).toHaveValue('Forge');
});

test('drawing and selecting on the bed opens the Design controls from Machine', async ({ page }) => {
  await newProject(page);
  await selectMachine(page);
  await page.getByTestId('tool-rect').click();
  await expect(page.getByTestId('sidebar-design')).toHaveAttribute('aria-selected', 'true');
  await dragOnCanvas(page, [0.3, 0.3], [0.4, 0.4]);
  await expect(page.getByTestId('layer-settings')).toBeVisible();
  await selectMachine(page);
  const canvas = (await page.getByTestId('bed-canvas').boundingBox())!;
  await page.mouse.click(canvas.x + canvas.width * 0.35, canvas.y + canvas.height * 0.3);
  await expect(page.getByTestId('sidebar-design')).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByTestId('status-bar')).toContainText('1 selected');
});
