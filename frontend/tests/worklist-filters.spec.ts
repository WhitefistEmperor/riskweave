import { expect, test, type Page } from '@playwright/test';
import { record } from './workspace-fixtures';

async function worklist(page: Page) {
  const records = Array.from({ length: 12 }, (_, index) => ({
    ...record,
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
    name: index >= 10 ? `Needle case ${index + 1}` : `Other case ${index + 1}`,
    status: index === 11 ? 'failed' : 'completed',
  }));
  const historyReads: string[] = [];
  await page.route('**/api/v1/session', (route) =>
    route.fulfill({
      json: {
        user_id: 'local-analyst',
        authentication_mode: 'development',
        production_authentication: false,
      },
    }),
  );
  await page.route('**/api/v1/investigations/page?*', (route) => {
    const params = new URL(route.request().url()).searchParams;
    const needle = (params.get('search') ?? '').trim().toLowerCase();
    const selected = params.get('status');
    const filtered = records.filter(
      (item) =>
        (!needle ||
          item.name.toLowerCase().includes(needle) ||
          item.id.includes(needle)) &&
        (!selected || item.status === selected),
    );
    const offset = Number(params.get('offset'));
    return route.fulfill({
      json: {
        items: filtered.slice(offset, offset + 10),
        total: records.length,
        matched: filtered.length,
        offset,
        limit: 10,
      },
    });
  });
  await page.route('**/api/v1/investigations/*/runs', (route) => {
    historyReads.push(route.request().url());
    return route.fulfill({ json: [] });
  });
  await page.goto('/investigations');
  await expect(page.getByText('12 matching of 12 saved')).toBeVisible();
  return { records, historyReads };
}

test('search covers later pages, combines case status and resets pagination', async ({
  page,
}) => {
  const { historyReads } = await worklist(page);
  await expect(
    page.getByRole('link', { name: 'Open Other case 1', exact: true }),
  ).toBeVisible();
  await expect.poll(() => historyReads.length).toBe(10);
  await expect(page.getByText('No runs yet', { exact: true })).toHaveCount(10);
  expect(historyReads.some((url) => url.endsWith('000000000011/runs'))).toBe(
    false,
  );
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(
    page.getByRole('link', { name: 'Open Needle case 12', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('No runs yet', { exact: true })).toHaveCount(2);
  await expect.poll(() => historyReads.length).toBe(12);
  await page.getByLabel('Search investigations').fill(' NEEDLE ');
  await expect(page.getByText('2 matching of 12 saved')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Previous', exact: true }),
  ).toBeDisabled();
  await page.getByLabel('Case status', { exact: true }).selectOption('failed');
  await expect(page.getByText('1 matching of 12 saved')).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Open Needle case 12', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Open Needle case 11', exact: true }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.getByText('12 matching of 12 saved')).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Open Other case 1', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('No runs yet', { exact: true })).toHaveCount(10);
  expect(historyReads).toHaveLength(12);
});

test('case ID search and unmatched filters never substitute another saved case', async ({
  page,
}) => {
  const { records } = await worklist(page);
  await page.getByLabel('Search investigations').fill(records[11].id);
  await expect(page.getByText('1 matching of 12 saved')).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Open Needle case 12', exact: true }),
  ).toBeVisible();
  await page.getByLabel('Case status', { exact: true }).selectOption('running');
  await expect(
    page.getByRole('heading', {
      name: 'No investigations match these filters',
    }),
  ).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
  await expect(
    page.getByRole('heading', { name: 'No investigations yet' }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(
    page.getByRole('link', { name: 'Open Other case 1', exact: true }),
  ).toBeVisible();
});

test('a page with mismatched request metadata fails closed', async ({
  page,
}) => {
  const { records } = await worklist(page);
  await page.route('**/api/v1/investigations/page?*', (route) =>
    route.fulfill({
      json: {
        items: [records[11]],
        total: 12,
        matched: 1,
        offset: 10,
        limit: 10,
      },
    }),
  );
  await page.getByLabel('Search investigations').fill('Needle');
  await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Open Needle case 12', exact: true }),
  ).toHaveCount(0);
  await expect(page.getByRole('table')).toHaveCount(0);
});

test('a refreshed case version reloads its cached analysis history', async ({
  page,
}) => {
  const { records, historyReads } = await worklist(page);
  await expect(page.getByText('No runs yet', { exact: true })).toHaveCount(10);
  records[0].updated_at = '2026-01-03T00:00:00Z';
  await page.getByLabel('Search investigations').fill(records[0].id);
  await expect(page.getByText('1 matching of 12 saved')).toBeVisible();
  await expect(page.getByText('No runs yet', { exact: true })).toHaveCount(1);
  await expect
    .poll(
      () =>
        historyReads.filter((url) => url.endsWith('000000000001/runs')).length,
    )
    .toBe(2);
});
