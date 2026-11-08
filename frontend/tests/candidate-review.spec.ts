import { test, expect } from '@playwright/test';
import {
  installWorkspace,
  candidateResult,
  runId,
  workspaceUrl,
} from './workspace-fixtures';
import type { CandidateReview, ReviewUpdate } from '../lib/platform-api';

const candidateId = candidateResult.rings[0].candidate.candidate_id;
const initial: CandidateReview = {
  run_id: runId,
  candidate_id: candidateId,
  disposition: 'unreviewed',
  version: 0,
  updated_at: null,
  history: [],
};
const audit = (version: number, note: string) => ({
  id: `audit-${version}`,
  actor_id: 'fixture-analyst',
  previous_disposition: 'unreviewed' as const,
  disposition: 'investigating' as const,
  version,
  note,
  created_at: '2026-01-01T00:00:00Z',
});

test('a lost review response retries the same submission and renders the note as text', async ({
  page,
}) => {
  await installWorkspace(page);
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({ json: candidateResult }),
  );
  let saved = initial;
  const keys: string[] = [];
  await page.route('**/review', (route) => {
    if (route.request().method() === 'GET')
      return route.fulfill({ json: saved });
    keys.push(route.request().headers()['idempotency-key']);
    const body = route.request().postDataJSON() as ReviewUpdate;
    saved = {
      ...initial,
      disposition: body.disposition,
      version: 1,
      updated_at: '2026-01-01T00:00:00Z',
      history: [audit(1, body.note)],
    };
    return keys.length === 1
      ? route.abort('failed')
      : route.fulfill({ json: saved });
  });
  await page.goto(workspaceUrl);
  await page
    .getByLabel('Review status', { exact: true })
    .selectOption('investigating');
  const note =
    '<script>throw new Error("must remain text")</script> Review the evidence.';
  await page.getByLabel('Review note', { exact: true }).fill(note);
  await page.getByRole('button', { name: 'Save review', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Backend unavailable');
  expect(keys).toHaveLength(1);
  await expect(page.getByLabel('Review note', { exact: true })).toHaveValue(
    note,
  );
  await page.getByRole('button', { name: 'Save review', exact: true }).click();
  await expect(
    page.getByText('Review saved to the audit history.'),
  ).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]);
  await page.getByText('Review history (1)', { exact: true }).click();
  await expect(page.getByText(note, { exact: true })).toBeVisible();
  await expect(page.getByLabel('Review note', { exact: true })).toHaveValue('');
});

test('conflicts preserve the draft and require a reload before resubmission', async ({
  page,
}) => {
  await installWorkspace(page);
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({ json: candidateResult }),
  );
  let saved = initial;
  const bodies: ReviewUpdate[] = [];
  await page.route('**/review', (route) => {
    if (route.request().method() === 'GET')
      return route.fulfill({ json: saved });
    const body = route.request().postDataJSON() as ReviewUpdate;
    bodies.push(body);
    if (bodies.length === 1) {
      saved = {
        ...initial,
        version: 1,
        disposition: 'investigating',
        updated_at: '2026-01-01T00:00:00Z',
        history: [audit(1, 'Another tab saved this review.')],
      };
      return route.fulfill({
        status: 409,
        json: { error: { code: 'CONFLICT', message: 'Review changed.' } },
      });
    }
    saved = {
      ...saved,
      version: 2,
      disposition: body.disposition,
      history: [
        ...saved.history,
        { ...audit(2, body.note), previous_disposition: 'investigating' },
      ],
    };
    return route.fulfill({ json: saved });
  });
  await page.goto(workspaceUrl);
  await page
    .getByLabel('Review note', { exact: true })
    .fill('My unsaved reasoning.');
  await page.getByRole('button', { name: 'Save review', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText(
    'changed since you opened',
  );
  await expect(
    page.getByRole('button', { name: 'Save review', exact: true }),
  ).toBeDisabled();
  await page
    .getByRole('button', { name: 'Reload review', exact: true })
    .click();
  await expect(
    page.getByText('Latest review loaded.', { exact: false }),
  ).toBeVisible();
  await expect(page.getByLabel('Review note', { exact: true })).toHaveValue(
    'My unsaved reasoning.',
  );
  await page.getByRole('button', { name: 'Save review', exact: true }).click();
  await expect(
    page.getByText('Review saved to the audit history.'),
  ).toBeVisible();
  expect(bodies.map((body) => body.expected_version)).toEqual([0, 1]);
});

test('a review response for another candidate cannot expose history or permit saving', async ({
  page,
}) => {
  await installWorkspace(page);
  await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
    route.fulfill({ json: candidateResult }),
  );
  await page.route('**/review', (route) =>
    route.fulfill({
      json: {
        ...initial,
        candidate_id: 'wrong-candidate',
        version: 1,
        history: [audit(1, 'Wrong candidate confidential note')],
      },
    }),
  );
  await page.goto(workspaceUrl);
  await expect(page.getByRole('main').getByRole('alert')).toContainText('unreadable response');
  await expect(page.getByText('Wrong candidate confidential note')).toHaveCount(
    0,
  );
  await expect(
    page.getByRole('button', { name: 'Save review', exact: true }),
  ).toBeDisabled();
});
