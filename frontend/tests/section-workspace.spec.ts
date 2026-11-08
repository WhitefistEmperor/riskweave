import { createHash } from 'node:crypto';
import { test, expect, type Page } from '@playwright/test';
import {
  candidateResult,
  installWorkspace,
  run,
  runId,
  workspaceUrl,
} from './workspace-fixtures';

const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
const wholeDigest = sha(Buffer.from(JSON.stringify(candidateResult)));
const candidate = candidateResult.rings[0].candidate;

async function install(page: Page, mode = 'valid') {
  await installWorkspace(page);
  await page.route(`**/api/v1/runs/${runId}`, (route) =>
    route.fulfill({ json: { ...run, result_checksum: wholeDigest } }),
  );
  await page.route(`**/api/v1/runs/${runId}/overview`, (route) =>
    route.fulfill({
      json: {
        ...candidateResult,
        rings: undefined,
        run_id: runId,
        result_sha256: wholeDigest,
        candidate_count: 9,
      },
    }),
  );
  await page.route(`**/api/v1/runs/${runId}/queue-page?*`, (route) => {
    const offset = Number(
      new URL(route.request().url()).searchParams.get('offset'),
    );
    const items = Array.from({ length: Math.min(8, 9 - offset) }, (_, i) => ({
      ...candidate,
      candidate_id:
        offset + i === 0 ? candidate.candidate_id : `candidate-${offset + i}`,
    }));
    return route.fulfill({
      json: {
        schema_version: '1',
        run_id: runId,
        result_sha256: wholeDigest,
        offset,
        limit: 8,
        total: 9,
        next_offset: offset === 0 ? 8 : null,
        items: items.map((item) => ({
          candidate_id: item.candidate_id,
          risk_score: item.risk_score,
          estimated_exposure_minor:
            mode === 'large-money'
              ? '9007199254740993'
              : item.estimated_exposure_minor,
          member_count:
            mode === 'invalid-count' ? -1 : item.member_entity_ids.length,
          event_count: item.related_event_ids.length,
        })),
      },
    });
  });
  await page.route(
    `**/api/v1/runs/${runId}/rings/*/sections/**`,
    async (route) => {
      const pieces = new URL(route.request().url()).pathname.split('/');
      const id = pieces[pieces.indexOf('rings') + 1];
      const kind = pieces[pieces.indexOf('sections') + 1];
      const selected = {
        ...candidate,
        candidate_id: id,
        estimated_exposure_minor:
          mode === 'large-money'
            ? '9007199254740993'
            : candidate.estimated_exposure_minor,
      };
      const queries = {
        ...candidateResult.rings[0].queries,
        get_candidate_ring: selected,
        calculate_exposure: {
          ...candidateResult.rings[0].queries.calculate_exposure,
          candidate_id: id,
          estimated_exposure_minor: selected.estimated_exposure_minor,
        },
      };
      const bytes = Buffer.from(
        JSON.stringify(kind === 'candidate' ? selected : queries).replaceAll(
          '"9007199254740993"',
          '9007199254740993',
        ),
      );
      const digest = sha(bytes);
      const scope = {
        schema_version: '1',
        run_id: runId,
        candidate_id: id,
        section: kind,
        result_sha256: wholeDigest,
      };
      if (route.request().url().endsWith('/manifest'))
        return route.fulfill({
          json: {
            ...scope,
            sha256: mode === 'wrong-full-hash' ? 'f'.repeat(64) : digest,
            size_bytes: bytes.length,
            chunk_bytes: 2000000,
            chunk_count: 1,
            encoding: 'base64',
            content_type: 'application/json',
          },
        });
      if (
        mode === 'delayed' &&
        id === candidate.candidate_id &&
        kind === 'evidence'
      )
        await new Promise((resolve) => setTimeout(resolve, 1000));
      return route.fulfill({
        json: {
          ...scope,
          section_sha256: mode === 'wrong-full-hash' ? 'f'.repeat(64) : digest,
          index: 0,
          size_bytes: bytes.length,
          sha256: digest,
          data:
            mode === 'wrong-chunk-hash'
              ? Buffer.alloc(bytes.length).toString('base64')
              : bytes.toString('base64'),
        },
      });
    },
  );
  let wholeRequests = 0;
  await page.route(`**/api/v1/runs/${runId}/results**`, (route) => {
    wholeRequests++;
    return route.abort();
  });
  return () => wholeRequests;
}

test('paged workspace loads only selected verified evidence, navigates and reloads', async ({
  page,
}) => {
  const wholeRequests = await install(page);
  await page.goto(workspaceUrl);
  await expect(
    page.getByRole('heading', { name: 'Persisted findings' }),
  ).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Selected candidate' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Candidate review queue' }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Next candidates', exact: true })
    .click();
  await expect(page.getByText('9–9 of 9 candidates')).toBeVisible();
  await page.getByRole('button', { name: 'Open ring DATE-8' }).click();
  await expect(
    page.getByRole('region', { name: 'Selected candidate' }),
  ).toBeFocused();
  await expect(page).toHaveURL(/ring=candidate-8/);
  await page.reload();
  await expect(
    page.getByRole('region', { name: 'Selected candidate' }),
  ).toContainText('DATE-8');
  expect(wholeRequests()).toBe(0);
});
for (const mode of ['wrong-chunk-hash', 'wrong-full-hash']) {
  test(`selected evidence rejects ${mode} before graph or review publication`, async ({
    page,
  }) => {
    const wholeRequests = await install(page, mode);
    await page.goto(workspaceUrl);
    await expect(
      page.getByRole('heading', { name: 'Response could not be read' }),
    ).toBeVisible();
    await expect(
      page.getByRole('region', { name: 'Selected candidate' }),
    ).toHaveCount(0);
    await expect(
      page.getByRole('heading', { name: 'Analyst review', exact: true }),
    ).toHaveCount(0);
    expect(wholeRequests()).toBe(0);
  });
}
test('selection change cancels delayed evidence and keeps the new candidate', async ({
  page,
}) => {
  await install(page, 'delayed');
  await page.goto(workspaceUrl);
  await expect(
    page.getByRole('button', { name: 'Next candidates', exact: true }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Next candidates', exact: true })
    .click();
  await expect(page.getByText('9–9 of 9 candidates')).toBeVisible();
  await page.getByRole('button', { name: 'Open ring DATE-8' }).click();
  await expect(
    page.getByRole('region', { name: 'Selected candidate' }),
  ).toContainText('DATE-8');
  await page.waitForTimeout(1100);
  await expect(
    page.getByRole('region', { name: 'Selected candidate' }),
  ).toContainText('DATE-8');
});

test('invalid queue counts fail closed before selected evidence loads', async ({
  page,
}) => {
  await install(page, 'invalid-count');
  await page.goto(workspaceUrl);
  await expect(
    page.getByRole('heading', { name: 'Response could not be read' }),
  ).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Selected candidate' }),
  ).toHaveCount(0);
});

test('queue decimal strings and checksum-verified legacy integer sections display exactly', async ({
  page,
}) => {
  const wholeRequests = await install(page, 'large-money');
  await page.goto(workspaceUrl);
  const selected = page.getByRole('region', { name: 'Selected candidate' });
  await expect(selected).toContainText(
    '9,007,199,254,740,993 unknown-currency minor units',
  );
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page
    .getByRole('button', { name: 'Exposure accounting', exact: true })
    .click();
  await expect(page.locator('.grouped-evidence')).toContainText(
    '9,007,199,254,740,993 unknown-currency minor units',
  );
  expect(wholeRequests()).toBe(0);
});
