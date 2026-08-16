#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const require = createRequire('/home/ubuntu/GitHub/vpn-atius/web/frontend/package.json');
const { chromium } = require('playwright');

const OUT = process.argv[2] || `/tmp/atius-login-ui-review-${new Date().toISOString().replace(/[:.]/g, '-')}`;
const CHROMIUM = process.env.E2E_CHROMIUM || '/usr/bin/chromium';
const viewport = { width: 1440, height: 900 };
const hosts = [
  { id: 'sso-reference', url: 'https://sso.atius.com.br/login', role: 'reference' },
  { id: 'grafana', url: 'https://grafana.atius.com.br/login', role: 'target' },
  { id: 'portainer', url: 'https://portainer.atius.com.br/login', role: 'target' },
  { id: 'docker', url: 'https://docker.atius.com.br/login', role: 'target' },
  { id: 'vpn', url: 'https://vpn.atius.com.br/login', role: 'target' },
  { id: 'adguard', url: 'https://adguard.atius.com.br/login', role: 'target' },
];

const selectors = [
  { key: 'body', selector: 'body' },
  { key: 'card', selector: 'main.card, .card' },
  { key: 'brand', selector: '.brand' },
  { key: 'brandMark', selector: '.brand-mark' },
  { key: 'brandName', selector: '.brand-name' },
  { key: 'dest', selector: '.dest' },
  { key: 'destSmall', selector: '.dest small' },
  { key: 'destRow', selector: '.dest-row' },
  { key: 'destRowSpan', selector: '.dest-row span' },
  { key: 'shield', selector: '.shield' },
  { key: 'form', selector: 'form' },
  { key: 'emailField', selector: '.field:has(input[name="email"]), .field:has(input[type="email"]), .field:has(input[placeholder*="email" i])' },
  { key: 'emailLabel', selector: 'label[for="email"], label:has(+ .control input[name="email"]), label:has(+ .control input[type="email"]), label:has(+ .control input[placeholder*="email" i])' },
  { key: 'emailControl', selector: '.control:has(input[name="email"]), .control:has(input[type="email"]), .control:has(input[placeholder*="email" i])' },
  { key: 'emailInput', selector: 'input[name="email"], input[type="email"], input[placeholder*="email" i]' },
  { key: 'passwordField', selector: '.field:has(input[name="password"]), .field:has(input[type="password"]), .field:has(input[placeholder*="senha" i])' },
  { key: 'passwordLabel', selector: 'label[for="password"], label:has(+ .control input[name="password"]), label:has(+ .control input[type="password"]), label:has(+ .control input[placeholder*="senha" i])' },
  { key: 'passwordControl', selector: '.control:has(input[name="password"]), .control:has(input[type="password"]), .control:has(input[placeholder*="senha" i])' },
  { key: 'passwordInput', selector: 'input[name="password"], input[type="password"], input[placeholder*="senha" i]' },
  { key: 'button', selector: 'button[type="submit"], button' },
  { key: 'iconLeftEmail', selector: '.field:has(input[name="email"]) .icon-left, .field:has(input[type="email"]) .icon-left, .field:has(input[placeholder*="email" i]) .icon-left' },
  { key: 'iconLeftPassword', selector: '.field:has(input[name="password"]) .icon-left, .field:has(input[type="password"]) .icon-left, .field:has(input[placeholder*="senha" i]) .icon-left' },
  { key: 'iconRightPassword', selector: '.field:has(input[name="password"]) .icon-right, .field:has(input[type="password"]) .icon-right, .field:has(input[placeholder*="senha" i]) .icon-right' },
];

const cssProps = [
  'display','position','boxSizing','width','height','minHeight','maxWidth',
  'fontFamily','fontSize','fontWeight','fontStyle','lineHeight','letterSpacing','textTransform','textAlign',
  'color','backgroundColor','backgroundImage','borderTopWidth','borderTopStyle','borderTopColor',
  'borderRightWidth','borderRightStyle','borderRightColor','borderBottomWidth','borderBottomStyle','borderBottomColor','borderLeftWidth','borderLeftStyle','borderLeftColor',
  'borderRadius','borderTopLeftRadius','borderTopRightRadius','borderBottomRightRadius','borderBottomLeftRadius',
  'paddingTop','paddingRight','paddingBottom','paddingLeft','marginTop','marginRight','marginBottom','marginLeft',
  'gap','rowGap','columnGap','alignItems','justifyContent','flexDirection','flex','boxShadow','opacity',
  'outlineWidth','outlineStyle','outlineColor','transform'
];

function hashBuffer(buf) { return createHash('sha256').update(buf).digest('hex'); }

