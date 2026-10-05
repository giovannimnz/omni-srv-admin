import fs from 'node:fs';
import path from 'node:path';
import { validateSafeTargetRoot } from './core.mjs';

const INVIOLABLE_NAMES = new Set([
  'Cookies',
  'Cookies-journal',
  'Network/Cookies',
  'Local Storage',
  'IndexedDB',
  'Extension State',
  'Web Data',
  'Preferences',
  'BUILD_ID'
]);

function isCandidateDir(name, fullPath) {
  if (name.startsWith('.next.backup-') || name.startsWith('dist.bak') || name.startsWith('build.bak')) {
    return true;
  }
  if (name === 'Cache_Data' || name === 'Code Cache' || name === 'GPUCache') {
    return true;
  }
  return false;
}

function getDirSize(dirPath) {
  let size = 0;
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(dirPath, entry.name);
      if (entry.isDirectory()) {
        size += getDirSize(full);
      } else if (entry.isFile()) {
        size += fs.statSync(full).size;
      }
    }
  } catch {
    // ignore inaccessible files
  }
  return size;
}

export async function runPruneScan({ targetRoot, dryRun = true, logRetentionDays = 14 }) {
  const root = validateSafeTargetRoot(targetRoot);
  const candidates = [];
  const logCutoffMs = Date.now() - logRetentionDays * 24 * 60 * 60 * 1000;

  function scan(currentDir) {
    let entries = [];
    try {
      entries = fs.readdirSync(currentDir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);

      if (INVIOLABLE_NAMES.has(entry.name) || entry.name.startsWith('.env') || entry.name.endsWith('.sqlite')) {
        continue;
      }

      if (entry.isDirectory()) {
        if (isCandidateDir(entry.name, fullPath)) {
          const size = getDirSize(fullPath);
          candidates.push({ type: 'dir', path: fullPath, size });
          continue; // do not descend into directory slated for deletion
        } else {
          scan(fullPath);
        }
      } else if (entry.isFile()) {
        if (entry.name.endsWith('.log')) {
          try {
            const stat = fs.statSync(fullPath);
            if (stat.mtimeMs < logCutoffMs) {
              candidates.push({ type: 'file', path: fullPath, size: stat.size });
            }
          } catch {}
        }
      }
    }
  }

  scan(root);

  let totalBytes = candidates.reduce((acc, c) => acc + c.size, 0);
  let reclaimedBytes = 0;

  if (!dryRun) {
    for (const item of candidates) {
      try {
        if (item.type === 'dir') {
          fs.rmSync(item.path, { recursive: true, force: true });
        } else {
          fs.unlinkSync(item.path);
        }
        reclaimedBytes += item.size;
      } catch (err) {
        // preserve error tolerance
      }
    }
  }

  return { candidates, totalBytes, reclaimedBytes, dryRun };
}
