import { test, expect } from '@playwright/test';
import { validSession } from '../lib/response-validation';
import { spawnSync } from 'node:child_process';

test('production frontend configuration fails closed without leaking malformed proxy values', () => {
  for (const target of ['', 'http://user:fixture-secret@', 'https://user:fixture-secret@api.example']) {
    const result = spawnSync(process.execPath,
      ['--experimental-strip-types', '--input-type=module', '-e', "await import('./next.config.ts')"],
      { encoding: 'utf8', env: { ...process.env, RINGSENTINEL_ENVIRONMENT: 'production',
        RINGSENTINEL_API_PROXY_TARGET: target, NEXT_PUBLIC_RINGSENTINEL_API_BASE_URL: '' } });
    expect(result.status).not.toBe(0);
    expect(result.stderr).not.toContain('fixture-secret');
  }
  const accepted = spawnSync(process.execPath,
    ['--experimental-strip-types', '--input-type=module', '-e', "await import('./next.config.ts')"],
    { encoding: 'utf8', env: { ...process.env, RINGSENTINEL_ENVIRONMENT: 'production',
      RINGSENTINEL_API_PROXY_TARGET: 'https://api.example', NEXT_PUBLIC_RINGSENTINEL_API_BASE_URL: '' } });
  expect(accepted.status, accepted.stderr).toBe(0);
});

test('session contract accepts verified tokens without accepting mismatched auth flags', () => {
  expect(validSession({ user_id: 'opaque', authentication_mode: 'jwt', production_authentication: true })).toBe(true);
  expect(validSession({ user_id: 'opaque', authentication_mode: 'jwt', production_authentication: false })).toBe(false);
  expect(validSession({ user_id: 'opaque', authentication_mode: 'development', production_authentication: true })).toBe(false);
});

test('built frontend sends security headers and renders verified session without token storage', async ({ page }) => {
  await page.route('**/api/v1/session', route => route.fulfill({ json: {
    user_id: 'jwt_verified_fixture', authentication_mode: 'jwt', production_authentication: true,
  } }));
  await page.route('**/api/v1/investigations', route => route.fulfill({ json: [] }));
  const response = await page.goto('/investigations');
  expect(response?.headers()['x-content-type-options']).toBe('nosniff');
  expect(response?.headers()['x-frame-options']).toBe('DENY');
  expect(response?.headers()['content-security-policy']).toContain("frame-ancestors 'none'");
  await expect(page.getByText('Verified analyst session', { exact: true })).toBeVisible();
  await expect(page.getByText(/Development identity/)).toHaveCount(0);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
});
