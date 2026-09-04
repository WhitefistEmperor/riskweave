import { test, expect } from '@playwright/test';

test('real replay starts, pauses, steps, and resets without future candidate evidence', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(
    page.getByRole('heading', {
      name: 'See the ring. Not just the transaction.',
    }),
  ).toBeVisible();
  await expect(page.getByText('No focus candidate yet')).toBeVisible();
  await page.screenshot({
    path: '../outputs/phase4-overview.png',
    fullPage: true,
  });
  await page.getByRole('button', { name: 'Step', exact: true }).click();
  await expect(page.getByText('2 / 104 window events')).toBeVisible();
  await page.getByRole('button', { name: 'Start replay', exact: true }).click();
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await page.getByRole('button', { name: 'Reset', exact: true }).click();
  await expect(page.getByText('1 / 104 window events')).toBeVisible();
  await expect(page.getByText('No focus candidate yet')).toBeVisible();
  expect(errors).toEqual([]);
});

test('candidate opens prefix-only explorer, interactive graph, evidence, and timeline', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: 'Start replay', exact: true }).click();
  await page
    .getByRole('button', { name: 'Open Ring Explorer', exact: true })
    .click();
  await expect(
    page.getByText(/Replay snapshot · no later events included/),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Fit graph', exact: true }),
  ).toBeVisible();
  await page.getByRole('combobox', { name: 'Inspect graph node' }).click();
  await page.getByRole('option').first().click();
  await page
    .getByRole('button', { name: 'Focus selected', exact: true })
    .click();
  await page.getByRole('button', { name: 'Fit graph', exact: true }).click();
  await page
    .getByRole('button', { name: 'shared devices', exact: true })
    .click();
  await page.screenshot({
    path: '../outputs/phase4-explorer.png',
    fullPage: true,
  });
  await page.getByRole('tab', { name: 'Activity timeline' }).click();
  await expect(
    page.getByText('First connected candidate precursor', { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: '../outputs/phase4-timeline.png',
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
