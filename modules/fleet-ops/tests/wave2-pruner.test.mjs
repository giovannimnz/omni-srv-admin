import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { runPruneScan } from '../src/pruner.mjs';

function setupSandbox() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'atius-ops-pruner-test-'));
  
  // Active app folder (must be preserved)
  const activeApp = path.join(tmp, 'app', '.next');
  fs.mkdirSync(activeApp, { recursive: true });
  fs.writeFileSync(path.join(activeApp, 'BUILD_ID'), 'build-123');

  // Stale backup folder (must be pruned)
  const staleBackup = path.join(tmp, 'app', '.next.backup-20260715');
  fs.mkdirSync(staleBackup, { recursive: true });
  fs.writeFileSync(path.join(staleBackup, 'old.js'), 'console.log("old");');

  // Browser profile with sensitive Cookies and purgeable Cache_Data
  const profileDir = path.join(tmp, 'browser-profile', 'Default');
  const cacheDataDir = path.join(profileDir, 'Cache', 'Cache_Data');
  fs.mkdirSync(cacheDataDir, { recursive: true });
  fs.writeFileSync(path.join(cacheDataDir, 'f_000001'), 'cache-binary-data');

  // SENSITIVE COOKIES - MUST NEVER BE DELETED
  fs.writeFileSync(path.join(profileDir, 'Cookies'), 'LIVE_AUTH_COOKIES_DO_NOT_DELETE');

  // Stale log file (16 days old)
  const staleLog = path.join(tmp, 'stale-16d.log');
  fs.writeFileSync(staleLog, 'old log content');
  const sixteenDaysAgo = new Date(Date.now() - 16 * 24 * 60 * 60 * 1000);
  fs.utimesSync(staleLog, sixteenDaysAgo, sixteenDaysAgo);

  // Recent log file (2 days old - must be preserved)
  const recentLog = path.join(tmp, 'recent-2d.log');
  fs.writeFileSync(recentLog, 'recent log content');

  return { tmp, activeApp, staleBackup, cacheDataDir, profileDir, staleLog, recentLog };
}

test('Wave 2: Pruner dry-run scans candidates without deleting', async () => {
  const sandbox = setupSandbox();
  try {
    const result = await runPruneScan({
      targetRoot: sandbox.tmp,
      dryRun: true,
      logRetentionDays: 14
    });

    assert.ok(result.candidates.length >= 3, 'Found candidates for backup, cache and stale log');
    assert.ok(result.totalBytes > 0, 'Calculated total bytes');
    
    // In dry-run, all files must still exist
    assert.ok(fs.existsSync(sandbox.staleBackup));
    assert.ok(fs.existsSync(sandbox.staleLog));
    assert.ok(fs.existsSync(path.join(sandbox.cacheDataDir, 'f_000001')));
    assert.ok(fs.existsSync(path.join(sandbox.profileDir, 'Cookies')));
    assert.ok(fs.existsSync(sandbox.activeApp));
  } finally {
    fs.rmSync(sandbox.tmp, { recursive: true, force: true });
  }
});

test('Wave 2: Pruner apply deletes eligible items and strictly protects inviolable files', async () => {
  const sandbox = setupSandbox();
  try {
    const result = await runPruneScan({
      targetRoot: sandbox.tmp,
      dryRun: false,
      logRetentionDays: 14
    });

    assert.ok(result.reclaimedBytes > 0, 'Reclaimed bytes reported');
    
    // Eligible items deleted
    assert.ok(!fs.existsSync(sandbox.staleBackup), '.next.backup must be deleted');
    assert.ok(!fs.existsSync(sandbox.staleLog), 'stale log >14d must be deleted');
    assert.ok(!fs.existsSync(path.join(sandbox.cacheDataDir, 'f_000001')), 'Cache_Data item deleted');

    // INVIOLABLE ITEMS PRESERVED
    assert.ok(fs.existsSync(path.join(sandbox.profileDir, 'Cookies')), 'Cookies MUST BE PRESERVED');
    assert.ok(fs.existsSync(sandbox.activeApp), 'Active .next MUST BE PRESERVED');
    assert.ok(fs.existsSync(sandbox.recentLog), 'Recent log (<14d) MUST BE PRESERVED');
  } finally {
    fs.rmSync(sandbox.tmp, { recursive: true, force: true });
  }
});