async function capture(page, host) {
  const consoleMessages = [];
  const pageErrors = [];
  const responses = [];
  page.on('console', msg => consoleMessages.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', err => pageErrors.push(String(err?.stack || err?.message || err)));
  page.on('response', resp => {
    const status = resp.status();
    const req = resp.request();
    if (req.resourceType() === 'document' || status >= 400) {
      responses.push({ status, url: resp.url(), resourceType: req.resourceType() });
    }
  });

  const started = Date.now();
  const result = { ...host, requestedUrl: host.url, startedAt: new Date(started).toISOString() };
  try {
    const response = await page.goto(host.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    result.initialStatus = response?.status() || null;
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(1000);
    await page.locator('main.card, .card, body').first().waitFor({ state: 'visible', timeout: 15000 });
  } catch (e) {
    result.navigationError = String(e?.stack || e?.message || e);
  }
  result.finalUrl = page.url();
  result.title = await page.title().catch(e => `TITLE_ERROR ${e.message}`);

  const screenshotPath = join(OUT, `${host.id}.png`);
  const image = await page.screenshot({ path: screenshotPath, fullPage: false, timeout: 30000 });
  result.screenshot = { path: screenshotPath, sha256: hashBuffer(image), bytes: image.length, viewport };

  result.dom = await page.evaluate(({ selectors, cssProps }) => {
    function styleFor(el) {
      const cs = getComputedStyle(el);
      const out = {};
      for (const prop of cssProps) out[prop] = cs[prop] || '';
      return out;
    }
    function rectFor(el) {
      const r = el.getBoundingClientRect();
      return {
        x: Number(r.x.toFixed(3)), y: Number(r.y.toFixed(3)),
        width: Number(r.width.toFixed(3)), height: Number(r.height.toFixed(3)),
        top: Number(r.top.toFixed(3)), right: Number(r.right.toFixed(3)),
        bottom: Number(r.bottom.toFixed(3)), left: Number(r.left.toFixed(3)),
      };
    }
    function attrsFor(el) {
      const attrs = {};
      for (const attr of Array.from(el.attributes || [])) {
        if (['class','id','for','name','type','placeholder','action','method','aria-label','role','value'].includes(attr.name)) attrs[attr.name] = attr.value;
      }
      return attrs;
    }
    const nodes = {};
    for (const { key, selector } of selectors) {
      const el = document.querySelector(selector);
      nodes[key] = el ? {
        selector,
        tagName: el.tagName.toLowerCase(),
        attributes: attrsFor(el),
        text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(),
        rect: rectFor(el),
        style: styleFor(el),
        html: (el.outerHTML || '').slice(0, 700),
      } : { selector, missing: true };
    }
    const labels = Array.from(document.querySelectorAll('label')).map((el, index) => ({ index, text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(), attributes: attrsFor(el), rect: rectFor(el), style: styleFor(el), html: (el.outerHTML || '').slice(0, 400) }));
    const inputs = Array.from(document.querySelectorAll('input')).map((el, index) => ({ index, attributes: attrsFor(el), rect: rectFor(el), style: styleFor(el), html: (el.outerHTML || '').slice(0, 400) }));
    const buttons = Array.from(document.querySelectorAll('button')).map((el, index) => ({ index, text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(), attributes: attrsFor(el), rect: rectFor(el), style: styleFor(el), html: (el.outerHTML || '').slice(0, 400) }));
    const sheets = Array.from(document.styleSheets).map((sheet) => {
      let rules = null;
      try { rules = sheet.cssRules ? Array.from(sheet.cssRules).slice(0, 120).map(r => r.cssText) : null; } catch {}
      return { href: sheet.href, ownerTag: sheet.ownerNode?.tagName?.toLowerCase() || '', ownerTextPrefix: sheet.ownerNode?.textContent?.slice(0, 100) || '', rules };
    });
    const rect = (key) => nodes[key] && !nodes[key].missing ? nodes[key].rect : null;
    const gaps = {};
    function gap(name, a, b) {
      if (rect(a) && rect(b)) gaps[name] = Number((rect(b).top - rect(a).bottom).toFixed(3));
    }
    gap('brandMark_to_brandName', 'brandMark', 'brandName');
    gap('brandName_to_dest', 'brandName', 'dest');
    gap('dest_to_emailField', 'dest', 'emailField');
    gap('emailLabel_to_emailInput', 'emailLabel', 'emailInput');
    gap('emailInput_to_passwordLabel', 'emailInput', 'passwordLabel');
    gap('passwordLabel_to_passwordInput', 'passwordLabel', 'passwordInput');
    gap('passwordInput_to_button', 'passwordInput', 'button');
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight, dpr: window.devicePixelRatio },
      url: location.href,
      documentElementClass: document.documentElement.className,
      bodyText: (document.body.innerText || document.body.textContent || '').replace(/\s+/g, ' ').trim(),
      nodes, labels, inputs, buttons, styleSheets: sheets, gaps,
      activeElement: document.activeElement ? document.activeElement.tagName.toLowerCase() : null,
    };
  }, { selectors, cssProps });

  result.consoleMessages = consoleMessages;
  result.pageErrors = pageErrors;
  result.responses = responses;
  result.durationMs = Date.now() - started;
  result.endedAt = new Date().toISOString();
  return result;
}

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: CHROMIUM, args: ['--no-sandbox', '--disable-gpu'] });
const all = [];
for (const host of hosts) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, ignoreHTTPSErrors: true, locale: 'pt-BR', timezoneId: 'America/Sao_Paulo' });
  const page = await context.newPage();
  const result = await capture(page, host);
  all.push(result);
  await context.close();
  await writeFile(join(OUT, `${host.id}.json`), JSON.stringify(result, null, 2));
  console.log(`${host.id}: ${result.initialStatus} ${result.finalUrl} -> ${result.screenshot.path}`);
}
await browser.close();
await writeFile(join(OUT, 'all-results.json'), JSON.stringify({ out: OUT, capturedAt: new Date().toISOString(), viewport, hosts: all }, null, 2));
console.log(`OUT=${OUT}`);
