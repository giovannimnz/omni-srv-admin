import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCliArgs, validateSafeTargetRoot, SecurityJailViolationError } from '../src/core.mjs';

test('Wave 1: CLI parseArgs defaults and safety', () => {
  const defaults = parseCliArgs(['prune']);
  assert.equal(defaults.command, 'prune');
  assert.equal(defaults.dryRun, true, 'dryRun must be default true for safety');
  assert.equal(defaults.json, false);
  assert.equal(defaults.force, false);
  assert.equal(defaults.target, 'local');

  const withFlags = parseCliArgs(['prune', '--apply', '--json', '--target=srv2']);
  assert.equal(withFlags.command, 'prune');
  assert.equal(withFlags.dryRun, false, '--apply disables dryRun');
  assert.equal(withFlags.json, true);
  assert.equal(withFlags.target, 'srv2');
});

test('Wave 1: Path jailer blocks dangerous and forbidden system roots', () => {
  const forbidden = ['/', '/home', '/var', '/etc', '/usr', '/home/ubuntu'];
  for (const root of forbidden) {
    assert.throws(() => validateSafeTargetRoot(root), SecurityJailViolationError);
  }

  // Safe path must be an allowed workspace or explicit subfolder
  const safe = '/home/ubuntu/GitHub/Atius-Capital/ats';
  assert.equal(validateSafeTargetRoot(safe), safe);
});
