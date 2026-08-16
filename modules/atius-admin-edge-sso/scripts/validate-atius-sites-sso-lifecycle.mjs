#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { chmod, mkdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import {
  FULL_LIFECYCLE_TARGET_IDS,
  lifecycleVerdict,
  resolveEvidenceScope,
} from './sso-lifecycle-evidence-scope.mjs';

process.umask(0o077);

const require = createRequire('/home/ubuntu/GitHub/vpn-atius/web/frontend/package.json');
process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = '1';
const { chromium } = require('playwright');
const sharp = require('sharp');

const CHROMIUM = process.env.E2E_CHROMIUM || '/usr/bin/chromium';
const VAULT_HOST = 'atius-srv-3';
const VAULT_PATH = 'kv/atius/browser-login/access-keys';
const DEFAULT_OUTPUT_ROOT = '/home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-30-host-local-lifecycle';
function cliValue(name) {
  const exact = process.argv.find((arg) => arg.startsWith(`${name}=`));
  if (exact) return exact.slice(name.length + 1);
  const index = process.argv.indexOf(name);
  if (index !== -1 && process.argv[index + 1] && !process.argv[index + 1].startsWith('--')) return process.argv[index + 1];
  return null;
}
const positionalOutput = process.argv.slice(2).find((arg) => !arg.startsWith('--'));
const OUTPUT_ROOT = resolve(
  cliValue('--evidence-dir')
  || positionalOutput
  || process.env.E2E_OUTPUT_DIR
  || DEFAULT_OUTPUT_ROOT,
);
const CYCLE_COOLDOWN_MS = Number(process.env.E2E_CYCLE_COOLDOWN_MS || 15_000);
const SITE_COOLDOWN_MS = Number(process.env.E2E_SITE_COOLDOWN_MS || 20_000);
const LOGIN_RETRY_DELAY_MS = Number(process.env.E2E_LOGIN_RETRY_DELAY_MS || 25_000);
const LOGIN_ATTEMPTS = Number(process.env.E2E_LOGIN_ATTEMPTS || 2);

const allTargets = [
  { id: 'sso', origin: 'https://sso.atius.com.br', authenticated: /Sessão Atius ativa|Atius SSO/i, readySelector: 'section[aria-live="polite"], div[class*="max-w-md"]', logoutSelector: 'button:has-text("Encerrar sessão"), button:has-text("Sair"), [data-atius-sso-logout="true"]', neutralLoginAuthenticated: true },
  { id: 'ssh', origin: 'https://ssh.atius.com.br', authenticated: /Atius SSH|Acessos remotos via SSH/i, readySelector: '.session, .grid', logoutSelector: '.logout[href="/logout"]' },
  { id: 'rdp', origin: 'https://rdp.atius.com.br', authenticated: /RDP|acesso remoto|credencial temporária|sessão/i, readySelector: 'main, form, .session, .grid', logoutSelector: '.logout[href="/logout"], a[href="/logout"]' },
  { id: 'oci', origin: 'https://oci.atius.com.br', authenticated: /OCI|Oracle Cloud|inventory|compute|network/i, readySelector: 'main, [role="main"], table', logoutSelector: 'a[href="/logout"], button:has-text("Sair"), [data-atius-sso-logout="true"]' },
  { id: 'talk', origin: 'https://talk.atius.com.br', authenticated: /talk\.atius|client portal|shell autenticada|review/i, readySelector: '.page-shell', logoutSelector: 'form[action="/logout"] button, form[action="/logout"] input[type="submit"]' },
  { id: 'admin-talk', origin: 'https://admin.talk.atius.com.br', authenticated: /admin\.talk|Atius Talk Atius Admin|autoridade master|oversight/i, readySelector: '.page-shell', logoutSelector: 'form[action="/logout"] button, form[action="/logout"] input[type="submit"]' },
  { id: 'remote', origin: 'https://remote.atius.com.br', authenticated: /noVNC|VNC|remote|desktop/i, readySelector: '#noVNC_container, #noVNC_status, body', logoutSelector: '[data-atius-sso-logout="true"]' },
  { id: 'grafana', origin: 'https://grafana.atius.com.br', authenticated: /grafana|dashboard/i, readySelector: '[aria-label="Perfil"]', logoutSelector: '[data-atius-sso-logout="true"]' },
  { id: 'portainer', origin: 'https://portainer.atius.com.br', authenticated: /portainer|environment|dashboard/i, readySelector: '[data-cy="userMenu-button"]', logoutSelector: '[data-atius-sso-logout="true"]' },
  { id: 'docker', origin: 'https://docker.atius.com.br', authenticated: /portainer|environment|dashboard/i, readySelector: '[data-cy="userMenu-button"]', logoutSelector: '[data-atius-sso-logout="true"]' },
  { id: 'vpn', origin: 'https://vpn.atius.com.br', authenticated: /interface|wireguard|vpn|peers|rotas|dashboard/i, readySelector: '.page-stack .health-anchor', logoutSelector: '.logout-link[href="/logout"]' },
  { id: 'adguard', origin: 'https://adguard.atius.com.br', authenticated: /adguard|dns|filter|client|dashboard|consulta/i, readySelector: 'a[href="control/logout"], a[href="/control/logout"]', logoutSelector: 'a[href="control/logout"], a[href="/control/logout"]' },
];
const evidenceScope = resolveEvidenceScope(
  allTargets,
  process.env.E2E_TARGETS,
  process.env.E2E_ALLOW_SUBSET_PASS === '1',
);
const { targets } = evidenceScope;

