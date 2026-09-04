import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

test('real upload, asynchronous analysis, evidence, and revisit', async ({
  page,
}) => {
  const dataset = execFileSync(
    'uv',
    [
      'run',
      '--locked',
      '--extra',
      'dev',
      'python',
      '-c',
      'from ringsentinel import GenerationConfig, SyntheticPaymentGenerator; print(SyntheticPaymentGenerator(GenerationConfig(seed=105, transactions=1000)).generate().model_dump_json())',
    ],
    { cwd: resolve('..'), maxBuffer: 10_000_000 },
  );
  await page.goto('/investigations');
  const name = `Browser verification ${Date.now()}`;
  await page.getByLabel('Investigation name').fill(name);
  await page.getByRole('button', { name: 'Create investigation' }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  await page.getByLabel('Dataset file').setInputFiles({
    name: 'sample.json',
    mimeType: 'application/json',
    buffer: dataset,
  });
  await page.getByRole('button', { name: 'Upload dataset' }).click();
  await expect(
    page.getByRole('button', { name: 'Start analysis' }),
  ).toBeEnabled();
  await page.getByRole('button', { name: 'Start analysis' }).click();
  await expect(page.getByRole('status')).toContainText(
    /Analysis status: (queued|running)/,
  );
  await expect(page.getByRole('status')).toContainText(
    'Analysis status: completed',
  );
  await expect(
    page.getByRole('heading', { name: 'Persisted findings' }),
  ).toBeVisible();
  await page.getByText('Run provenance and integrity', { exact: true }).click();
  await expect(page.getByText(/Result SHA256:/)).toBeVisible();
  await page
    .getByRole('button', { name: 'Shared devices', exact: true })
    .click();
  await page.getByRole('tab', { name: 'Investigator', exact: true }).click();
  await page
    .getByRole('button', { name: 'Ask investigator', exact: false })
    .click();
  await expect(
    page.getByText('Deterministic evidence fallback · no LLM'),
  ).toBeVisible();
  await expect(page.locator('.answer-statements li')).not.toHaveCount(0);
  const savedUrl = page.url();
  expect(savedUrl).toContain('?run=');
  await page.reload();
  await expect(page.getByRole('status')).toContainText(
    'Analysis status: completed',
  );
  await expect(
    page.getByRole('heading', { name: 'Persisted findings' }),
  ).toBeVisible();
});

test('empty investigation list and safe unauthorized/backend-unavailable states', async ({
  page,
}) => {
  // Transport fixtures exercise UI failure states; real backend auth is covered separately.
  await page.route('**/api/v1/investigations', (route) =>
    route.fulfill({ json: [] }),
  );
  await page.goto('/investigations');
  await expect(
    page.getByRole('heading', { name: 'No investigations yet' }),
  ).toBeVisible();
  await page.unroute('**/api/v1/investigations');
  await page.route('**/api/v1/investigations', (route) =>
    route.fulfill({
      status: 401,
      headers: { 'X-Request-ID': 'ui-auth-fixture' },
      json: {
        error: {
          code: 'UNAUTHORIZED',
          message: 'A valid session is required.',
          request_id: 'ui-auth-fixture',
        },
      },
    }),
  );
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Unauthorized', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('ui-auth-fixture');
  await page.unroute('**/api/v1/investigations');
  await page.route('**/api/v1/investigations', (route) =>
    route.abort('failed'),
  );
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Backend unavailable');
});

test('failed and empty-result runs render without invented findings', async ({
  page,
}) => {
  const invId = '00000000-0000-4000-8000-000000000001';
  const runId = '00000000-0000-4000-8000-000000000002';
  const run = {
    id: runId,
    investigation_id: invId,
    artifact_id: 'fixture',
    status: 'failed',
    created_at: '2026-01-01T00:00:00Z',
    started_at: null,
    completed_at: null,
    error_code: 'ANALYSIS_TIMEOUT',
    error_message_safe: 'Analysis exceeded its execution time limit.',
    version_metadata: { application: 'fixture', detector: 'fixture' },
    configuration_snapshot: {},
    result_checksum: null,
  };
  await page.route(`**/api/v1/investigations/${invId}`, (route) =>
    route.fulfill({
      json: {
        id: invId,
        name: 'UI state fixture',
        status: 'failed',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    }),
  );
  await page.route(`**/api/v1/investigations/${invId}/artifacts`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route(`**/api/v1/investigations/${invId}/runs`, (route) =>
    route.fulfill({ json: [run] }),
  );
  await page.route(`**/api/v1/runs/${runId}`, (route) =>
    route.fulfill({ json: run }),
  );
  await page.goto(`/investigations/${invId}?run=${runId}`);
  await expect(page.getByRole('status')).toContainText(
    'Analysis status: failed',
  );
  await expect(page.getByRole('alert')).toContainText('ANALYSIS_TIMEOUT');
  await expect(
    page.getByRole('heading', { name: 'Persisted findings' }),
  ).toHaveCount(0);
  await page.unroute(`**/api/v1/runs/${runId}`);
  await page.route(`**/api/v1/runs/${runId}`, (route) =>
    route.fulfill({
      json: {
        ...run,
        status: 'completed',
        error_code: null,
        error_message_safe: null,
      },
    }),
  );
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({
      json: {
        schema_version: '1',
        threshold: 0.71,
        event_count: 1,
        entity_count: 2,
        model_scope: 'UI fixture only',
        rings: [],
      },
    }),
  );
  await page.reload();
  await expect(
    page.getByText(
      'No candidate rings were detected. This is not proof of legitimacy.',
    ),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Ask investigator' }),
  ).toHaveCount(0);
});
