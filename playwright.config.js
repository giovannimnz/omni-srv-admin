// @ts-check
const { defineConfig, devices } = require('@playwright/test');

const fs = require('fs');
let chromiumPath = process.env.PLAYWRIGHT_CHROMIUM_PATH;
if (!chromiumPath) {
  for (const p of ['/usr/local/bin/google-chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser']) {
    if (fs.existsSync(p)) {
      chromiumPath = p;
      break;
    }
  }
}

module.exports = defineConfig({
  testDir: './tests/playwright',
  timeout: 45000,
  expect: {
    timeout: 15000,
  },
  fullyParallel: false,
  workers: 1, // CPU Guardrail <20%
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    headless: true,
    ignoreHTTPSErrors: true,
    screenshot: 'on',
    video: 'off',
    viewport: { width: 1280, height: 720 },
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          executablePath: chromiumPath,
          args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
        },
      },
    },
  ],
});