function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex');
}

function sanitizedUrl(raw) {
  const url = new URL(raw);
  return `${url.origin}${url.pathname}`;
}

function vaultCredentials() {
  const raw = execFileSync('ssh', [
    '-n',
    '-o', 'ProxyCommand=none',
    '-o', 'BatchMode=yes',
    '-o', 'ConnectTimeout=10',
    '-o', 'IPQoS=none',
    VAULT_HOST,
    `sudo -n /usr/local/sbin/atius-vault kv get -format=json ${VAULT_PATH}`,
  ], { encoding: 'utf8', timeout: 20_000 });
  const data = JSON.parse(raw).data.data;
  if (!data.username || !data.password) throw new Error('browser-login credentials incomplete');
  return { username: String(data.username), password: String(data.password) };
}

function scrub(message, credentials) {
  return String(message)
    .replaceAll(credentials.username, '[REDACTED_USERNAME]')
    .replaceAll(credentials.password, '[REDACTED_PASSWORD]');
}

async function screenshot(page, targetDir, cycle, stage, stageName) {
  const name = `cycle-${cycle}-${stage}-${stageName}.png`;
  const path = join(targetDir, name);
  await page.evaluate((url) => {
    document.getElementById('__atius_evidence_url')?.remove();
    const banner = document.createElement('div');
    banner.id = '__atius_evidence_url';
    banner.textContent = `EVIDENCE URL: ${url}`;
    banner.style.cssText = [
      'position:fixed',
      'z-index:2147483647',
      'left:0',
      'right:0',
      'top:0',
      'padding:8px 12px',
      'background:#111827',
      'color:#f9fafb',
      'font:13px/1.3 monospace',
      'border-bottom:2px solid #f97316',
      'box-shadow:0 2px 8px rgba(0,0,0,.35)',
      'pointer-events:none',
    ].join(';');
    document.documentElement.appendChild(banner);
  }, sanitizedUrl(page.url())).catch(() => {});
  const image = await page.screenshot({ fullPage: true, timeout: 60_000 });
  await page.evaluate(() => document.getElementById('__atius_evidence_url')?.remove()).catch(() => {});
  await writeFile(path, image, { mode: 0o600 });
  await chmod(path, 0o600);
  return { name, path, sha256: sha256(image), url: sanitizedUrl(page.url()) };
}

