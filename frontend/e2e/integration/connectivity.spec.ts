import { test, expect } from '@playwright/test';

const BACKEND_URL = (process.env.BACKEND_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

async function pollBackendHealth(maxAttempts = 60, intervalMs = 2000): Promise<void> {
  let lastError = 'unknown';

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      const response = await fetch(`${BACKEND_URL}/health`);
      if (response.status === 200) {
        return;
      }
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error(`Backend at ${BACKEND_URL}/health did not return 200 (last: ${lastError})`);
}

test.describe.configure({ mode: 'serial' });

test.beforeAll(async () => {
  await pollBackendHealth();
});

test.describe('Live backend integration', () => {
  let jobId: string;

  test('health page reports live backend (not mock)', async ({ page }) => {
    await page.goto('/app/health');
    await expect(page.getByRole('heading', { name: 'System health' })).toBeVisible();
    await expect(page.getByText('ok', { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('hyrepath-enrichment-mock')).toHaveCount(0);
  });

  test('sync enrich completes dossier', async ({ page }) => {
    const username = `e2e-${Date.now()}`;

    await page.goto('/app/enrich');
    await expect(page.getByRole('heading', { name: 'New enrichment' })).toBeVisible();

    await page.getByLabel('Quick (sync)').click();
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    // Faster live run: tier2 only (tier3/4 sidecars may be absent locally)
    await page.getByRole('checkbox', { name: 'TIER3 — Deep OSINT' }).click();
    await page.getByRole('checkbox', { name: 'TIER4 — Job & Business Intelligence' }).click();
    await expect(page.getByRole('button', { name: 'Run enrichment' })).toBeEnabled({ timeout: 15_000 });
    await page.getByRole('button', { name: 'Run enrichment' }).click();

    await expect(page).toHaveURL(/\/app\/jobs\/.+/, { timeout: 120_000 });
    await expect(page.getByRole('heading', { name: 'Job dossier' })).toBeVisible();
    await expect(page.getByText('completed', { exact: true })).toBeVisible({ timeout: 60_000 });

    const match = page.url().match(/\/app\/jobs\/([^/?#]+)/);
    expect(match?.[1]).toBeTruthy();
    jobId = match![1];
  });

  test('job detail page loads', async ({ page }) => {
    test.skip(!jobId, 'requires job from sync enrich test');

    await page.goto(`/app/jobs/${jobId}`);
    await expect(page.getByRole('heading', { name: 'Job dossier' })).toBeVisible();
    await expect(page.locator('code').filter({ hasText: jobId })).toBeVisible();
  });

  test('history list shows at least one job', async ({ page }) => {
    test.skip(!jobId, 'requires job from sync enrich test');

    await page.goto('/app/history');
    await expect(page.getByRole('heading', { name: 'Job history' })).toBeVisible();
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('link', { name: jobId })).toBeVisible();
  });

  test('dashboard shows total jobs without error', async ({ page }) => {
    await page.goto('/app');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Total jobs')).toBeVisible();
    await expect(page.locator('p.text-destructive')).toHaveCount(0);
  });

  test('opt-out submission succeeds', async ({ page }) => {
    await page.goto('/opt-out');
    await expect(page.getByRole('heading', { name: /opt out of enrichment/i })).toBeVisible();
    await page.getByLabel('Identifier').fill(`e2e-optout-${Date.now()}@example.com`);
    await page.getByRole('button', { name: /submit opt out/i }).click();
    await expect(page.getByTestId('opt-out-success')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('Request accepted')).toBeVisible();
  });
});
