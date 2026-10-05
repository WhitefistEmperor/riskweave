import { test, expect } from '@playwright/test';
import {
  installWorkspace,
  candidateResult,
  runId,
  workspaceUrl,
} from './workspace-fixtures';

test('large saved networks retain every entity and link with usable inspection', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await installWorkspace(page);
  const data = structuredClone(candidateResult);
  const ids = Array.from(
    { length: 1200 },
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
  await page.goto(workspaceUrl + '&view=evidence');
  await page.getByRole('tab', { name: 'Network', exact: true }).click();
  await expect(page.locator('.network-scope')).toContainText(
    '1201 entities · 1200 explicit links',
  );
  await page.getByRole('button', { name: 'Fit graph', exact: true }).click();
  await page.getByRole('combobox', { name: 'Entity', exact: true }).click();
  await expect(page.getByRole('listbox').getByRole('option')).toHaveCount(1201);
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
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await expect(
    page.getByRole('tab', { name: 'Evidence', exact: true }),
  ).toHaveAttribute('aria-selected', 'true');
  expect(errors).toEqual([]);
});