async function waitForLogin(page, origin) {
  await waitForCurrentUrl(page, (url) => url.origin === origin && url.pathname === '/login', 60_000);
  await page.getByPlaceholder('Digite seu email ou username').first().waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByPlaceholder('Digite sua senha').first().waitFor({ state: 'visible', timeout: 30_000 });
  await page.waitForFunction(() => {
    const button = [...document.querySelectorAll('button')]
      .find((element) => /Entrar com Atius SSO|Entrar/i.test(element.textContent || ''));
    const form = button?.closest('form');
    if (!form) return false;
    const hasReactHandler = [...Object.keys(form), ...Object.keys(button)]
      .some((key) => key.startsWith('__reactProps$') || key.startsWith('__reactFiber$'));
    const nativePost = form.method.toLowerCase() === 'post' && form.action.length > 0;
    return hasReactHandler || nativePost;
  }, { timeout: 30_000 });
  if (new URL(page.url()).search) throw new Error(`login URL is not clean: ${sanitizedUrl(page.url())}`);
  const visual = await page.evaluate(() => {
    const card = document.querySelector('.card, main > section, .w-full.max-w-md.rounded-xl, div[class*="max-w-md"][class*="rounded-xl"]');
    const logo = document.querySelector('.brand-mark, img[alt="Atius"]');
    const destinationLabel = [...document.querySelectorAll('small, p, span')]
      .find((element) => /destino seguro/i.test(element.textContent || ''));
    const destinationHost = destinationLabel?.parentElement
      ? [...destinationLabel.parentElement.querySelectorAll('span')]
        .find((element) => {
          const text = (element.textContent || '').trim();
          return text && !/destino seguro/i.test(text);
        })
      : null;
    const labels = [...document.querySelectorAll('label')].map((label) => (
      [...label.children].find((element) => /^(Email ou username|Senha)$/.test((element.textContent || '').trim()))
      || label
    ));
    const button = document.querySelector('button[type="submit"]');
    const inputs = [...document.querySelectorAll('input')].slice(0, 2);
    const style = (element) => element ? getComputedStyle(element) : null;
    const rect = (element) => element ? element.getBoundingClientRect() : null;
    const iconLinks = [...document.querySelectorAll('link[rel*="icon"]')].map((element) => element.href);
    return {
      card: card ? { width: rect(card).width, radius: style(card).borderRadius, padding: style(card).padding } : null,
      logo: logo ? { width: rect(logo).width, height: rect(logo).height } : null,
      destinationLabel: destinationLabel ? {
        fontSize: style(destinationLabel).fontSize,
        fontWeight: style(destinationLabel).fontWeight,
        lineHeight: style(destinationLabel).lineHeight,
        letterSpacing: style(destinationLabel).letterSpacing,
      } : null,
      destinationHost: destinationHost ? {
        text: (destinationHost.textContent || '').trim(),
        fontSize: style(destinationHost).fontSize,
        fontWeight: style(destinationHost).fontWeight,
        lineHeight: style(destinationHost).lineHeight,
      } : null,
      labels: labels.map((element) => ({
        fontSize: style(element).fontSize,
        fontWeight: style(element).fontWeight,
        lineHeight: style(element).lineHeight,
      })),
      inputs: inputs.map((element) => ({
        height: rect(element).height,
        radius: style(element).borderRadius,
      })),
      button: button ? {
        height: rect(button).height,
        fontSize: style(button).fontSize,
        fontWeight: style(button).fontWeight,
        lineHeight: style(button).lineHeight,
        radius: style(button).borderRadius,
      } : null,
      iconLinks,
      emoji: /[👤🔒👁]/u.test(document.body.textContent || ''),
      background: [
        document.body,
        document.querySelector('main'),
        document.querySelector('.bg-dark-gradient'),
        document.querySelector('[class*="bg-dark-gradient"]'),
      ]
        .map((element) => element ? getComputedStyle(element).backgroundImage : 'none')
        .find((value) => value && value !== 'none') || 'none',
    };
  });
  const expectedFont = (value, fontSize, fontWeight, lineHeight) => (
    value?.fontSize === fontSize && value?.fontWeight === fontWeight && value?.lineHeight === lineHeight
  );
  const expectedDestination = new URL(origin).hostname;
  const neutralDestination = visual.destinationHost?.text === 'Nenhum destino selecionado';
  if (
    !visual.card || Math.abs(visual.card.width - 448) > 1 || visual.card.radius !== '12px'
    || !visual.logo || visual.logo.width < 39 || visual.logo.width > 45 || visual.logo.height < 39 || visual.logo.height > 45
    || !expectedFont(visual.destinationLabel, '11px', '400', '16.5px') || visual.destinationLabel.letterSpacing !== 'normal'
    || !expectedFont(visual.destinationHost, '14px', '400', '20px')
    || (neutralDestination ? expectedDestination !== 'sso.atius.com.br' : visual.destinationHost.text !== expectedDestination)
    || (!neutralDestination && /[:/?#]/.test(visual.destinationHost.text))
    || visual.labels.length !== 2 || visual.labels.some((value) => !expectedFont(value, '14px', '500', '20px'))
    || visual.inputs.length !== 2 || visual.inputs.some((value) => Math.abs(value.height - 44) > 1 || value.radius !== '10px')
    || !expectedFont(visual.button, '14px', '500', '20px') || Math.abs(visual.button.height - 44) > 1 || visual.button.radius !== '10px'
    || visual.emoji || !/linear-gradient/i.test(visual.background)
    || visual.iconLinks.length === 0 || !visual.iconLinks.some((href) => /atius|_atius/i.test(href))
  ) {
    throw new Error(`canonical login visual contract failed at ${sanitizedUrl(page.url())}: ${JSON.stringify(visual)}`);
  }
}

async function waitForCurrentUrl(page, predicate, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const current = new URL(page.url());
      if (predicate(current)) return current;
    } catch {}
    await page.waitForTimeout(250);
  }
  throw new Error(`URL predicate timed out at ${sanitizedUrl(page.url())}`);
}

