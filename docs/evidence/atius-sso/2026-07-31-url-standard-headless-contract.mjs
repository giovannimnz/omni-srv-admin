#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { chmod, mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createRequire } from 'node:module';

process.umask(0o077);

const require = createRequire('/home/ubuntu/GitHub/vpn-atius/web/frontend/package.json');
const { chromium } = require('playwright');
const chromiumPath = process.env.E2E_CHROMIUM || '/usr/bin/chromium';
const outputRoot = process.argv[2] || '/home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-31-url-standard-headless';

const hosts = [
  { id: 'central', host: 'sso.atius.com.br', legacyTarget: 'https://ssh.atius.com.br/compute', expectsCookie: true },
  { id: 'ssh', host: 'ssh.atius.com.br', legacyTarget: 'https://ssh.atius.com.br/compute', expectsCookie: true },
  { id: 'rdp', host: 'rdp.atius.com.br', legacyTarget: 'https://rdp.atius.com.br/giovanni-w11-pc', expectsCookie: true },
  { id: 'oci', host: 'oci.atius.com.br', legacyTarget: 'https://oci.atius.com.br/', expectsCookie: true },
  { id: 'talk', host: 'talk.atius.com.br', legacyTarget: 'https://talk.atius.com.br/', expectsCookie: true },
  { id: 'admin-talk', host: 'admin.talk.atius.com.br', legacyTarget: 'https://admin.talk.atius.com.br/', expectsCookie: true },
  { id: 'remote', host: 'remote.atius.com.br', legacyTarget: 'https://remote.atius.com.br/mt5/1/', expectsCookie: true },
  { id: 'grafana', host: 'grafana.atius.com.br', legacyTarget: 'https://grafana.atius.com.br/', expectsCookie: false },
  { id: 'portainer', host: 'portainer.atius.com.br', legacyTarget: 'https://portainer.atius.com.br/', expectsCookie: false },
  { id: 'docker', host: 'docker.atius.com.br', legacyTarget: 'https://docker.atius.com.br/', expectsCookie: false },
  { id: 'vpn', host: 'vpn.atius.com.br', legacyTarget: 'https://vpn.atius.com.br/', expectsCookie: false },
  { id: 'adguard', host: 'adguard.atius.com.br', legacyTarget: 'https://adguard.atius.com.br/', expectsCookie: false },
];

function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex');
}

function cleanUrl(url) {
  const parsed = new URL(url);
  return `${parsed.origin}${parsed.pathname}`;
}

function assertCleanLoginUrl(url, host) {
  const parsed = new URL(url);
  if (parsed.origin !== `https://${host}` || parsed.pathname !== '/login' || parsed.search !== '' || parsed.hash !== '') {
    throw new Error(`URL final não é /login limpo para ${host}: ${url}`);
  }
}

async function documentHeaders(page, response) {
  if (!response) return null;
  return {
    status: response.status(),
    url: cleanUrl(response.url()),
    location: response.headers()['location'] || null,
    setCookiePresent: Boolean(response.headers()['set-cookie']),
  };
}

async function screenshot(page, dir, name) {
  const path = join(dir, `${name}.png`);
  await page.evaluate((visibleUrl) => {
    document.getElementById('__atius_url_contract_evidence')?.remove();
    const banner = document.createElement('div');
    banner.id = '__atius_url_contract_evidence';
    banner.textContent = `EVIDENCE URL: ${visibleUrl}`;
    banner.style.cssText = [
      'position:fixed', 'z-index:2147483647', 'left:0', 'right:0', 'top:0',
      'padding:8px 12px', 'background:#111827', 'color:#f9fafb',
      'font:13px/1.3 monospace', 'border-bottom:2px solid #f97316',
      'pointer-events:none',
    ].join(';');
    document.documentElement.appendChild(banner);
  }, cleanUrl(page.url())).catch(() => {});
  const image = await page.screenshot({ fullPage: true, timeout: 60_000 });
  await page.evaluate(() => document.getElementById('__atius_url_contract_evidence')?.remove()).catch(() => {});
  await writeFile(path, image, { mode: 0o600 });
  await chmod(path, 0o600);
  return { path, sha256: sha256(image), url: cleanUrl(page.url()) };
}

