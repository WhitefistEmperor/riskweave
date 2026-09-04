import { test, expect } from '@playwright/test';
import {
  installWorkspace,
  runId,
  candidateResult,
  workspaceUrl,
  investigationId,
} from './workspace-fixtures';

for (const width of [1440, 1280, 1024, 768]) {
  test(`analyst workspace is usable at ${width}px with keyboard navigation`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 1050 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await installWorkspace(page);
    await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
      route.fulfill({ json: candidateResult }),
    );
    await page.goto('/');
    await expect(page).toHaveURL(/\/investigations$/);
    await expect(
      page.getByRole('heading', { name: 'Investigations', exact: true }),
    ).toBeVisible();
    await page.keyboard.press('Tab');
    await expect(
      page.getByRole('link', { name: 'Skip to investigation' }),
    ).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('#workspace-content')).toBeFocused();
    await page.goto(workspaceUrl);
    await expect(
      page.getByRole('heading', { name: 'Persisted findings' }),
    ).toBeVisible();
    await page.getByRole('button', { name: /^Open ring / }).click();
    await expect(
      page.getByRole('region', { name: 'Selected candidate' }),
    ).toBeFocused();
    for (const name of ['Network', 'Evidence', 'Timeline', 'Investigator']) {
      await page.getByRole('tab', { name, exact: true }).click();
      await expect(
        page.getByRole('tab', { name, exact: true }),
      ).toHaveAttribute('aria-selected', 'true');
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
    }
    await page.getByRole('tab', { name: 'Network', exact: true }).click();
    await page.getByRole('combobox', { name: 'Entity', exact: true }).focus();
    await page.keyboard.press('Enter');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await expect(page.locator('.selection-details')).toContainText(
      'ui-customer',
    );
    await page.getByRole('button', { name: 'Expand graph' }).click();
    await expect(page.locator('.evidence-canvas')).toHaveCSS('height', '640px');
    await page.getByRole('button', { name: 'Compact graph' }).click();
    await expect(page.locator('.evidence-canvas')).toHaveCSS('height', '460px');
    await page.getByRole('button', { name: 'Toggle Sidebar' }).click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    expect(errors).toEqual([]);
  });
}

test('evidence pagination exposes all rows and full identifiers accessibly', async ({
  page,
}) => {
  await installWorkspace(page);
  const data = structuredClone(candidateResult);
  data.rings[0].queries.get_shared_devices = Array.from(
    { length: 51 },
    (_, i) => ({
      entity_id: `fixture-device-${i.toString().padStart(3, '0')}`,
      customer_ids: ['fixture-customer-one', 'fixture-customer-two'],
      customer_count: 2,
      event_count: 2,
    }),
  );
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({ json: data }),
  );
  await page.goto(workspaceUrl + '&view=evidence');
  await page
    .getByRole('button', { name: 'Shared devices', exact: true })
    .click();
  await expect(page.getByText('1–25 of 51 rows')).toBeVisible();
  await page.getByText('CE-000', { exact: true }).click();
  await expect(
    page.getByText('fixture-device-000', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Next rows' }).click();
  await expect(page.getByText('26–50 of 51 rows')).toBeVisible();
  await page.getByRole('button', { name: 'Next rows' }).click();
  await expect(page.getByText('51–51 of 51 rows')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next rows' })).toBeDisabled();
});

test('cancelled page polling stops and saved state resumes on revisit', async ({
  page,
}) => {
  const { run } = await import('./workspace-fixtures');
  await installWorkspace(page, { ...run, status: 'running' });
  let reads = 0;
  await page.route(`**/api/v1/runs/${runId}`, (route) => {
    reads += 1;
    return route.fulfill({ json: { ...run, status: 'running' } });
  });
  await page.goto(workspaceUrl);
  await expect(page.getByRole('status')).toContainText('running');
  await page.goto('/investigations');
  await expect(
    page.getByRole('heading', { name: 'Saved investigations' }),
  ).toBeVisible();
  const stoppedAt = reads;
  await page.waitForTimeout(2200);
  expect(reads).toBe(stoppedAt);
  await page.goto(`/investigations/${investigationId}?run=${runId}`);
  await expect(page.getByRole('status')).toContainText('running');
  expect(reads).toBeGreaterThan(stoppedAt);
});