async function waitForRemoteFramebuffer(page) {
  const deadline = Date.now() + 60_000;
  let lastStats = { uniqueColors: 0, nonBlackRatio: 0 };
  while (Date.now() < deadline) {
    const statusText = (await page.locator('#noVNC_status').allInnerTexts().catch(() => []))
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
    if (/disconnected|failed to connect|connection closed|unable to connect/i.test(statusText)) {
      throw new Error(`remote noVNC reported a connection failure: ${statusText}`);
    }
    const viewport = page.viewportSize();
    if (!viewport || viewport.width < 420 || viewport.height < 360) {
      await page.waitForTimeout(500);
      continue;
    }
    const image = await page.screenshot({
      animations: 'disabled',
      clip: {
        x: 0,
        y: 40,
        width: viewport.width - 100,
        height: viewport.height - 120,
      },
      timeout: 15_000,
    });
    const { data, info } = await sharp(image)
      .resize({ width: 160, height: 100, fit: 'fill' })
      .removeAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });
    const colors = new Set();
    let nonBlack = 0;
    for (let index = 0; index < data.length; index += info.channels) {
      const red = data[index];
      const green = data[index + 1];
      const blue = data[index + 2];
      colors.add((red << 16) | (green << 8) | blue);
      if (red >= 12 || green >= 12 || blue >= 12) nonBlack += 1;
    }
    lastStats = {
      uniqueColors: colors.size,
      nonBlackRatio: nonBlack / (data.length / info.channels),
    };
    if (lastStats.uniqueColors >= 16 && lastStats.nonBlackRatio >= 0.005) return;
    await page.waitForTimeout(500);
  }
  throw new Error(`remote noVNC framebuffer remained blank: ${JSON.stringify(lastStats)}`);
}

async function visibleLoginError(page) {
  const text = await page.locator('body').innerText({ timeout: 3_000 }).catch(() => '');
  return /não foi possível entrar|credenciais|invalid|erro/i.test(text);
}

