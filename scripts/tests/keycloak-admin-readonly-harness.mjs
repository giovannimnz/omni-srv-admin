#!/usr/bin/env node
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import {
  chmod,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  stat,
  writeFile,
} from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(TEST_DIR, '../..')
const LIVE_ADAPTER = path.join(REPO_ROOT, 'scripts/lib/keycloak-admin-readonly-live.sh')
const TRANSFORM = path.join(
  REPO_ROOT,
  'scripts/lib/keycloak-admin-readonly-exporter-transform.py',
)
const STATE_HELPER = path.join(
  REPO_ROOT,
  'scripts/lib/keycloak-admin-readonly-operation-state.py',
)

function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

function cleanEnvironment(root) {
  const env = Object.fromEntries(
    Object.entries(process.env).filter(([name]) => !name.startsWith('KARO_TEST_')),
  )
  return {
    ...env,
    KARO_TEST_CONTEXT: 'runner-v1',
    KARO_TEST_PARENT_PID: String(process.pid),
    KARO_TEST_ROOT: root,
  }
}

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    encoding: 'utf8',
    maxBuffer: 2 * 1024 * 1024,
    ...options,
  })
}

async function exporterScenario(root, env) {
  const exporter = path.join(root, 'atius-vault-export-env')
  const backup = path.join(root, 'exporter.backup')
  const original = '#!/usr/bin/env bash\nset -euo pipefail\nprintf "%s\\\\n" "existing-profile"\n'
  await writeFile(exporter, original, { mode: 0o700 })
  await chmod(exporter, 0o700)
  const common = [
    '--file',
    exporter,
    '--backup',
    backup,
    '--expected-before-sha256',
    sha256(original),
    '--sandbox',
  ]
  const preview = run('python3', [TRANSFORM, 'preview', ...common], { env })
  if (preview.status !== 0) throw new Error(`exporter preview failed: ${preview.stderr}`)
  const installedSha = JSON.parse(preview.stdout).installedSha256
  const withInstalled = [...common, '--expected-installed-sha256', installedSha]
  for (const mode of ['apply', 'verify', 'restore', 'reapply', 'verify']) {
    const result = run('python3', [TRANSFORM, mode, ...withInstalled], { env })
    if (result.status !== 0) throw new Error(`exporter ${mode} failed: ${result.stderr}`)
  }
  return {
    scenario: 'exporter',
    backupMode: (await stat(backup)).mode & 0o777,
    installedSha,
  }
}

async function journalScenario(root, env) {
  const operations = path.join(root, 'operations')
  const operationId = 'readonly-20260724-journal'
  const operationDirectory = path.join(operations, operationId)
  await mkdir(operationDirectory, { recursive: true, mode: 0o700 })
  await chmod(operations, 0o700)
  await chmod(operationDirectory, 0o700)
  const scopedEnv = { ...env, KARO_TEST_OPERATION_ROOT: operations }
  const payload = JSON.stringify({ operationId, status: 'armed', secretsRecorded: false })
  const args = [
    STATE_HELPER,
    'event',
    '--operation-id',
    operationId,
    '--event-file',
    '001-client-armed.json',
  ]
  const first = run('python3', args, { input: payload, env: scopedEnv })
  const second = run('python3', args, { input: payload, env: scopedEnv })
  return {
    scenario: 'journal',
    firstStatus: first.status,
    secondStatus: second.status,
  }
}

async function failureScenario(root, env, boundary) {
  const operations = path.join(root, 'operations')
  const operationId = `readonly-${boundary.replaceAll('-', '')}-0001`
  const operationDirectory = path.join(operations, operationId)
  await mkdir(operationDirectory, { recursive: true, mode: 0o700 })
  await chmod(operations, 0o700)
  await chmod(operationDirectory, 0o700)
  const resultPath = path.join(root, 'result.json')
  const result = run(
    'bash',
    [
      LIVE_ADAPTER,
      '--mode',
      'test-transaction',
      '--operation-id',
      operationId,
      '--client-uuid',
      '11111111-1111-4111-8111-111111111111',
      '--state-dir',
      operationDirectory,
      '--expected-exporter-sha256',
      '1'.repeat(64),
      '--expected-put-helper-sha256',
      '2'.repeat(64),
      '--result',
      resultPath,
    ],
    {
      env: {
        ...env,
        KARO_TEST_OPERATION_ROOT: operations,
        KARO_FAIL_AFTER: boundary,
      },
    },
  )
  const order = (await readFile(path.join(root, 'rollback-order.log'), 'utf8'))
    .trim()
    .split('\n')
  const failure = JSON.parse(await readFile(resultPath, 'utf8'))
  return {
    scenario: 'failure',
    status: result.status,
    order,
    rollbackSucceeded: failure.automaticRollback.succeeded,
  }
}

async function main() {
  const [scenario, detail] = process.argv.slice(2)
  if (!['exporter', 'journal', 'failure'].includes(scenario)) {
    throw new Error('usage: keycloak-admin-readonly-harness.mjs exporter|journal|failure [boundary]')
  }
  if (scenario === 'failure' && !detail) throw new Error('failure scenario requires a boundary')
  const root = await mkdtemp(path.join(os.tmpdir(), 'karo-harness-'))
  await chmod(root, 0o700)
  try {
    const env = cleanEnvironment(root)
    const result =
      scenario === 'exporter'
        ? await exporterScenario(root, env)
        : scenario === 'journal'
          ? await journalScenario(root, env)
          : await failureScenario(root, env, detail)
    process.stdout.write(`${JSON.stringify(result)}\n`)
  } finally {
    await rm(root, { recursive: true, force: true })
  }
}

main().catch((error) => {
  process.stderr.write(`harness failed: ${error.message}\n`)
  process.exitCode = 1
})