async function main() {
  await mkdir(outputRoot, { recursive: true, mode: 0o700 });
  const browser = await chromium.launch({ executablePath: chromiumPath, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const startedAt = new Date().toISOString();
  const sites = [];

  try {
    for (const site of hosts) {
      const dir = join(outputRoot, site.id);
      await mkdir(dir, { recursive: true, mode: 0o700 });
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: false, locale: 'pt-BR' });
      const page = await context.newPage();
      const siteResult = { ...site, status: 'PASS', checks: {}, screenshots: [] };
      try {
        const loginResponse = await page.goto(`https://${site.host}/login`, { waitUntil: 'domcontentloaded', timeout: 45_000 });
        assertCleanLoginUrl(page.url(), site.host);
        const bodyText = await page.locator('body').innerText({ timeout: 10_000 }).catch(() => '');
        if (!/Entrar|Email|username|Senha/i.test(bodyText)) {
          throw new Error(`login visual/text not detected for ${site.host}`);
        }
        siteResult.checks.login = { finalUrl: cleanUrl(page.url()), response: await documentHeaders(page, loginResponse) };
        siteResult.screenshots.push(await screenshot(page, dir, '01-login'));

        const ssoResponse = await page.goto(`https://${site.host}/sso`, { waitUntil: 'domcontentloaded', timeout: 45_000 });
        assertCleanLoginUrl(page.url(), site.host);
        siteResult.checks.ssoNoQuery = { finalUrl: cleanUrl(page.url()), response: await documentHeaders(page, ssoResponse) };

        await context.clearCookies();
        const legacyUrl = `https://${site.host}/sso?return_to=${encodeURIComponent(site.legacyTarget)}`;
        const legacyResponse = await page.goto(legacyUrl, { waitUntil: 'domcontentloaded', timeout: 45_000 });
        assertCleanLoginUrl(page.url(), site.host);
        const cookies = await context.cookies(`https://${site.host}/`);
        const returnCookie = cookies.find((cookie) => cookie.name === 'atius_sso_login_return_to');
        if (returnCookie) {
          throw new Error(`one-shot return_to cookie persisted after /login render: ${site.host}`);
        }
        const legacyBody = await page.locator('body').innerText({ timeout: 10_000 }).catch(() => '');
        siteResult.checks.legacy = {
          requested: cleanUrl(legacyUrl),
          finalUrl: cleanUrl(page.url()),
          response: await documentHeaders(page, legacyResponse),
          finalReturnCookie: { present: false },
          transientCarrierExpected: site.expectsCookie,
          loginTextSha256: sha256(Buffer.from(legacyBody)),
        };
        siteResult.screenshots.push(await screenshot(page, dir, '02-legacy-clean-login'));
      } catch (error) {
        siteResult.status = 'FAIL';
        siteResult.error = error instanceof Error ? error.message : String(error);
        siteResult.failure = await screenshot(page, dir, '99-failure').catch(() => null);
      } finally {
        await context.close();
      }
      sites.push(siteResult);
    }
  } finally {
    await browser.close();
  }

  const finalVerdict = sites.every((site) => site.status === 'PASS') ? 'PASS' : 'FAIL';
  const screenshots = sites.flatMap((site) => site.screenshots || []);
  const report = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    startedAt,
    runner: 'playwright-headless',
    finalVerdict,
    publicCanonicalUrl: 'https://<app>.atius.com.br/login',
    compatibilityContract: {
      queryFreeSso: '308-compatible redirect to clean /login, browser final URL has no query',
      legacyReturnTo: 'validated transient cookie for ATS-owned facades, clean /login final URL',
      redirectOnlyApps: 'clean /login final URL without return_to cookie',
    },
    totals: { sites: sites.length, screenshots: screenshots.length },
    sites,
    secretsRecorded: false,
  };
  const reportPath = join(outputRoot, 'report.json');
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
  await chmod(reportPath, 0o600);
  console.log(JSON.stringify({ finalVerdict, reportPath, totals: report.totals, sites: sites.map(({ id, status, error }) => ({ id, status, error })) }, null, 2));
  if (finalVerdict !== 'PASS') process.exit(1);
}

await main();
