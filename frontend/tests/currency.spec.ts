import { test, expect } from '@playwright/test';
import { money, approximateMoney } from '../lib/api';
import { parseExactJson, validMinorAmount } from '../lib/exact-money';
import { validResult } from '../lib/response-validation';
import {
  candidateResult,
  installWorkspace,
  runId,
  workspaceUrl,
} from './workspace-fixtures';

test('minor-unit formatting preserves currency scale and fractional amounts', () => {
  expect(approximateMoney(12345.6, 'USD')).toMatch(/Approx\. USD\s123\.46/);
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

for (const [currency, amount, minor = 12345, legacy = false] of [
  ['USD', /USD\s123\.45/],
  ['JPY', /JPY\s12,345/],
  ['KWD', /KWD\s12\.345/],
  [null, '12,345 unknown-currency minor units'],
  ['USD', /USD\s90,071,992,547,409.93/, '9007199254740993'],
  ['USD', /USD\s90,071,992,547,409.93/, '9007199254740993', true],
] as const) {
  test(`persisted ${currency ?? 'legacy unknown'} ${legacy ? 'legacy integer' : 'API'} ${minor} amounts agree in findings, evidence and timeline`, async ({
    page,
  }) => {
    await installWorkspace(page);
    const data = structuredClone(candidateResult);
    if (currency) data.currency = currency;
    const ring = data.rings[0];
    ring.candidate.estimated_exposure_minor = minor;
    ring.queries.calculate_exposure.estimated_exposure_minor = minor;
    ring.queries.get_transaction_timeline = [
      {
        event_id: 'fixture-payment',
        event_type: 'PAYMENT',
        transaction_id: 'fixture-transaction',
        timestamp: '2026-01-01T00:00:00Z',
        amount_minor: minor,
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
        amount_minor: minor,
        unique_customers: 1,
      },
    ];
    await page.route(`**/api/v1/runs/${runId}/results`, (route) =>
      route.fulfill({
        contentType: 'application/json',
        body: legacy
          ? JSON.stringify(data).replaceAll(
              '"9007199254740993"',
              '9007199254740993',
            )
          : JSON.stringify(data),
      }),
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

test('exact money rejects rounded numbers and malformed decimal amounts', () => {
  expect(money(9007199254740991, 'USD')).toMatch(/USD\s90,071,992,547,409\.91/);
  expect(money('9223372036854775807', 'KWD')).toMatch(
    /KWD\s9,223,372,036,854,775\.807/,
  );
  expect(money('-1', 'USD')).toMatch(/-USD\s0\.01/);
  expect(money('9007199254740993', null)).toBe(
    '9,007,199,254,740,993 unknown-currency minor units',
  );
  expect(() => money(Number('9007199254740993'), 'USD')).toThrow();
  for (const value of ['01', '-1', '1.0', '1e3', '', ' 1', 1.1, Infinity])
    expect(validMinorAmount(value)).toBe(false);
  const parsed = parseExactJson(
    '{"amount_minor":9007199254740993,"text":"9007199254740993","risk_score":0.8,"count":12}',
  );
  expect(parsed).toEqual({
    amount_minor: '9007199254740993',
    text: '9007199254740993',
    risk_score: 0.8,
    count: 12,
  });
  expect(
    validMinorAmount(
      (
        parseExactJson('{"amount_minor":9007199254740990.1}') as {
          amount_minor: unknown;
        }
      ).amount_minor,
    ),
  ).toBe(false);
  const invalid = structuredClone(candidateResult);
  invalid.rings[0].candidate.estimated_exposure_minor =
    Number('9007199254740993');
  expect(validResult(invalid)).toBe(false);
});