async function login(page, target, credentials) {
  let lastError = '';
  for (let attempt = 1; attempt <= LOGIN_ATTEMPTS; attempt += 1) {
    const currentBeforeLogin = new URL(page.url());
    if (currentBeforeLogin.origin === target.origin && currentBeforeLogin.pathname !== '/login') {
      await waitForAuthenticatedUi(page, target);
      return;
    }
    await waitForLogin(page, target.origin);
    if (target.neutralLoginAuthenticated) {
      const text = await page.locator('body').innerText().catch(() => '');
      if (/Sessão Atius ativa/i.test(text)) {
        throw new Error('central SSO session became authenticated without credential submission');
      }
    }
    try {
      await page.getByPlaceholder('Digite seu email ou username').first().fill(credentials.username);
      await page.getByPlaceholder('Digite sua senha').first().fill(credentials.password);
      await page.getByRole('button', { name: /Entrar com Atius SSO|Entrar/i }).first().click();
    } catch (error) {
      const currentAfterDetachedLogin = new URL(page.url());
      if (currentAfterDetachedLogin.origin === target.origin && currentAfterDetachedLogin.pathname !== '/login') {
        await waitForAuthenticatedUi(page, target);
        return;
      }
      throw error;
    }
    const start = Date.now();
    while (Date.now() - start < 60_000) {
      const current = new URL(page.url());
      if (current.origin !== target.origin) throw new Error(`foreign visible origin observed after login click: ${sanitizedUrl(page.url())}`);
      if (target.neutralLoginAuthenticated && current.pathname === '/login') {
        const text = await page.locator('body').innerText().catch(() => '');
        if (/Sessão Atius ativa/i.test(text) && /Encerrar sessão|Sair/i.test(text)) {
          await waitForAuthenticatedUi(page, target);
          return;
        }
      }
      if (current.pathname !== '/login') {
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 }).catch(() => {});
        await waitForAuthenticatedUi(page, target);
        return;
      }
      if (await visibleLoginError(page)) {
        lastError = `login attempt ${attempt} stayed on /login with visible auth error`;
        break;
      }
      await page.waitForTimeout(500);
    }
    if (attempt < LOGIN_ATTEMPTS) {
      await page.waitForTimeout(LOGIN_RETRY_DELAY_MS);
      await page.goto(`${target.origin}/login`, { waitUntil: 'commit', timeout: 30_000 }).catch(() => {});
    }
  }
  throw new Error(lastError || `login did not leave app-local /login at ${sanitizedUrl(page.url())}`);
}

async function waitForAuthenticatedUi(page, target) {
  if (target.id === 'grafana') {
    const current = new URL(page.url());
    if (current.pathname.startsWith('/d/')) {
      const operationalWindow = new URL(current);
      operationalWindow.searchParams.set('from', 'now-15m');
      operationalWindow.searchParams.set('to', 'now');
      if (operationalWindow.href !== current.href) {
        await page.goto(operationalWindow.href, { waitUntil: 'domcontentloaded', timeout: 45_000 });
      }
      await page.setViewportSize({ width: 1440, height: 1800 });
    }
  }
  await page.locator(target.readySelector).first().waitFor({ state: 'visible', timeout: 60_000 });
  if (target.id === 'remote') await waitForRemoteFramebuffer(page);
  const text = `${await page.title()} ${await page.locator('body').innerText().catch(() => '')}`;
  if (!target.authenticated.test(text)) {
    throw new Error(`authenticated marker not found at ${sanitizedUrl(page.url())}`);
  }
  if (/authentication in progress|unable to retrieve application settings/i.test(text)) {
    throw new Error(`authenticated UI remained in failure/loading state at ${sanitizedUrl(page.url())}`);
  }
  if (target.id === 'grafana') {
    const panels = page.locator('section[data-testid^="data-testid Panel header "]:visible');
    await panels.first().waitFor({ state: 'visible', timeout: 60_000 });
    const panelContents = page.locator('section[data-testid^="data-testid Panel header "] [data-testid="data-testid panel content"]:visible');
    await page.waitForFunction(() => {
      const visiblePanels = [...document.querySelectorAll('section[data-testid^="data-testid Panel header "]')]
        .filter((element) => {
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
        });
      if (visiblePanels.length < 2) return false;
      const contents = visiblePanels
        .map((panel) => panel.querySelector('[data-testid="data-testid panel content"]'))
        .filter(Boolean);
      if (contents.length !== visiblePanels.length) return false;
      const texts = contents.map((content) => (content.textContent || '').replace(/\s+/g, ' ').trim());
      return texts.every((panelText) => (
        panelText.length > 0
        && !/(^|\b)(sem dados|no data|loading|carregando)(\b|$)/i.test(panelText)
        && !/datasource.*(error|unavailable)|query error|failed to fetch|no data source/i.test(panelText)
      ));
    }, { timeout: 60_000 });
    const visiblePanelCount = await panels.count();
    const panelContentTexts = await panelContents.allInnerTexts();
    const invalidPanels = panelContentTexts.filter((panelText) => (
      /(^|\b)(sem dados|no data|loading|carregando)(\b|$)/i.test(panelText)
      || /datasource.*(error|unavailable)|query error|failed to fetch|no data source/i.test(panelText)
    ));
    if (visiblePanelCount < 2 || panelContentTexts.length !== visiblePanelCount || invalidPanels.length > 0) {
      throw new Error(`grafana dashboard has incomplete or invalid visible panels at ${sanitizedUrl(page.url())}`);
    }
  }
  if (target.id === 'portainer' || target.id === 'docker') {
    if (!new URL(page.url()).hash.includes('/1/kubernetes/dashboard')) {
      const dashboardLink = page.locator('a[href="#!/1/kubernetes/dashboard"]').first();
      await dashboardLink.waitFor({ state: 'visible', timeout: 60_000 });
      await dashboardLink.click();
      await waitForCurrentUrl(page, (url) => (
        url.origin === target.origin && url.hash.includes('/1/kubernetes/dashboard')
      ), 60_000);
    }
    await page.getByText('Environment summary', { exact: true }).first().waitFor({ state: 'visible', timeout: 60_000 });
    const dashboardCards = [
      ['dashboard-namespace', 'Namespaces'],
      ['dashboard-application', 'Applications'],
      ['dashboard-service', 'Services'],
      ['dashboard-ingress', 'Ingresses'],
      ['dashboard-configmaps', 'ConfigMaps'],
      ['dashboard-secrets', 'Secrets'],
      ['dashboard-volume', 'Volumes'],
    ];
    for (const [dataCy, label] of dashboardCards) {
      await page.locator(`[data-cy="${dataCy}"]`).first().waitFor({ state: 'visible', timeout: 60_000 });
      await page.waitForFunction(({ selector, resourceLabel }) => {
        const card = document.querySelector(selector);
        if (!card) return false;
        const text = (card.textContent || '').replace(/\s+/g, ' ').trim();
        const escapedLabel = resourceLabel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return new RegExp(`(\\d+\\s*${escapedLabel}|${escapedLabel}\\s*\\d+)`, 'i').test(text);
      }, { selector: `[data-cy="${dataCy}"]`, resourceLabel: label }, { timeout: 60_000 });
    }
    await page.waitForTimeout(5_000);
    const environmentText = await page.locator('body').innerText();
    if (!/atius-k3s[\s\S]*Namespaces[\s\S]*Applications[\s\S]*Services/i.test(environmentText)) {
      throw new Error(`portainer Kubernetes environment dashboard is incomplete at ${sanitizedUrl(page.url())}`);
    }
    if (/unable to connect|failed to load|environment is unreachable|endpoint is down/i.test(environmentText)) {
      throw new Error(`portainer Kubernetes environment is unavailable at ${sanitizedUrl(page.url())}`);
    }
  }
}

