import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import {
  installWorkspace,
  candidateResult,
  runId,
  workspaceUrl,
} from './workspace-fixtures';

async function installLargeNetwork(page: Page, count = 1200) {
  await installWorkspace(page);
  const data = structuredClone(candidateResult);
  const ids = Array.from(
    { length: count },
    (_, i) => `large-customer-${i.toString().padStart(4, '0')}`,
  );
  data.rings[0].candidate.member_entity_ids = ids;
  data.rings[0].queries.get_ring_members = ids.map((entity_id) => ({
    entity_id,
    entity_type: 'CUSTOMER',
    created_at: '2025-01-01T00:00:00Z',
  }));
  data.rings[0].queries.get_shared_devices = [
    {
      entity_id: 'large-shared-device',
      customer_ids: ids,
      customer_count: ids.length,
      event_count: ids.length,
    },
  ];
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({ json: data }),
  );
}

test('large saved networks retain every entity and link with usable inspection', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await installLargeNetwork(page);
  await page.goto(workspaceUrl + '&view=evidence');
  await page.getByRole('tab', { name: 'Network', exact: true }).click();
  await expect(page.locator('.network-scope')).toContainText(
    '1201 entities · 1200 explicit links',
  );
  await page.getByRole('button', { name: 'Fit graph', exact: true }).click();
  await page.getByRole('combobox', { name: 'Entity', exact: true }).click();
  await expect(page.getByRole('listbox').getByRole('option')).toHaveCount(64);
  await page.keyboard.press('Escape');
  await page
    .getByRole('button', { name: 'Next entity page', exact: true })
    .click();
  await page.getByRole('combobox', { name: 'Entity', exact: true }).click();
  await expect(
    page.getByRole('listbox').getByRole('option').filter({ hasText: '0064' }),
  ).toBeVisible();
  await page.keyboard.press('Escape');
  await page
    .getByRole('searchbox', { name: 'Find entity', exact: true })
    .fill('large-customer-1199');
  await page.getByRole('combobox', { name: 'Entity', exact: true }).click();
  await expect(page.getByRole('listbox').getByRole('option')).toHaveCount(1);
  await page
    .getByRole('listbox')
    .getByRole('option')
    .filter({ hasText: '1199' })
    .click();
  await expect(page.locator('.selection-details')).toContainText(
    'large-customer-1199',
  );
  await expect(page.locator('.selection-details')).toContainText(
    '1 explicit relationships shown.',
  );
  await page
    .getByRole('button', { name: 'Focus selected', exact: true })
    .click();
  await page
    .getByRole('searchbox', { name: 'Find relationship', exact: true })
    .fill('large-customer-1199');
  await page
    .getByRole('combobox', { name: 'Relationship', exact: true })
    .click();
  await expect(page.getByRole('listbox').getByRole('option')).toHaveCount(1);
  await page.getByRole('listbox').getByRole('option').first().click();
  await expect(page.locator('.selection-details')).toContainText(
    'large-customer-1199',
  );
  await expect(page.locator('.selection-details')).toContainText(
    'large-shared-device',
  );
  await page
    .getByRole('button', { name: 'Open source evidence', exact: true })
    .click();
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await expect(
    page.getByRole('tab', { name: 'Evidence', exact: true }),
  ).toHaveAttribute('aria-selected', 'true');
  expect(errors).toEqual([]);
});

test('leaving a preparing network cancels it and revisiting builds a complete fresh graph', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await installLargeNetwork(page, 8000);
  await page.goto(workspaceUrl + '&view=evidence');
  await page.getByRole('tab', { name: 'Network', exact: true }).click();
  await expect(
    page.getByRole('progressbar', { name: 'Network loading progress' }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Fit graph', exact: true }),
  ).toBeDisabled();
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await expect(
    page.getByRole('tab', { name: 'Evidence', exact: true }),
  ).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', { name: 'Network', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Fit graph', exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole('progressbar', { name: 'Network loading progress' }),
  ).toHaveCount(0);
  await expect(page.locator('.evidence-canvas')).toHaveCount(1);
  await expect(page.locator('.evidence-canvas canvas').first()).toBeVisible();
  await expect(page.locator('.network-scope')).toContainText(
    '8001 entities · 8000 explicit links',
  );
  await page.getByRole('combobox', { name: 'Entity', exact: true }).click();
  await expect(page.getByRole('listbox').getByRole('option')).toHaveCount(64);
  await page.keyboard.press('Escape');
  await page
    .getByRole('searchbox', { name: 'Find entity', exact: true })
    .fill('large-customer-7999');
  await page.getByRole('combobox', { name: 'Entity', exact: true }).click();
  await expect(page.getByRole('listbox').getByRole('option')).toHaveCount(1);
  await page
    .getByRole('listbox')
    .getByRole('option')
    .filter({ hasText: '7999' })
    .click();
  await expect(page.locator('.selection-details')).toContainText(
    'large-customer-7999',
  );
  await expect(page.locator('.selection-details')).toContainText(
    '1 explicit relationships shown.',
  );
  expect(errors).toEqual([]);
});
