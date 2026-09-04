import { test, expect } from '@playwright/test';
import {
  installWorkspace,
  investigationId,
  runId,
  run,
  result,
  candidateResult,
  workspaceUrl,
} from './workspace-fixtures';

test('malformed successful responses and internal errors stay safe and include request IDs', async ({
  page,
}) => {
  await installWorkspace(page);
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({
      headers: { 'X-Request-ID': 'malformed-fixture' },
      json: { ...result, rings: [{ unexpected: true }] },
    }),
  );
  await page.goto(workspaceUrl);
  await expect(page.getByRole('alert')).toContainText(
    'Response could not be read',
  );
  await expect(page.getByRole('alert')).toContainText('malformed-fixture');
  await expect(
    page.getByRole('heading', { name: 'Persisted findings' }),
  ).toHaveCount(0);
  await page.unroute(`**/api/v1/runs/${runId}/results`);
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({
      status: 500,
      headers: { 'X-Request-ID': 'internal-fixture' },
      json: {
        error: {
          code: 'INTERNAL_ERROR',
          message: 'Traceback /private/server/secret.py',
        },
      },
    }),
  );
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('internal-fixture');
  await expect(page.getByRole('alert')).not.toContainText('Traceback');
  await expect(page.getByRole('alert')).not.toContainText('secret.py');
  await page.route(`**/api/v1/runs/${runId}`, (route) =>
    route.fulfill({
      headers: { 'X-Request-ID': 'malformed-run' },
      json: {
        ...run,
        status: 'failed',
        error_message_safe: { unexpected: 'object' },
      },
    }),
  );
  await page.reload();
  await expect(page.getByRole('alert')).toContainText(
    'Response could not be read',
  );
  await expect(page.getByRole('alert')).toContainText('malformed-run');
});

test('missing and mismatched run URLs never display another investigation’s findings', async ({
  page,
}) => {
  await installWorkspace(page);
  await page.route(`**/api/v1/runs/${runId}`, (route) =>
    route.fulfill({
      status: 404,
      headers: { 'X-Request-ID': 'stale-fixture' },
      json: { error: { code: 'NOT_FOUND', message: 'Run not found.' } },
    }),
  );
  await page.goto(workspaceUrl);
  await expect(page.getByRole('alert')).toContainText('Record not available');
  await expect(page.getByRole('alert')).toContainText('stale-fixture');
  await page.unroute(`**/api/v1/runs/${runId}`);
  await page.route(`**/api/v1/runs/${runId}`, (route) =>
    route.fulfill({
      json: { ...run, investigation_id: 'another-investigation' },
    }),
  );
  await page.reload();
  await expect(page.getByRole('alert')).toContainText(
    'different investigation',
  );
  await expect(
    page.getByRole('heading', { name: 'Persisted findings' }),
  ).toHaveCount(0);
});