async function assertAuthenticated(page, target) {
  await waitForAuthenticatedUi(page, target);
}

async function logout(page, target) {
  const controls = page.locator(target.logoutSelector);
  await controls.first().waitFor({ state: 'attached', timeout: 20_000 });
  let clicked = false;
  for (let index = 0; index < await controls.count(); index += 1) {
    const control = controls.nth(index);
    if (!(await control.isVisible())) continue;
    await control.click();
    clicked = true;
    break;
  }
  if (!clicked) throw new Error(`visible app logout control not found: ${target.logoutSelector}`);
  await waitForLogin(page, target.origin);
  return target.logoutSelector;
}

async function validAuthCookie(context) {
  const cookies = await context.cookies();
  return cookies.some((cookie) => cookie.name === 'auth-token' && cookie.value.length > 0);
}

async function runTarget(browser, target, credentials) {
  const targetDir = join(OUTPUT_ROOT, target.id);
  await mkdir(targetDir, { recursive: true, mode: 0o700 });
  const context = await browser.newContext({
    ignoreHTTPSErrors: false,
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  const mainFrameUrls = [];
  const documentResponses = [];
  const screenshots = [];
  const cycles = [];

  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame() && /^https?:/.test(frame.url())) {
      mainFrameUrls.push(sanitizedUrl(frame.url()));
    }
  });
  page.on('response', (response) => {
    if (response.request().resourceType() === 'document') {
      documentResponses.push({ status: response.status(), url: sanitizedUrl(response.url()) });
    }
  });

  try {
    for (let cycle = 1; cycle <= 2; cycle += 1) {
      await context.clearCookies();
      const cycleStart = documentResponses.length;
      await page.goto(`${target.origin}/`, { waitUntil: 'domcontentloaded', timeout: 45_000 });
      await waitForLogin(page, target.origin);
      screenshots.push(await screenshot(page, targetDir, cycle, '01', 'access'));

      if (page.url() !== `${target.origin}/login`) {
        throw new Error(`entry did not preserve app-local clean login: ${sanitizedUrl(page.url())}`);
      }
      screenshots.push(await screenshot(page, targetDir, cycle, '02', 'login'));

      await login(page, target, credentials);
      await assertAuthenticated(page, target);
      if (!(await validAuthCookie(context))) throw new Error('auth-token missing after login');
      screenshots.push(await screenshot(page, targetDir, cycle, '03', 'authenticated'));

      const logoutControl = await logout(page, target);
      if (await validAuthCookie(context)) throw new Error('auth-token remains after logout');
      screenshots.push(await screenshot(page, targetDir, cycle, '04', 'logged-out'));
      await page.waitForTimeout(CYCLE_COOLDOWN_MS);

      const cycleDocuments = documentResponses.slice(cycleStart);
      const foreignVisibleUrl = mainFrameUrls.find((url) => new URL(url).origin !== target.origin);
      if (foreignVisibleUrl) throw new Error(`foreign visible origin observed: ${foreignVisibleUrl}`);

      cycles.push({
        cycle,
        status: 'PASS',
        entryUrl: `${target.origin}/`,
        loginUrl: `${target.origin}/login`,
        authenticatedUrl: screenshots.at(-2).url,
        logoutUrl: screenshots.at(-1).url,
        authCookieIssued: true,
        authCookieCleared: true,
        logoutInteraction: 'visible-app-control',
        logoutControl,
        controlPlaneVisible: false,
        documentResponses: cycleDocuments,
      });
    }

    return {
      id: target.id,
      origin: target.origin,
      status: 'PASS',
      cycles,
      screenshots,
      mainFrameUrls,
    };
  } catch (error) {
    const failure = await screenshot(page, targetDir, cycles.length + 1, '99', 'failure').catch(() => null);
    return {
      id: target.id,
      origin: target.origin,
      status: 'FAIL',
      cycles,
      screenshots,
      mainFrameUrls,
      failure,
      error: scrub(error instanceof Error ? error.message : error, credentials),
    };
  } finally {
    await context.close();
  }
}

