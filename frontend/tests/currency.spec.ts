import { test, expect } from '@playwright/test';
import { money } from '../lib/api';
import { validResult } from '../lib/response-validation';
import {
  candidateResult,
  installWorkspace,
  runId,
  workspaceUrl,
} from './workspace-fixtures';

test('minor-unit formatting preserves currency scale and fractional amounts', () => {
  expect(money(12345, 'INR')).toMatch(/INR\s123\.45/);
  expect(money(12345, 'USD')).toMatch(/USD\s123\.45/);
  expect(money(12345, 'JPY')).toMatch(/JPY\s12,345/);
  expect(money(12345, 'KWD')).toMatch(/KWD\s12\.345/);
  expect(money(12345, null)).toBe('12,345 unknown-currency minor units');
  expect(money(12345, 'ZZZ')).toBe('12,345 ZZZ minor units');
  expect(money(12345, 'XAU')).toBe('12,345 XAU minor units');
  expect(validResult({ ...candidateResult, currency: 'JPY' })).toBe(true);
  expect(validResult({ ...candidateResult, currency: 'usd' })).toBe(false);
  expect(validResult({ ...candidateResult, currency: 12 })).toBe(false);
});

for (const [currency, amount] of [
  ['USD', /USD\s123\.45/],
  ['JPY', /JPY\s12,345/],
  ['KWD', /KWD\s12\.345/],
  [null, '12,345 unknown-currency minor units'],
] as const) {
  test(`persisted ${currency ?? 'legacy unknown'} amounts agree in findings, evidence and timeline`, async ({
    page,
  }) => {
    await installWorkspace(page);
    const data = structuredClone(candidateResult);
    if (currency) data.currency = currency;
    const ring = data.rings[0];
    ring.candidate.estimated_exposure_minor = 12345;
    ring.queries.calculate_exposure.estimated_exposure_minor = 12345;
    ring.queries.get_transaction_timeline = [
      {
        event_id: 'fixture-payment',
        event_type: 'PAYMENT',
        transaction_id: 'fixture-transaction',
        timestamp: '2026-01-01T00:00:00Z',
        amount_minor: 12345,
        status: 'CAPTURED',
        customer_id: 'ui-customer',
        merchant_id: 'ui-merchant',
        risk_score: 0.8,
      },
    ];
    ring.queries.get_temporal_activity = [
      {
        hour: '2026-01-01T00:00:00Z',
        event_count: 1,
        payment_count: 1,
        refund_count: 0,
        amount_minor: 12345,
        unique_customers: 1,
      },
    ];
    await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
      route.fulfill({ json: data }),
    );
    await page.goto(workspaceUrl);
    await expect(page.locator('.findings-workspace')).toContainText(amount);
    await page.getByRole('button', { name: /^Open ring / }).click();
    await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
    await page
      .getByRole('button', { name: 'Exposure accounting', exact: true })
      .click();
    await expect(page.locator('.grouped-evidence')).toContainText(amount);
    await page.getByRole('tab', { name: 'Timeline', exact: true }).click();
    await expect(page.locator('.timeline-workspace')).toContainText(amount);
    await expect(page.locator('.timeline-workspace')).not.toContainText('INR');
    if (currency)
      await expect(page.locator('.model-scope')).toContainText(
        'scoring for this currency has not been validated',
      );
    else
      await expect(page.locator('.model-scope')).toContainText(
        'currency: unknown',
      );
  });
}
