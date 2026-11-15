import { createHash } from 'node:crypto';
import { test, expect } from '@playwright/test';
import {
  installWorkspace,
  run,
  runId,
  investigationId,
  result,
  workspaceUrl,
} from './workspace-fixtures';

for (const dispatchState of ['pending', 'accepted'] as const) {
  test(`background ${dispatchState} survives leaving and returning without browser execution`, async ({
    page,
  }) => {
    const queued = {
      ...run,
      status: 'queued' as const,
      started_at: null,
      completed_at: null,
      result_checksum: null,
      dispatch_state: dispatchState,
      configuration_snapshot: {
        execution_mode: 'request',
        background_dispatch: 'vercel_workflow',
      },
    };
    await installWorkspace(page, queued);
    let executeCalls = 0;
    await page.route(`**/api/v1/runs/${runId}/execute`, (route) => {
      executeCalls++;
      return route.fulfill({ json: queued });
    });
    await page.goto(workspaceUrl);
    await expect(
      page.getByText(
        dispatchState === 'accepted'
          ? 'Queued for background analysis.'
          : 'Background delivery is pending.',
        { exact: false },
      ),
    ).toBeVisible();
    await expect(
      page.getByText('Keep this page open', { exact: false }),
    ).toHaveCount(0);
    await page.goto('/investigations');
    const content = Buffer.from(JSON.stringify(result));
    const sha = createHash('sha256').update(content).digest('hex');
    const completed = {
      ...queued,
      ...run,
      configuration_snapshot: queued.configuration_snapshot,
      result_checksum: sha,
      dispatch_state: 'accepted',
    };
    await page.route(`**/api/v1/runs/${runId}`, (route) =>
      route.fulfill({ json: completed }),
    );
    await page.route(`**/api/v1/runs/${runId}/results/manifest`, (route) =>
      route.fulfill({
        json: {
          schema_version: '1',
          run_id: runId,
          investigation_id: investigationId,
          encoding: 'base64',
          content_type: 'application/json',
          size_bytes: content.length,
          sha256: sha,
          chunk_bytes: 2_000_000,
          chunk_count: 1,
        },
      }),
    );
    await page.route(`**/api/v1/runs/${runId}/results/chunks/0`, (route) =>
      route.fulfill({
        json: {
          schema_version: '1',
          run_id: runId,
          index: 0,
          size_bytes: content.length,
          sha256: sha,
          result_sha256: sha,
          data: content.toString('base64'),
        },
      }),
    );
    await page.goto(workspaceUrl);
    await expect(
      page.getByRole('heading', { name: 'Persisted findings' }),
    ).toBeVisible();
    expect(executeCalls).toBe(0);
  });
}

test('invalid delivery state is rejected before making execution decisions', async ({
  page,
}) => {
  await installWorkspace(page);
  await page.route(`**/api/v1/runs/${runId}`, (route) =>
    route.fulfill({
      headers: { 'X-Request-ID': 'invalid-delivery-state' },
      json: { ...run, dispatch_state: { unexpected: true } },
    }),
  );
  await page.goto(workspaceUrl);
  await expect(page.getByRole('main').getByRole('alert')).toContainText(
    'Response could not be read',
  );
  await expect(page.getByRole('main').getByRole('alert')).toContainText(
    'invalid-delivery-state',
  );
});
