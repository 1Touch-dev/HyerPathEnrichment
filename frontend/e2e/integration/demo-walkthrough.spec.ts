/**
 * Full demo walkthrough against a live Docker backend (FRONTEND_USE_MOCKS=false).
 * Covers marketing → enrich → job → history → console ops → opt-out.
 */
import { test, expect } from '@playwright/test';

const BACKEND_URL = (process.env.BACKEND_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

async function pollBackendHealth(maxAttempts = 90, intervalMs = 2000): Promise<void> {
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

test.describe('Demo walkthrough (live Docker backend)', () => {
  let jobId: string;

  test('hub and recruiter landing CTA opens enrich with tiers', async ({ page }) => {
    test.setTimeout(60_000);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /multi-tier public-signal dossier/i })).toBeVisible();
    await page.goto('/recruiters');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

    await page.getByRole('link', { name: /open console with recruiter tiers/i }).first().click();
    await expect(page).toHaveURL(/\/app\/enrich\?tiers=/);
    await expect(page.getByRole('heading', { name: 'New enrichment' })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: /TIER1/i })).toBeChecked();
    await expect(page.getByRole('checkbox', { name: /TIER2/i })).toBeChecked();
  });

  test('live health is not mock', async ({ page }) => {
    await page.goto('/app/health');
    await expect(page.getByRole('heading', { name: 'System health' })).toBeVisible();
    await expect(page.getByText('ok', { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('hyrepath-enrichment-mock')).toHaveCount(0);
  });

  test('sync enrich completes dossier (tier2)', async ({ page }) => {
    test.setTimeout(180_000);
    const username = `demo-walk-${Date.now()}`;

    await page.goto('/app/enrich');
    await expect(page.getByRole('heading', { name: 'New enrichment' })).toBeVisible();

    await page.getByLabel('Quick (sync)').click();
    await page.getByRole('textbox', { name: 'Username' }).fill(username);
    // Thin-stack friendly: tier2 only
    const tier1 = page.getByRole('checkbox', { name: /TIER1/i });
    if (await tier1.isChecked()) {
      await tier1.click();
    }
    const tier3 = page.getByRole('checkbox', { name: /TIER3/i });
    if (await tier3.isChecked()) {
      await tier3.click();
    }
    const tier4 = page.getByRole('checkbox', { name: /TIER4/i });
    if (await tier4.isChecked()) {
      await tier4.click();
    }
    await expect(page.getByRole('checkbox', { name: /TIER2/i })).toBeChecked();

    await expect(page.getByRole('button', { name: 'Run enrichment' })).toBeEnabled({ timeout: 15_000 });
    await page.getByRole('button', { name: 'Run enrichment' }).click();

    await expect(page).toHaveURL(/\/app\/jobs\/.+/, { timeout: 120_000 });
    await expect(page.getByRole('heading', { name: 'Job dossier' })).toBeVisible();
    await expect(page.getByText('completed', { exact: true })).toBeVisible({ timeout: 120_000 });

    const match = page.url().match(/\/app\/jobs\/([^/?#]+)/);
    expect(match?.[1]).toBeTruthy();
    jobId = match![1];
  });

  test('job detail reload and history', async ({ page }) => {
    test.skip(!jobId, 'requires job from sync enrich');

    await page.goto(`/app/jobs/${jobId}`);
    await expect(page.getByRole('heading', { name: 'Job dossier' })).toBeVisible();
    await expect(page.locator('code').filter({ hasText: jobId })).toBeVisible();

    await page.goto('/app/history');
    await expect(page.getByRole('heading', { name: 'Job history' })).toBeVisible();
    await expect(page.getByRole('link', { name: jobId })).toBeVisible({ timeout: 15_000 });
  });

  test('dashboard, settings, privacy, results hub', async ({ page }) => {
    await page.goto('/app');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Total jobs')).toBeVisible();
    await expect(page.locator('p.text-destructive')).toHaveCount(0);

    await page.goto('/app/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    await page.goto('/app/privacy');
    await expect(page.getByRole('heading', { name: 'Privacy & DSAR' })).toBeVisible();

    await page.goto('/app/jobs');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  });

  test('opt-out succeeds against live API', async ({ page }) => {
    await page.goto('/opt-out');
    await expect(page.getByRole('heading', { name: /opt out of enrichment/i })).toBeVisible();
    await page.getByLabel('Identifier').fill(`demo-optout-${Date.now()}@example.com`);
    await page.getByRole('button', { name: /submit opt out/i }).click();
    await expect(page.getByTestId('opt-out-success')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('Request accepted')).toBeVisible();
  });
});
