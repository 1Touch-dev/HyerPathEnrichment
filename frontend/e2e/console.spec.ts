import { test, expect } from '@playwright/test';

test.describe('Enrichment flow', () => {
  test('async enrichment completes mock job dossier', async ({ page }) => {
    await page.goto('/app/enrich');
    await expect(page.getByRole('heading', { name: 'New enrichment' })).toBeVisible();

    await page.getByRole('textbox', { name: 'Username' }).fill('e2e-playwright');
    await expect(page.getByRole('button', { name: 'Run enrichment' })).toBeEnabled({ timeout: 15_000 });
    await page.getByRole('button', { name: 'Run enrichment' }).click();

    await expect(page.getByRole('heading', { name: 'Job dossier' })).toBeVisible();
    await expect(page.getByText('completed', { exact: true })).toBeVisible({ timeout: 15_000 });
  });

  test('history page lists jobs after enrichment', async ({ page }) => {
    await page.goto('/app/history');
    await expect(page.getByRole('heading', { name: 'Job history' })).toBeVisible();
  });

  test('settings page loads', async ({ page }) => {
    await page.goto('/app/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  });

  test('privacy DSAR ops form loads', async ({ page }) => {
    await page.goto('/app/privacy');
    await expect(page.getByRole('heading', { name: 'Privacy & DSAR' })).toBeVisible();
  });
});
