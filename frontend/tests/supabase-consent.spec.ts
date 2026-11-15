import { test, expect } from '@playwright/test';
import { supabaseProjectUrl, trustedRedirect } from '../lib/supabase-consent';

test('consent accepts only an exact Supabase Auth issuer', () => {
  expect(supabaseProjectUrl('https://abcd1234.supabase.co/auth/v1')).toBe(
    'https://abcd1234.supabase.co',
  );
  expect(supabaseProjectUrl('https://abcd1234.supabase.co/auth/v1/')).toBe(
    'https://abcd1234.supabase.co',
  );
  for (const rejected of [
    'http://abcd1234.supabase.co/auth/v1',
    'https://abcd1234.supabase.co.evil.test/auth/v1',
    'https://evil.test/abcd1234.supabase.co/auth/v1',
    'https://abcd1234.supabase.co/',
    'https://abcd1234.supabase.co/auth/v1?x=1',
    'https://user:pw@abcd1234.supabase.co/auth/v1',
    'https://issuer.example/oauth',
    '',
  ])
    expect(supabaseProjectUrl(rejected)).toBeNull();
});

test('consent redirects an authorization code only to this console callback', () => {
  const origin = 'https://riskweave.example';
  expect(
    trustedRedirect(`${origin}/auth/callback?code=abc&state=xyz`, origin),
  ).toBe(`${origin}/auth/callback?code=abc&state=xyz`);
  for (const rejected of [
    'https://attacker.example/auth/callback?code=abc',
    `${origin}/investigations?code=abc`,
    `${origin}.attacker.example/auth/callback?code=abc`,
    'javascript:alert(1)',
    'not a url',
  ])
    expect(trustedRedirect(rejected, origin)).toBeNull();
});

test('consent page reports missing configuration without contacting a provider', async ({
  page,
}) => {
  const providerRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('supabase')) providerRequests.push(request.url());
  });
  await page.goto('/oauth/consent?authorization_id=test-id');
  await expect(page.getByText('Analyst sign-in is not configured')).toBeVisible();
  expect(providerRequests).toEqual([]);
});
