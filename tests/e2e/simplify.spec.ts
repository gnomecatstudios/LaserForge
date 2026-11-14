import { expect, test } from '@playwright/test';
import { newProject, prepare } from './helpers';

test('previews closed-path simplification, cancels, applies and undoes', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await prepare(page);
  await newProject(page);
  await page.getByTestId('tool-pen').click();
  const box = (await page.getByTestId('bed-canvas').boundingBox())!;
  for (const [x, y] of [
    [0.3, 0.3],
    [0.4, 0.3],
    [0.5, 0.3],
    [0.5, 0.4],
    [0.5, 0.5],
    [0.4, 0.5],
    [0.3, 0.5],
    [0.3, 0.3],
  ]) {
    await page.mouse.click(box.x + box.width * x, box.y + box.height * y);
  }
  await expect(page.getByTestId('path-node')).toHaveCount(7);
  await page.getByTestId('tool-simplify').click();
  await expect(page.getByRole('img', { name: 'Path simplification preview' })).toBeVisible();
  await expect(page.getByTestId('simplify-count')).toContainText('7 → 4');
  await page.screenshot({ path: '/tmp/laserforge-simplify-preview.png' });
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByTestId('path-node')).toHaveCount(7);
  await page.getByTestId('tool-simplify').click();
  await page.getByRole('button', { name: 'Apply simplification' }).click();
  await expect(page.getByTestId('path-node')).toHaveCount(4);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(page.getByTestId('path-node')).toHaveCount(7);
  expect(errors).toEqual([]);
});
