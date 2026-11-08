import { createHash } from 'node:crypto';
import { test, expect } from '@playwright/test';
import {
  artifact,
  installWorkspace,
  investigationId,
  record,
} from './workspace-fixtures';

const bytes = Buffer.from('{}' + ' '.repeat(4_700_000));
const sha = (data: Buffer) => createHash('sha256').update(data).digest('hex');
const uploadId = '00000000-0000-4000-8000-000000000040';
const progress = {
  id: uploadId,
  investigation_id: investigationId,
  name: 'large.json',
  status: 'pending',
  size_bytes: bytes.length,
  checksum: sha(bytes),
  chunk_bytes: 2_000_000,
  chunk_count: 3,
  received: [] as number[],
  artifact_id: null,
};
const path = `**/api/v1/investigations/${investigationId}`;

test('interrupted upload resumes only missing parts and validates before enabling analysis', async ({
  page,
}) => {
  await installWorkspace(page);
  let pending = false;
  let completed = false;
  let interrupted = false;
  const received: number[] = [];
  const attempted: number[] = [];
  const keys: string[] = [];
  let runPosts = 0;
  await page.route(path, (route) =>
    route.fulfill({
      json: { ...record, status: pending ? 'uploading' : 'created' },
    }),
  );
  await page.route(`${path}/runs`, (route) => {
    if (route.request().method() === 'POST') runPosts++;
    return route.fulfill({ json: [] });
  });
  const accepted = {
    ...artifact,
    size_bytes: bytes.length,
    checksum: sha(bytes),
    original_name: 'large.json',
  };
  await page.route(`${path}/artifacts`, (route) =>
    route.fulfill({ json: completed ? [accepted] : [] }),
  );
  await page.route(`${path}/uploads`, (route) => {
    if (route.request().method() === 'POST') {
      expect(route.request().postDataJSON()).toEqual({
        name: 'large.json',
        size_bytes: bytes.length,
        checksum: sha(bytes),
      });
      keys.push(route.request().headers()['idempotency-key']);
      pending = true;
      return route.fulfill({ json: { ...progress, received } });
    }
    return route.fulfill({ json: pending ? [{ ...progress, received }] : [] });
  });
  await page.route(`${path}/uploads/${uploadId}/parts/*`, (route) => {
    const index = Number(
      new URL(route.request().url()).pathname.split('/').at(-1),
    );
    const part = route.request().postDataBuffer()!;
    expect(part).toEqual(
      bytes.subarray(index * 2_000_000, (index + 1) * 2_000_000),
    );
    expect(route.request().headers()['x-chunk-sha256']).toBe(sha(part));
    attempted.push(index);
    if (index === 1 && !interrupted) {
      interrupted = true;
      return route.fulfill({
        status: 503,
        json: {
          error: {
            code: 'ANALYSIS_UNAVAILABLE',
            message: 'Temporary interruption',
            request_id: 'upload-test',
          },
        },
      });
    }
    received.push(index);
    return route.fulfill({ json: { ...progress, received } });
  });
  await page.route(`${path}/uploads/${uploadId}/complete`, (route) => {
    expect(received).toEqual([0, 1, 2]);
    pending = false;
    completed = true;
    return route.fulfill({ json: accepted });
  });
  await page.goto(`/investigations/${investigationId}`);
  await page.locator('#dataset-file').setInputFiles({
    name: 'large.json',
    mimeType: 'application/json',
    buffer: bytes,
  });
  await page
    .getByRole('button', { name: 'Upload dataset', exact: true })
    .click();
  await expect(
    page.getByRole('status').filter({ hasText: 'Upload incomplete' }),
  ).toContainText('1 of 3 parts saved');
  await expect(
    page.getByRole('button', { name: 'Upload dataset', exact: true }),
  ).toBeEnabled();
  await page
    .getByRole('button', { name: 'Upload dataset', exact: true })
    .click();
  await expect(
    page.getByRole('button', { name: 'Start analysis', exact: true }),
  ).toBeEnabled();
  expect(attempted).toEqual([0, 1, 1, 2]);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  expect(runPosts).toBe(0);
  await expect(
    page.getByRole('button', { name: 'Discard incomplete upload' }),
  ).toHaveCount(0);
});

test('reopening shows a pending upload and discarding releases the analysis controls', async ({
  page,
}) => {
  await installWorkspace(page);
  let pending = true;
  await page.route(`${path}/runs`, (route) => route.fulfill({ json: [] }));
  await page.route(path, (route) =>
    route.fulfill({
      json: { ...record, status: pending ? 'uploading' : 'completed' },
    }),
  );
  await page.route(`${path}/uploads`, (route) =>
    route.fulfill({ json: pending ? [{ ...progress, received: [0] }] : [] }),
  );
  await page.route(`${path}/uploads/${uploadId}`, (route) => {
    expect(route.request().method()).toBe('DELETE');
    pending = false;
    return route.fulfill({ json: { id: uploadId, status: 'aborted' } });
  });
  await page.goto(`/investigations/${investigationId}`);
  await expect(
    page.getByRole('status').filter({ hasText: 'Upload incomplete' }),
  ).toContainText('large.json');
  await expect(
    page.getByRole('button', { name: 'Start analysis', exact: true }),
  ).toBeDisabled();
  await page
    .getByRole('button', { name: 'Discard incomplete upload', exact: true })
    .click();
  await expect(
    page.getByRole('button', { name: 'Start analysis', exact: true }),
  ).toBeEnabled();
  expect(pending).toBe(false);
});

test('an expired reservation uses a fresh key only after the server confirms no pending upload', async ({
  page,
}) => {
  await installWorkspace(page);
  const keys: string[] = [];
  let completed = false;
  const accepted = {
    ...artifact,
    size_bytes: bytes.length,
    checksum: sha(bytes),
    original_name: 'large.json',
  };
  await page.route(path, (route) =>
    route.fulfill({ json: { ...record, status: 'created' } }),
  );
  await page.route(`${path}/runs`, (route) => route.fulfill({ json: [] }));
  await page.route(`${path}/artifacts`, (route) =>
    route.fulfill({ json: completed ? [accepted] : [] }),
  );
  await page.route(`${path}/uploads`, (route) => {
    if (route.request().method() !== 'POST') return route.fulfill({ json: [] });
    keys.push(route.request().headers()['idempotency-key']);
    if (keys.length === 1)
      return route.fulfill({
        status: 409,
        json: {
          error: {
            code: 'CONFLICT',
            message: 'Upload expired',
            request_id: 'expiry-test',
          },
        },
      });
    completed = true;
    return route.fulfill({
      json: { ...progress, status: 'completed', artifact_id: accepted.id },
    });
  });
  await page.goto(`/investigations/${investigationId}`);
  await page
    .locator('#dataset-file')
    .setInputFiles({
      name: 'large.json',
      mimeType: 'application/json',
      buffer: bytes,
    });
  await page
    .getByRole('button', { name: 'Upload dataset', exact: true })
    .click();
  await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Upload dataset', exact: true }),
  ).toBeEnabled();
  await page
    .getByRole('button', { name: 'Upload dataset', exact: true })
    .click();
  await expect(
    page.getByRole('button', { name: 'Start analysis', exact: true }),
  ).toBeEnabled();
  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe(keys[1]);
});
