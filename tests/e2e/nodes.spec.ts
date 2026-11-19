import { expect, test } from '@playwright/test';
import { newProject, prepare, dragOnCanvas } from './helpers';
test.beforeEach(async ({ page }) => prepare(page));
test('draws a closed path, moves a node, undoes and unites shapes', async ({ page }) => {
  await newProject(page);
  await page.getByTestId('tool-pen').click();
  const box = (await page.getByTestId('bed-canvas').boundingBox())!;
  const at = (x: number, y: number) => page.mouse.click(box.x + box.width * x, box.y + box.height * y);
  await at(0.4, 0.4);
  await at(0.6, 0.4);
  await at(0.5, 0.6);
  await at(0.4, 0.4);
  await expect(page.getByTestId('path-node')).toHaveCount(3);
  const node = page.getByTestId('path-node').first();
  const before = await node.getAttribute('style');
  const n = (await node.boundingBox())!;
  await page.mouse.move(n.x + n.width / 2, n.y + n.height / 2);
  await page.mouse.down();
  await page.mouse.move(n.x + 30, n.y + 25);
  await page.mouse.up();
  await expect(node).not.toHaveAttribute('style', before!);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(node).toHaveAttribute('style', before!);
  await page.getByTestId('tool-rect').click();
  await dragOnCanvas(page, [0.45, 0.45], [0.65, 0.65]);
  await page.keyboard.press('ControlOrMeta+a');
  await page.getByTestId('tool-unite').click();
  await expect(page.getByTestId('status-bar')).toContainText('1 object');
  await expect(page.getByTestId('path-node').first()).toBeVisible();
  await page.keyboard.press('ControlOrMeta+z');
  await expect(page.getByTestId('status-bar')).toContainText('2 objects');
});
test('finishes open paths and cancels unfinished drawing', async ({ page }) => {
  await newProject(page);
  await page.keyboard.press('b');
  const box = (await page.getByTestId('bed-canvas').boundingBox())!;
  await page.mouse.click(box.x + 200, box.y + 200);
  await page.mouse.click(box.x + 300, box.y + 250);
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('path-node')).toHaveCount(2);
  await page.keyboard.press('b');
  await page.mouse.click(box.x + 250, box.y + 300);
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('status-bar')).toContainText('1 object');
});

test('double-clicking a vector opens its nodes', async ({ page }) => {
  await newProject(page);
  await page.getByTestId('tool-rect').click();
  await dragOnCanvas(page, [0.4, 0.4], [0.6, 0.6]);
  const box = (await page.getByTestId('bed-canvas').boundingBox())!;
  await page.mouse.dblclick(box.x + box.width * 0.5, box.y + box.height * 0.4);
  await expect(page.getByTestId('tool-node')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('path-node')).toHaveCount(4);
});

test('clicking a selected path inserts a movable node and supports undo', async ({ page }) => {
  await newProject(page);
  await page.getByTestId('tool-rect').click();
  await dragOnCanvas(page, [0.4, 0.4], [0.6, 0.6]);
  await page.getByTestId('tool-node').click();
  await expect(page.getByTestId('path-node')).toHaveCount(4);
  const first = (await page.getByTestId('path-node').nth(0).boundingBox())!;
  const second = (await page.getByTestId('path-node').nth(1).boundingBox())!;
  await page.mouse.click(
    (first.x + second.x) / 2 + first.width / 2,
    (first.y + second.y) / 2 + first.height / 2,
  );
  await expect(page.getByTestId('path-node')).toHaveCount(5);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(page.getByTestId('path-node')).toHaveCount(4);
});

test('selecting a node and pressing Delete removes only that node', async ({ page }) => {
  await newProject(page);
  await page.getByTestId('tool-rect').click();
  await dragOnCanvas(page, [0.4, 0.4], [0.6, 0.6]);
  await page.getByTestId('tool-node').click();
  await expect(page.getByTestId('path-node')).toHaveCount(4);
  await page.getByTestId('path-node').nth(1).click();
  await expect(page.getByTestId('path-node').nth(1)).toHaveAttribute('aria-pressed', 'true');
  await page.keyboard.press('Delete');
  await expect(page.getByTestId('path-node')).toHaveCount(3);
  await expect(page.getByTestId('status-bar')).toContainText('1 object');
  await page
    .getByTestId('path-node')
    .first()
    .click({ modifiers: ['Alt'] });
  await expect(page.getByTestId('path-node')).toHaveCount(2);
  await page
    .getByTestId('path-node')
    .first()
    .click({ modifiers: ['Alt'] });
  await expect(page.getByTestId('path-node')).toHaveCount(2);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(page.getByTestId('path-node')).toHaveCount(3);
});

