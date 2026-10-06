import { expect, test } from '@playwright/test';
import { connectionSources } from '../lib/security-policy.mjs';

test('identity connection configuration rejects wildcard and credential sources', () => {
  for (const extra of ['["https://*.example"]', '["https://user:fixture-secret@issuer.example"]',
    '["http://issuer.example"]', '["https://issuer.example/path"]', '["https://issuer.example;script-src"]']) {
    expect(() => connectionSources('https://issuer.example/tenant', extra, true))
      .toThrow('OIDC connection origins must be explicit HTTP(S) origins');
  }
  expect(connectionSources('https://issuer.example/tenant', '["https://token.example"]', true))
    .toEqual(['https://issuer.example', 'https://token.example']);
});

test('fresh server nonce hydrates the workspace and blocks injected scripts and handlers', async ({ page }) => {
  await page.setExtraHTTPHeaders({
    'x-nonce': 'caller-selected-nonce',
    'Content-Security-Policy': "script-src 'unsafe-inline'",
  });
  const violations: string[] = [];
  page.on('console', message => {
    if (message.text().includes('Content Security Policy')) violations.push(message.text());
  });
  const response = await page.goto('/investigations');
  const policy = response!.headers()['content-security-policy'];
  const nonce = policy.match(/'nonce-([^']+)'/)?.[1];
  expect(nonce).toBeTruthy();
  expect(nonce).not.toBe('caller-selected-nonce');
  const scripts = policy.split(';').find(value => value.trim().startsWith('script-src '))!;
  expect(scripts).toContain("'strict-dynamic'");
  expect(scripts).not.toContain("'unsafe-inline'");
  expect(scripts).not.toContain("'unsafe-eval'");
  expect(response!.headers()['cache-control']).toContain('no-store');
  await expect(page.getByRole('heading', { name: 'Investigations', exact: true })).toBeVisible();
  const inlineNonces = await page.evaluate(() => Array.from(document.scripts)
    .filter(script => !script.src && script.textContent).map(script => script.nonce));
  expect(inlineNonces.length).toBeGreaterThan(0);
  expect(inlineNonces.every(value => value === nonce)).toBe(true);
  expect(violations).toEqual([]);

  await page.route('**/investigations', async route => {
    if (route.request().resourceType() !== 'document') return route.continue();
    const original = await route.fetch();
    const html = (await original.text()).replace('</body>',
      '<script>window.__injectedScript = true</script>' +
      '<button id="injected-handler" onclick="window.__injectedHandler = true">fixture</button></body>');
    await route.fulfill({ response: original, body: html });
  });
  const second = await page.reload();
  await page.locator('#injected-handler').click({ force: true });
  expect(await page.evaluate(() => ({
    script: Reflect.get(window, '__injectedScript'),
    handler: Reflect.get(window, '__injectedHandler'),
  }))).toEqual({ script: undefined, handler: undefined });

  expect(second!.headers()['content-security-policy'].match(/'nonce-([^']+)'/)?.[1]).not.toBe(nonce);
  await expect(page.getByRole('heading', { name: 'Investigations', exact: true })).toBeVisible();
  const missing = await page.request.get('/missing-document.png');
  expect(missing.status()).toBe(404);
  expect(missing.headers()['content-security-policy']).toContain("'nonce-");
});

test('browser connections cannot leave the configured application and identity origins', async ({ page }) => {
  await page.goto('/investigations');
  expect(await page.evaluate(() => new Promise(resolve => {
    document.addEventListener('securitypolicyviolation', event => resolve({
      directive: event.effectiveDirective, blocked: event.blockedURI,
    }), { once: true });
    void fetch('https://unconfigured.example.invalid/private', {
      method: 'POST', body: 'generated-fixture',
    }).catch(() => {});
    setTimeout(() => resolve('no-policy-violation'), 1000);
  }))).toEqual({ directive: 'connect-src', blocked: expect.stringContaining('https://unconfigured.example.invalid') });
  await expect(page.getByRole('heading', { name: 'Investigations', exact: true })).toBeVisible();
});
