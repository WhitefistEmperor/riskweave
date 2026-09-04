import { test, expect } from '@playwright/test';
import { validSession } from '../lib/response-validation';

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
