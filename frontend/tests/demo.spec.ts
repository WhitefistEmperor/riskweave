import { test, expect } from '@playwright/test';

test('small-screen navigation and optional WebMCP contract', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const registry: Record<string, { execute: (input: unknown) => unknown }> =
      {};
    Object.defineProperty(window, '__testTools', { value: registry });
    Object.defineProperty(document, 'modelContext', {
      value: {
        registerTool(
          tool: { name: string; execute: (input: unknown) => unknown },
          options: { signal: AbortSignal },
        ) {
          registry[tool.name] = tool;
          options.signal.addEventListener('abort', () => {
            delete registry[tool.name];
          });
        },
      },
    });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/demo');
  await expect(page).toHaveTitle('RiskWeave | Network Risk Operations');
  await expect(
    page.getByRole('heading', {
      name: 'See the ring. Not just the transaction.',
    }),
  ).toBeVisible();
  const result = await page.evaluate(() => {
    const registry = (
      window as unknown as {
        __testTools: Record<string, { execute: (input: unknown) => unknown }>;
      }
    ).__testTools;
    const before = registry.read_ring_console.execute({});
    let invalidRejected = false;
    try {
      registry.control_ring_replay.execute({ action: 'delete' });
    } catch {
      invalidRejected = true;
    }
    registry.control_ring_replay.execute({ action: 'step' });
    return { names: Object.keys(registry).sort(), invalidRejected, before };
  });
  expect(result.names).toEqual([
    'control_ring_replay',
    'navigate_ring_workspace',
    'read_ring_console',
  ]);
  expect(result.invalidRejected).toBe(true);
  await expect(page.getByText('2 / 104 window events')).toBeVisible();
  await page.getByRole('button', { name: 'Toggle Sidebar' }).click();
  await page.getByRole('button', { name: 'Benchmark', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'The benchmark, with the caveats.' }),
  ).toBeVisible();
});

test('measured benchmark and benign sharing outcomes are visible', async ({
  page,
}) => {
  await page.goto('/demo');
  await expect(
    page.getByRole('heading', {
      name: 'See the ring. Not just the transaction.',
    }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Benchmark', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'The benchmark, with the caveats.' }),
  ).toBeVisible();
  await expect(page.getByText('8.14%', { exact: true })).toBeVisible();
  await expect(page.getByText('4.44%', { exact: true })).toBeVisible();
  await expect(
    page.getByRole('columnheader', { name: 'Benign-community flag rate' }),
  ).toBeVisible();
  await page.screenshot({
    path: '../outputs/phase4-benchmark.png',
    fullPage: true,
  });
  await page
    .getByRole('button', { name: 'Hard negatives', exact: true })
    .click();
  await expect(
    page.getByText('Community flagged', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Not flagged', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /hostel/ }).click();
  await expect(
    page.getByText('Community flagged', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Not flagged', { exact: true })).toBeVisible();
  await page.screenshot({
    path: '../outputs/phase4-hard-negatives.png',
    fullPage: true,
  });
});

test('grounded investigator cites evidence and handles unsupported questions', async ({
  page,
}) => {
  await page.goto('/demo');
  await expect(
    page.getByRole('heading', {
      name: 'See the ring. Not just the transaction.',
    }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Ring Explorer', exact: true })
    .click();
  await page.getByRole('tab', { name: 'Investigator', exact: true }).click();
  await page
    .getByRole('button', { name: 'Ask investigator', exact: true })
    .click();
  await expect(
    page.getByText('Deterministic evidence fallback · no LLM', { exact: true }),
  ).toBeVisible();
  await expect(page.locator('.evidence-citation').first()).toBeVisible();
  await page.screenshot({
    path: '../outputs/phase4-investigator.png',
    fullPage: true,
  });
  await page
    .getByLabel('ANALYST QUESTION')
    .fill('What is the account owner’s real name?');
  await page
    .getByRole('button', { name: 'Ask investigator', exact: true })
    .click();
  await expect(
    page.getByText(/outside the supported evidence queries/),
  ).toBeVisible();
});

test('real replay starts, pauses, steps, and resets without future candidate evidence', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/demo');
  await expect(
    page.getByRole('heading', {
      name: 'See the ring. Not just the transaction.',
    }),
  ).toBeVisible();
  await expect(page.getByText('No focus candidate yet')).toBeVisible();
  await page.screenshot({
    path: '../outputs/phase4-overview.png',
    fullPage: true,
  });
  await page.getByRole('button', { name: 'Step', exact: true }).click();
  await expect(page.getByText('2 / 104 window events')).toBeVisible();
  await page.getByRole('button', { name: 'Start replay', exact: true }).click();
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await page.getByRole('button', { name: 'Reset', exact: true }).click();
  await expect(page.getByText('1 / 104 window events')).toBeVisible();
  await expect(page.getByText('No focus candidate yet')).toBeVisible();
  expect(errors).toEqual([]);
});

test('candidate opens prefix-only explorer, interactive graph, evidence, and timeline', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/demo');
  await page.getByRole('button', { name: 'Start replay', exact: true }).click();
  await page
    .getByRole('button', { name: 'Open Ring Explorer', exact: true })
    .click();
  await expect(
    page.getByText(/Replay snapshot · no later events included/),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Fit graph', exact: true }),
  ).toBeVisible();
  await page.getByRole('combobox', { name: 'Inspect graph node' }).click();
  await page.getByRole('option').first().click();
  await page
    .getByRole('button', { name: 'Focus selected', exact: true })
    .click();
  await page.getByRole('button', { name: 'Fit graph', exact: true }).click();
  await page
    .getByRole('button', { name: 'shared devices', exact: true })
    .click();
  await page.screenshot({
    path: '../outputs/phase4-explorer.png',
    fullPage: true,
  });
  await page.getByRole('tab', { name: 'Activity timeline' }).click();
  await expect(
    page.getByText('First connected candidate precursor', { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: '../outputs/phase4-timeline.png',
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
