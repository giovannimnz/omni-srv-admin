// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const PRINTS_DIR = process.env.PRINTS_DIR || '/home/ubuntu/Prints';
if (!fs.existsSync(PRINTS_DIR)) {
  fs.mkdirSync(PRINTS_DIR, { recursive: true });
}

test.describe('Atius Fleet & CI/CD Multi-Environment Validation (DEV & PRD)', () => {
  test.use({ ignoreHTTPSErrors: true });

  test('PRD GitLab (.com.br) displays Atius SSO button', async ({ page }) => {
    await page.goto('https://gitlab.atius.com.br/users/sign_in', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expect(page).toHaveTitle(/GitLab/i);
    const ssoButton = page.locator('button[data-testid="oidc-login-button"], button:has-text("Atius SSO")');
    await expect(ssoButton).toBeVisible({ timeout: 15000 });

    const screenshotPath = path.join(PRINTS_DIR, 'gitlab_atius_com_br_signin.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`[PASS] gitlab.atius.com.br verified. Screenshot: ${screenshotPath}`);
  });

  test('DEV GitLab (gitlabdev.atius.com.br) displays Atius SSO button', async ({ page }) => {
    await page.goto('https://gitlabdev.atius.com.br/users/sign_in', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expect(page).toHaveTitle(/GitLab/i);
    const ssoButton = page.locator('button[data-testid="oidc-login-button"], button:has-text("Atius SSO")');
    await expect(ssoButton).toBeVisible({ timeout: 15000 });

    const screenshotPath = path.join(PRINTS_DIR, 'gitlabdev_atius_com_br_signin.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`[PASS] gitlabdev.atius.com.br verified. Screenshot: ${screenshotPath}`);
  });

  test('DEV Pipeline (pipelinedev.atius.com.br) displays Atius SSO button', async ({ page }) => {
    await page.goto('https://pipelinedev.atius.com.br/users/sign_in', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expect(page).toHaveTitle(/GitLab/i);
    const ssoButton = page.locator('button[data-testid="oidc-login-button"], button:has-text("Atius SSO")');
    await expect(ssoButton).toBeVisible({ timeout: 15000 });

    const screenshotPath = path.join(PRINTS_DIR, 'pipelinedev_atius_com_br_signin.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`[PASS] pipelinedev.atius.com.br verified. Screenshot: ${screenshotPath}`);
  });

  test('PRD Pipeline (pipeline.atius.com.br) displays Atius SSO button', async ({ page }) => {
    await page.goto('https://pipeline.atius.com.br/users/sign_in', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expect(page).toHaveTitle(/GitLab/i);
    const ssoButton = page.locator('button[data-testid="oidc-login-button"], button:has-text("Atius SSO")');
    await expect(ssoButton).toBeVisible({ timeout: 15000 });

    const screenshotPath = path.join(PRINTS_DIR, 'pipeline_atius_com_br_signin.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`[PASS] pipeline.atius.com.br verified. Screenshot: ${screenshotPath}`);
  });

  test('PRD GitLab (.io) displays Atius SSO button', async ({ page }) => {
    await page.goto('https://gitlab.atius.io/users/sign_in', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expect(page).toHaveTitle(/GitLab/i);
    const ssoButton = page.locator('button[data-testid="oidc-login-button"], button:has-text("Atius SSO")');
    await expect(ssoButton).toBeVisible({ timeout: 15000 });

    const screenshotPath = path.join(PRINTS_DIR, 'gitlab_atius_io_signin.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`[PASS] gitlab.atius.io verified. Screenshot: ${screenshotPath}`);
  });

  test('DEV GitLab (gitlabdev.atius.io) displays Atius SSO button', async ({ page }) => {
    await page.goto('https://gitlabdev.atius.io/users/sign_in', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expect(page).toHaveTitle(/GitLab/i);
    const ssoButton = page.locator('button[data-testid="oidc-login-button"], button:has-text("Atius SSO")');
    await expect(ssoButton).toBeVisible({ timeout: 15000 });

    const screenshotPath = path.join(PRINTS_DIR, 'gitlabdev_atius_io_signin.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`[PASS] gitlabdev.atius.io verified. Screenshot: ${screenshotPath}`);
  });

  test('Atius SSO portal renders login UI', async ({ page }) => {
    await page.goto('https://sso.atius.com.br/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    const screenshotPath = path.join(PRINTS_DIR, 'sso_atius_com_br_login.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`[PASS] sso.atius.com.br verified. Screenshot: ${screenshotPath}`);
  });
});
