import { createHash } from 'node:crypto';
import { test, expect } from '@playwright/test';
import {
  candidateResult,
  installWorkspace,
  investigationId,
  run,
  runId,
  workspaceUrl,
} from './workspace-fixtures';

const chunkBytes = 2_000_000;
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
// This is an evidence transport fixture, not a measured model result.
const largeResult = {
  ...candidateResult,
  rings: candidateResult.rings.map((ring) => ({
    ...ring,
    queries: {
      ...ring.queries,
      calculate_exposure: {
        ...ring.queries.calculate_exposure,
        definition: 'é😀'.repeat(800_000),
      },
    },
  })),
};
const bytes = Buffer.from(JSON.stringify(largeResult));
const digest = sha(bytes);
const savedRun = {
  ...run,
  result_checksum: digest,
  configuration_snapshot: { execution_mode: 'request' },
};
const manifest = {
  schema_version: '1',
  run_id: runId,
  investigation_id: investigationId,
  encoding: 'base64',
  content_type: 'application/json',
  size_bytes: bytes.length,
  sha256: digest,
  chunk_bytes: chunkBytes,
  chunk_count: Math.ceil(bytes.length / chunkBytes),
};

for (const mode of ['request', 'local']) {
  test(`large ${mode}-mode evidence reassembles authenticated UTF-8 fragments before displaying findings`, async ({
    page,
  }) => {
    expect(bytes.length).toBeGreaterThan(4_500_000);
    await installWorkspace(page, {
      ...savedRun,
      configuration_snapshot: { execution_mode: mode },
    });
    let wholeRequests = 0;
    const requested: number[] = [];
    await page.route(`**/api/v1/runs/${runId}/results`, (route) => {
      wholeRequests++;
      return route.fulfill({
        status: 409,
        json: {
          error: {
            code: 'RESULT_TRANSPORT_REQUIRED',
            message: 'Use fragment transport.',
            request_id: 'transport-fixture',
          },
        },
      });
    });
    await page.route(`**/api/v1/runs/${runId}/results/manifest`, (route) =>
      route.fulfill({ json: manifest }),
    );
    await page.route(`**/api/v1/runs/${runId}/results/chunks/*`, (route) => {
      const index = Number(
        new URL(route.request().url()).pathname.split('/').at(-1),
      );
      requested.push(index);
      const part = bytes.subarray(index * chunkBytes, (index + 1) * chunkBytes);
      const json = {
        schema_version: '1',
        run_id: runId,
        index,
        size_bytes: part.length,
        result_sha256: digest,
        sha256: sha(part),
        data: part.toString('base64'),
      };
      expect(Buffer.byteLength(JSON.stringify(json))).toBeLessThan(4_500_000);
      return route.fulfill({ json });
    });
    await page.goto(workspaceUrl);
    await expect(
      page.getByRole('heading', { name: 'Persisted findings' }),
    ).toBeVisible();
    expect(requested).toEqual(
      Array.from({ length: manifest.chunk_count }, (_, index) => index),
    );
    expect(wholeRequests).toBe(mode === 'local' ? 1 : 0);
  });
}

for (const changeChunkHash of [false, true]) {
  test(`corrupt evidence fails closed with ${changeChunkHash ? 'matching fragment but wrong whole' : 'wrong fragment'} checksum`, async ({
    page,
  }) => {
    await installWorkspace(page, savedRun);
    await page.route(`**/api/v1/runs/${runId}/results/manifest`, (route) =>
      route.fulfill({ json: manifest }),
    );
    await page.route(`**/api/v1/runs/${runId}/results/chunks/*`, (route) => {
      const index = Number(
        new URL(route.request().url()).pathname.split('/').at(-1),
      );
      const part = Buffer.from(
        bytes.subarray(index * chunkBytes, (index + 1) * chunkBytes),
      );
      const originalHash = sha(part);
      if (index === 0) part[part.length - 1] ^= 1;
      return route.fulfill({
        json: {
          schema_version: '1',
          run_id: runId,
          index,
          size_bytes: part.length,
          result_sha256: digest,
          sha256: changeChunkHash ? sha(part) : originalHash,
          data: part.toString('base64'),
        },
      });
    });
    await page.goto(workspaceUrl);
    await expect(page.getByRole('main').getByRole('alert')).toContainText(
      'Response could not be read',
    );
    await expect(
      page.getByRole('heading', { name: 'Persisted findings' }),
    ).toHaveCount(0);
  });
}

const badManifests: Array<[string, Record<string, string | number>]> = [
  ['other case', { investigation_id: 'another-case' }],
  ['other run', { run_id: 'another-run' }],
  ['different saved checksum', { sha256: 'a'.repeat(64) }],
  ['oversized allocation', { size_bytes: 500_000_001 }],
  ['incorrect chunk count', { chunk_count: 1 }],
];
for (const [name, changed] of badManifests) {
  test(`a manifest with ${name} is rejected before any fragment fetch`, async ({
    page,
  }) => {
    await installWorkspace(page, savedRun);
    let chunks = 0;
    await page.route(`**/api/v1/runs/${runId}/results/manifest`, (route) =>
      route.fulfill({ json: { ...manifest, ...changed } }),
    );
    await page.route(`**/api/v1/runs/${runId}/results/chunks/*`, () => {
      chunks++;
    });
    await page.goto(workspaceUrl);
    await expect(page.getByRole('main').getByRole('alert')).toContainText(
      'Response could not be read',
    );
    expect(chunks).toBe(0);
  });
}

test('leaving a case aborts fragment delivery without fetching later fragments', async ({
  page,
}) => {
  await installWorkspace(page, savedRun);
  await page.route(`**/api/v1/runs/${runId}/results/manifest`, (route) =>
    route.fulfill({ json: manifest }),
  );
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const requested: string[] = [];
  await page.route(
    `**/api/v1/runs/${runId}/results/chunks/*`,
    async (route) => {
      requested.push(new URL(route.request().url()).pathname);
      await gate;
      const part = bytes.subarray(0, chunkBytes);
      await route.fulfill({
        json: {
          schema_version: '1',
          run_id: runId,
          index: 0,
          size_bytes: part.length,
          result_sha256: digest,
          sha256: sha(part),
          data: part.toString('base64'),
        },
      });
    },
  );
  const first = page.waitForRequest(`**/api/v1/runs/${runId}/results/chunks/0`);
  await page.goto(workspaceUrl);
  await first;
  await page
    .getByRole('navigation', { name: 'Breadcrumb' })
    .getByRole('link', { name: 'Investigations' })
    .click();
  release();
  await expect(
    page.getByRole('heading', { name: 'Investigations', exact: true }),
  ).toBeVisible();
  expect(requested).toEqual([`/api/v1/runs/${runId}/results/chunks/0`]);
});
