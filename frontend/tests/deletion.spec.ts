import { test, expect } from '@playwright/test';
import {
  installWorkspace,
  investigationId,
  record,
  run,
  workspaceUrl,
} from './workspace-fixtures';

test('deletion requires the exact case name, blocks duplicate submissions and reports pending cleanup', async ({
  page,
}) => {
  await installWorkspace(page);
  let requests = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    `**/api/v1/investigations/${investigationId}`,
    async (route) => {
      if (route.request().method() !== 'DELETE')
        return route.fulfill({ json: record });
      requests += 1;
      expect(route.request().postDataJSON()).toEqual({
        confirm_name: record.name,
        expected_updated_at: record.updated_at,
      });
      await gate;
      return route.fulfill({
        json: {
          investigation_id: investigationId,
          status: 'deleted',
          storage_cleanup: 'pending',
        },
      });
    },
  );
  await page.goto(workspaceUrl);
  await page
    .getByRole('button', { name: 'Delete investigation', exact: true })
    .click();
  const dialog = page.getByRole('alertdialog');
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole('button', { name: 'Permanently delete' }),
  ).toBeDisabled();
  await dialog
    .getByLabel('Type the investigation name')
    .fill(record.name.toLowerCase());
  await expect(
    dialog.getByRole('button', { name: 'Permanently delete' }),
  ).toBeDisabled();
  await dialog.getByLabel('Type the investigation name').fill(record.name);
  await dialog.getByRole('button', { name: 'Permanently delete' }).click();
  await expect(
    dialog.getByRole('button', { name: 'Deleting…' }),
  ).toBeDisabled();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeVisible();
  expect(requests).toBe(1);
  release();
  await expect(page).toHaveURL(/\/investigations\?removed=pending$/);
  await expect(page.getByRole('status')).toContainText(
    'Some stored files are awaiting cleanup',
  );
});

test('an active run cannot open deletion confirmation', async ({ page }) => {
  await installWorkspace(page, { ...run, status: 'running' });
  await page.goto(workspaceUrl);
  await expect(
    page.getByRole('button', { name: 'Delete investigation', exact: true }),
  ).toBeDisabled();
  await expect(page.getByRole('alertdialog')).toHaveCount(0);
});

for (const outcome of ['conflict', 'mismatched-scope'] as const) {
  test(`${outcome} deletion reply preserves the confirmation without claiming success`, async ({
    page,
  }) => {
    await installWorkspace(page);
    let requests = 0;
    await page.route(`**/api/v1/investigations/${investigationId}`, (route) => {
      if (route.request().method() !== 'DELETE')
        return route.fulfill({ json: record });
      requests += 1;
      return outcome === 'conflict'
        ? route.fulfill({
            status: 409,
            json: { error: { code: 'CONFLICT', message: 'Conflict' } },
          })
        : route.fulfill({
            json: {
              investigation_id: 'another-case',
              status: 'deleted',
              storage_cleanup: 'complete',
            },
          });
    });
    await page.goto(workspaceUrl);
    await page
      .getByRole('button', { name: 'Delete investigation', exact: true })
      .click();
    const dialog = page.getByRole('alertdialog');
    await dialog.getByLabel('Type the investigation name').fill(record.name);
    await dialog.getByRole('button', { name: 'Permanently delete' }).click();
    await expect(dialog.getByRole('alert')).toContainText(
      outcome === 'conflict'
        ? 'Reload the case before deleting'
        : 'unreadable response',
    );
    await expect(dialog.getByLabel('Type the investigation name')).toHaveValue(
      record.name,
    );
    if (outcome === 'conflict') {
      await expect(
        dialog.getByRole('button', { name: 'Permanently delete' }),
      ).toBeDisabled();
      await expect(
        dialog.getByRole('button', { name: 'Reload case' }),
      ).toBeVisible();
    }
    expect(requests).toBe(1);
    await expect(page).toHaveURL(new RegExp(investigationId));
    await dialog.getByRole('button', { name: 'Keep investigation' }).click();
    await expect(dialog).toHaveCount(0);
  });
}

test('real created case can be deleted and no longer reopened', async ({
  page,
  request,
}) => {
  await page.goto('/investigations');
  const name = `Deletion browser verification ${Date.now()}`;
  await page.getByLabel('Investigation name').fill(name);
  await page.getByRole('button', { name: 'Create investigation' }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  const id = new URL(page.url()).pathname.split('/').at(-1)!;
  await page
    .getByRole('button', { name: 'Delete investigation', exact: true })
    .click();
  await page
    .getByRole('alertdialog')
    .getByLabel('Type the investigation name')
    .fill(name);
  await page.getByRole('button', { name: 'Permanently delete' }).click();
  await expect(page).toHaveURL(/\/investigations\?removed=complete$/);
  await expect(page.getByRole('status')).toContainText('stored files removed');
  expect(
    (
      await request.get(`http://127.0.0.1:8000/api/v1/investigations/${id}`)
    ).status(),
  ).toBe(404);
});
