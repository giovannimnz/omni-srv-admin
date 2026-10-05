import path from 'node:path';

export class SecurityJailViolationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'SecurityJailViolationError';
  }
}

const FORBIDDEN_ROOTS = new Set(['/', '/home', '/var', '/etc', '/usr', '/home/ubuntu', '~']);

export function parseCliArgs(args = process.argv.slice(2)) {
  const result = {
    command: args[0] || 'help',
    subcommand: args[1] && !args[1].startsWith('-') ? args[1] : null,
    dryRun: true,
    json: false,
    force: false,
    target: 'local',
    options: {}
  };

  for (const arg of args) {
    if (arg === '--apply' || arg === '--execute' || arg === '-e') {
      result.dryRun = false;
    } else if (arg === '--dry-run') {
      result.dryRun = true;
    } else if (arg === '--json') {
      result.json = true;
    } else if (arg === '--force' || arg === '-f') {
      result.force = true;
    } else if (arg.startsWith('--target=')) {
      result.target = arg.split('=')[1];
    }
  }

  return result;
}

export function validateSafeTargetRoot(targetPath) {
  const resolved = path.resolve(targetPath);
  if (FORBIDDEN_ROOTS.has(resolved) || resolved === '/' || resolved === '/home/ubuntu') {
    throw new SecurityJailViolationError(`Target root '${resolved}' is a forbidden system root.`);
  }
  return resolved;
}