test('oversized and malformed uploads give actionable errors without starting analysis', async ({
  page,
}) => {
  await installWorkspace(page);
  await page.route(
    `**/api/v1/investigations/${investigationId}/runs`,
    (route) => route.fulfill({ json: [] }),
  );
  await page.route(
    `**/api/v1/investigations/${investigationId}/artifacts`,
    (route) =>
      route.request().method() === 'POST'
        ? route.fulfill({
            status: 413,
            headers: { 'X-Request-ID': 'size-fixture' },
            json: {
              error: {
                code: 'UPLOAD_TOO_LARGE',
                message: 'Upload exceeds the configured limit.',
              },
            },
          })
        : route.fulfill({ json: [] }),
  );
  await page.goto(`/investigations/${investigationId}`);
  await page.getByLabel('Dataset file').setInputFiles({
    name: 'invalid.json',
    mimeType: 'application/json',
    buffer: Buffer.from('{'),
  });
  await page
    .getByRole('button', { name: 'Upload dataset', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText('Dataset is too large');
  await expect(page.getByRole('alert')).toContainText('size-fixture');
  await expect(
    page.getByRole('button', { name: 'Start analysis', exact: true }),
  ).toHaveCount(0);
  await page.unroute(`**/api/v1/investigations/${investigationId}/artifacts`);
  await page.route(
    `**/api/v1/investigations/${investigationId}/artifacts`,
    (route) =>
      route.fulfill({
        status: 422,
        headers: { 'X-Request-ID': 'upload-fixture' },
        json: {
          error: { code: 'INVALID_DATASET', message: 'Invalid DatasetBundle.' },
        },
      }),
  );
  await page
    .getByRole('button', { name: 'Upload dataset', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText(
    'valid RingSentinel DatasetBundle',
  );
  await expect(page.getByRole('alert')).toContainText('upload-fixture');
});

test('ambiguous start retry reuses idempotency key and completed polling stops', async ({
  page,
}) => {
  await installWorkspace(page);
  const keys: string[] = [];
  let reads = 0;
  await page.route(
    `**/api/v1/investigations/${investigationId}/runs`,
    async (route) => {
      if (route.request().method() === 'GET')
        return route.fulfill({ json: [] });
      keys.push(route.request().headers()['idempotency-key']);
      if (keys.length === 1) return route.abort('failed');
      return route.fulfill({ json: { ...run, status: 'queued' } });
    },
  );
  await page.route(`**/api/v1/runs/${runId}`, (route) => {
    reads += 1;
    return route.fulfill({
      json: { ...run, status: reads < 2 ? 'running' : 'completed' },
    });
  });
  await page.goto(`/investigations/${investigationId}`);
  await page
    .getByRole('button', { name: 'Start analysis', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText('Backend unavailable');
  await page
    .getByRole('button', { name: 'Start analysis', exact: true })
    .click();
  await expect(page.getByRole('status')).toContainText(
    'Analysis status: completed',
  );
  await expect(
    page.getByRole('heading', { name: 'Persisted findings' }),
  ).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[1]).toBe(keys[0]);
  const terminalReads = reads;
  await page.waitForTimeout(2200); // More than two polling intervals: intentional lifecycle assertion.
  expect(reads).toBe(terminalReads);
});

test('polling connection loss is recoverable without re-enqueuing a run', async ({
  page,
}) => {
  await installWorkspace(page, { ...run, status: 'running' });
  let posts = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST') posts += 1;
  });
  await page.route(`**/api/v1/runs/${runId}`, (route) => route.abort('failed'));
  await page.goto(workspaceUrl);
  await expect(page.getByRole('alert')).toContainText('Backend unavailable');
  await page.unroute(`**/api/v1/runs/${runId}`);
  await page.route(`**/api/v1/runs/${runId}`, (route) =>
    route.fulfill({ json: run }),
  );
  await page.getByRole('button', { name: 'Retry loading saved state' }).click();
  await expect(
    page.getByRole('heading', { name: 'Persisted findings' }),
  ).toBeVisible();
  expect(posts).toBe(0);
});

test('investigator malformed/provider-unavailable replies stay grounded and citations open their source', async ({
  page,
}) => {
  await installWorkspace(page);
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({ json: candidateResult }),
  );
  await page.route('**/investigate', (route) =>
    route.fulfill({
      headers: { 'X-Request-ID': 'investigator-malformed' },
      json: { provider: 'broken', statements: 'not-an-array' },
    }),
  );
  await page.goto(workspaceUrl + '&view=investigator');
  await page
    .getByRole('button', { name: 'Ask investigator', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText('investigator-malformed');
  await expect(page.locator('.answer-statements li')).toHaveCount(0);
  await page.unroute('**/investigate');
  await page.route('**/investigate', (route) =>
    route.fulfill({
      json: {
        provider: 'deterministic',
        statements: [
          {
            id: 'F1',
            text: 'Fixture observation: one recorded member.',
            query: 'get_ring_members',
            path: '$.length',
          },
        ],
        sources: [
          {
            query: 'get_ring_members',
            result: candidateResult.rings[0].queries.get_ring_members,
          },
        ],
        limitations: ['UI fixture only—not a detector result.'],
        warning:
          'Provider unavailable. Computed evidence fallback is available.',
      },
    }),
  );
  await page
    .getByRole('button', { name: 'Ask investigator', exact: true })
    .click();
  await expect(
    page.getByText('Deterministic evidence fallback · no LLM'),
  ).toBeVisible();
  await expect(
    page.getByText(
      'Provider unavailable. Computed evidence fallback is available.',
    ),
  ).toBeVisible();
  await page.locator('.evidence-citation').click();
  await expect(
    page.getByRole('button', { name: 'Source: get ring members' }),
  ).toHaveAttribute('aria-expanded', 'true');
  await expect(
    page.getByText('Fixture observation: one recorded member.'),
  ).toBeVisible();
});

test('unknown candidate URL does not substitute a different ring', async ({
  page,
}) => {
  await installWorkspace(page);
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({ json: candidateResult }),
  );
  await page.goto(workspaceUrl + '&ring=missing-candidate');
  await expect(page.getByRole('alert')).toContainText(
    'Candidate not available in this run',
  );
  await expect(
    page.getByRole('region', { name: 'Selected candidate' }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: /^Inspect candidate / }).click();
  await expect(
    page.getByRole('region', { name: 'Selected candidate' }),
  ).toBeVisible();
  expect(page.url()).toContain('ring=ui-fixture-candidate');
});