test('Delete in the node tool never removes the whole object', async ({ page }) => {
  await newProject(page);
  await page.getByTestId('tool-rect').click();
  await dragOnCanvas(page, [0.4, 0.4], [0.6, 0.6]);
  await page.getByTestId('tool-node').click();
  await page.getByTestId('path-node').nth(1).click();
  await page.keyboard.press('Delete');
  await page.keyboard.press('Delete');
  await expect(page.getByTestId('path-node')).toHaveCount(3);
  await expect(page.getByTestId('status-bar')).toContainText('1 object');
  await page.getByTestId('path-node').nth(1).click();
  await page.keyboard.press('v');
  await page.getByTestId('tool-node').click();
  await expect(page.getByTestId('path-node').nth(1)).toHaveAttribute('aria-pressed', 'false');
  await page.keyboard.press('Delete');
  await expect(page.getByTestId('path-node')).toHaveCount(3);
});

test('picks several nodes with Shift+click, box and Ctrl+A, then deletes or moves them together', async ({
  page,
}) => {
  await newProject(page);
  await page.getByTestId('tool-ellipse').click();
  await dragOnCanvas(page, [0.3, 0.3], [0.7, 0.7]);
  await page.getByTestId('tool-node').click();
  const nodes = page.getByTestId('path-node');
  await expect(nodes).toHaveCount(4);
  const picked = page.locator('[data-testid="path-node"][aria-pressed="true"]');

  // Shift+click adds and removes.
  await nodes.nth(0).click();
  await nodes.nth(1).click({ modifiers: ['Shift'] });
  await nodes.nth(2).click({ modifiers: ['Shift'] });
  await expect(picked).toHaveCount(3);
  await nodes.nth(2).click({ modifiers: ['Shift'] });
  await expect(picked).toHaveCount(2);

  // Dragging one picked node moves both by the same amount.
  const before = await Promise.all([0, 1, 3].map((i) => nodes.nth(i).boundingBox()));
  const a = before[0]!;
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
  await page.mouse.down();
  await page.mouse.move(a.x + a.width / 2 + 40, a.y + a.height / 2 + 30, { steps: 5 });
  await page.mouse.up();
  const after = await Promise.all([0, 1, 3].map((i) => nodes.nth(i).boundingBox()));
  for (const i of [0, 1]) {
    expect(after[i]!.x - before[i]!.x).toBeCloseTo(40, 0);
    expect(after[i]!.y - before[i]!.y).toBeCloseTo(30, 0);
  }
  expect(after[2]).toEqual(before[2]);
  await page.keyboard.press('ControlOrMeta+z');

  // Delete removes every picked node in one undo step.
  await page.keyboard.press('Delete');
  await expect(nodes).toHaveCount(2);
  await page.keyboard.press('ControlOrMeta+z');
  await expect(nodes).toHaveCount(4);

  // A box on empty canvas picks the nodes inside it and keeps the shape selected.
  const box = (await page.getByTestId('bed-canvas').boundingBox())!;
  const top = (await nodes.nth(0).boundingBox())!;
  await dragOnCanvas(page, [0.2, 0.2], [0.8, (top.y + 20 - box.y) / box.height]);
  await expect(page.getByTestId('status-bar')).toContainText('1 selected');
  await expect(picked).not.toHaveCount(0);
  const boxed = await picked.count();
  expect(boxed).toBeLessThan(4);

  // Ctrl+A picks every node; Delete stops at two.
  await page.keyboard.press('ControlOrMeta+a');
  await expect(picked).toHaveCount(4);
  await page.keyboard.press('Delete');
  await expect(nodes).toHaveCount(2);
  await expect(page.getByTestId('status-bar')).toContainText('1 object');

  // A plain click on empty canvas still deselects.
  await page.mouse.click(box.x + 10, box.y + 10);
  await expect(nodes).toHaveCount(0);
});
