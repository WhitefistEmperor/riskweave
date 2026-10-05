import { expect, test, type Page, type Route } from '@playwright/test';
import { record } from './workspace-fixtures';

// Dedicated OIDC-configured frontend, real oidc-client-ts timers/storage, mocked
// private API bodies. This is session UI proof, not live issuer/JWT validation.
test.skip(
  process.env.RISKWEAVE_OIDC_BROWSER_TEST !== '1',
  'Requires the isolated OIDC frontend',
);
const authority = 'http://127.0.0.1:5174/fixture-issuer';
const storageKey = `oidc.user:${authority}:riskweave-session-browser-control`;
const privateName = 'Private expiry inspection case';

async function installSession(page: Page, lifetime: number) {
  await page.addInitScript(
    ({ key, seconds }) => {
      sessionStorage.setItem(
        key,
        JSON.stringify({
          access_token: 'synthetic-session-token',
          id_token: 'synthetic-id-token',
          token_type: 'Bearer',
          scope: 'openid profile ringsentinel:analyst',
          profile: { sub: 'session-browser-control' },
          expires_at: Math.floor(Date.now() / 1000) + seconds,
        }),
      );
    },
    { key: storageKey, seconds: lifetime },
  );
  const requests: string[] = [];
  await page.route('**/api/**', async (route) => {
    requests.push(route.request().url());
    expect(route.request().headers().authorization).toBe(
      'Bearer synthetic-session-token',
    );
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/session') {
      await route.fulfill({
        json: {
          user_id: 'session-browser-control',
          authentication_mode: 'jwt',
          production_authentication: true,
        },
      });
    } else if (pathname === '/api/v1/investigations/page') {
      await route.fulfill({
        json: {
          items: [{ ...record, name: privateName }],
          total: 1,
          matched: 1,
          offset: 0,
          limit: 10,
        },
      });
    } else {
      await route.fulfill({ json: [] });
    }
  });
  return requests;
}

test('already expired sessions never mount or request the private workspace', async ({
  page,
}) => {
  const requests = await installSession(page, -10);
  await page.goto('/investigations');
  await expect(
    page.getByRole('heading', { name: 'Signed out of RiskWeave' }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Return to sign-in' }),
  ).toBeVisible();
  await expect(page.getByText(privateName)).toHaveCount(0);
  expect(requests).toEqual([]);
});

test('idle token expiry unmounts loaded private data without another API request', async ({
  page,
}) => {
  const requests = await installSession(page, 10);
  await page.goto('/investigations');
  await expect(
    page.getByRole('link', { name: `Open ${privateName}`, exact: true }),
  ).toBeVisible();
  await expect
    .poll(() => requests.some((url) => new URL(url).pathname.endsWith('/runs')))
    .toBe(true);
  const loadedRequests = requests.length;
  await expect(
    page.getByRole('heading', { name: 'Your session has expired' }),
  ).toBeVisible();
  await expect(page.getByText(privateName)).toHaveCount(0);
  await expect(
    page.getByRole('navigation', { name: 'Main navigation' }),
  ).toHaveCount(0);
  expect(requests.length).toBe(loadedRequests);
});

test('sign-out clears the workspace before provider response and keeps it hidden on failure', async ({
  page,
}) => {
  await installSession(page, 120);
  let metadata: Route | undefined;
  await page.route(
    '**/fixture-issuer/.well-known/openid-configuration',
    (route) => {
      metadata = route;
    },
  );
  await page.goto('/investigations');
  await expect(
    page.getByRole('link', { name: `Open ${privateName}`, exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Signed out of RiskWeave' }),
  ).toBeVisible();
  await expect(page.getByText(privateName)).toHaveCount(0);
  await expect.poll(() => Boolean(metadata)).toBe(true);
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), storageKey),
  ).toBeNull();
  await metadata!.abort('failed');
  await expect(page.getByRole('main').getByRole('alert')).toContainText(
    'Sign-out could not finish',
  );
  await expect(page.getByText(privateName)).toHaveCount(0);
  await page.getByRole('link', { name: 'Return to sign-in' }).click();
  await expect(
    page.getByRole('heading', { name: 'Sign in to RiskWeave' }),
  ).toBeVisible();
});