async function main() {
  await mkdir(OUTPUT_ROOT, { recursive: true, mode: 0o700 });
  const credentials = vaultCredentials();
  const browser = await chromium.launch({
    executablePath: CHROMIUM,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  let sites;
  try {
    sites = [];
    for (const [index, target] of targets.entries()) {
      sites.push(await runTarget(browser, target, credentials));
      if (index < targets.length - 1) await new Promise((resolve) => setTimeout(resolve, SITE_COOLDOWN_MS));
    }
  } finally {
    await browser.close();
  }

  const screenshotCount = sites.reduce((sum, site) => sum + site.screenshots.length, 0);
  const cycleCount = sites.reduce((sum, site) => sum + site.cycles.length, 0);
  const finalVerdict = lifecycleVerdict({
    scope: evidenceScope.scope,
    sites,
    cycleCount,
    screenshotCount,
  });
  const report = {
    schemaVersion: 2,
    generatedAt: new Date().toISOString(),
    finalVerdict,
    runner: 'playwright-headless',
    evidenceScope: evidenceScope.scope,
    selectedTargetIds: evidenceScope.selectedIds,
    requiredFleetTargetIds: FULL_LIFECYCLE_TARGET_IDS,
    completeFleetEvidence: evidenceScope.scope === 'full' && finalVerdict === 'PASS',
    proofScope: {
      hostLocalLifecycle: true,
      centralOidcFlow: false,
    },
    sites,
    totals: { sites: sites.length, cycles: cycleCount, screenshots: screenshotCount },
    secretsRecorded: false,
  };
  const reportPath = join(OUTPUT_ROOT, 'report.json');
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, { mode: 0o600 });
  await chmod(reportPath, 0o600);
  console.log(JSON.stringify({
    finalVerdict,
    reportPath,
    totals: report.totals,
    sites: sites.map(({ id, status, cycles: siteCycles, error }) => ({ id, status, cycles: siteCycles.length, error })),
  }, null, 2));
  if (finalVerdict === 'FAIL') process.exit(1);
}

await main();
