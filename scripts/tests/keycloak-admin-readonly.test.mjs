import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { chmod, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  CANDIDATE_STEP_IDS,
  CONTRACT,
  atomicWritePrivateJson,
  digestObject,
  validateApproval,
  validateCandidate,
} from '../lib/keycloak-admin-readonly-contract.mjs'

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(TEST_DIR, '../..')
const TRANSFORM = path.join(REPO_ROOT, 'scripts/lib/keycloak-admin-readonly-exporter-transform.py')
const SECRET_PIPE = path.join(REPO_ROOT, 'scripts/lib/keycloak-admin-readonly-secret-pipe.py')
const LIVE_ADAPTER = path.join(REPO_ROOT, 'scripts/lib/keycloak-admin-readonly-live.sh')
const RUNNER = path.join(REPO_ROOT, 'scripts/provision-keycloak-admin-readonly.mjs')
const APPROVAL_PRODUCER = path.join(REPO_ROOT, 'scripts/create-keycloak-admin-readonly-approval.mjs')

function minimalCandidate() {
  return {
    schemaVersion: '1',
    mode: 'candidate',
    finalVerdict: 'GO',
    liveProvisioning: false,
    humanApprovalRequired: true,
    recoveryAdminUsed: false,
    expectedStepIds: [...CANDIDATE_STEP_IDS],
    steps: CANDIDATE_STEP_IDS.map((id) => ({ id, status: 'PASS' })),
    contract: { profile: CONTRACT.profile, vaultPath: CONTRACT.vaultPath },
    candidate: {
      digest: 'a'.repeat(64),
      sourceDigest: 'b'.repeat(64),
      preimageDigest: 'c'.repeat(64),
      targetScopeDigest: 'd'.repeat(64),
    },
    secretsRecorded: false,
  }
}

test('contract freezes exact profile, field, client, flow, and role sets', () => {
  assert.equal(CONTRACT.profile, 'keycloak-admin-readonly')
  assert.equal(CONTRACT.vaultPath, 'kv/atius/keycloak/admin-readonly')
  assert.deepEqual(CONTRACT.vaultFields, [
    'KEYCLOAK_BASE_URL',
    'KEYCLOAK_READONLY_CLIENT_ID',
    'KEYCLOAK_READONLY_CLIENT_SECRET',
    'KEYCLOAK_REALM',
  ])
  assert.deepEqual(CONTRACT.client, {
    protocol: 'openid-connect',
    enabled: true,
    publicClient: false,
    standardFlowEnabled: false,
    directAccessGrantsEnabled: false,
    implicitFlowEnabled: false,
    serviceAccountsEnabled: true,
    fullScopeAllowed: false,
    bearerOnly: false,
    redirectUris: [],
    webOrigins: [],
  })
  assert.deepEqual(CONTRACT.roles, [
    'realm-management/query-clients',
    'realm-management/view-clients',
  ])
})

test('approval validation is digest-bound and TTL-bounded', () => {
  const candidate = minimalCandidate()
  validateCandidate(candidate)
  const now = new Date('2026-07-24T03:00:00Z')
  const approval = {
    schemaVersion: '1',
    operationId: 'readonly-20260724-0001',
    operationMode: 'provision-with-rollback-reapply',
    candidateDigest: candidate.candidate.digest,
    sourceDigest: candidate.candidate.sourceDigest,
    preimageDigest: candidate.candidate.preimageDigest,
    targetScopeDigest: candidate.candidate.targetScopeDigest,
    approvedForKeycloakProvision: true,
    profile: CONTRACT.profile,
    vaultPath: CONTRACT.vaultPath,
    realm: CONTRACT.realm,
    clientId: CONTRACT.clientId,
    issuedAt: '2026-07-24T03:00:00Z',
    expiresAt: '2026-07-24T03:15:00Z',
  }
  validateApproval(approval, candidate, now)
  assert.throws(
    () => validateApproval({ ...approval, expiresAt: '2026-07-24T03:15:01Z' }, candidate, now),
    /900 seconds/,
  )
  assert.throws(
    () => validateApproval({ ...approval, targetScopeDigest: 'e'.repeat(64) }, candidate, now),
    /exact candidate/,
  )
})

test('private O_EXCL writer makes operation artifacts one-time', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'karo-exclusive-'))
  const target = path.join(directory, 'operation.json')
  try {
    await atomicWritePrivateJson(target, { operationId: 'one' }, { exclusive: true })
    assert.equal((await stat(target)).mode & 0o777, 0o600)
    await assert.rejects(
      atomicWritePrivateJson(target, { operationId: 'two' }, { exclusive: true }),
      /EEXIST/,
    )
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('external producer writes 0600 once and cannot overwrite', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'karo-approval-'))
  const candidatePath = path.join(directory, 'candidate.json')
  const approvalPath = path.join(directory, 'approval.json')
  await writeFile(candidatePath, `${JSON.stringify(minimalCandidate())}\n`, { mode: 0o600 })
  const args = [
    APPROVAL_PRODUCER,
    '--candidate',
    candidatePath,
    '--output',
    approvalPath,
    '--operation-id',
    'readonly-20260724-approval',
    '--approved-by',
    'sandbox-operator',
    '--ttl-seconds',
    '900',
  ]
  try {
    const first = spawnSync(process.execPath, args, { encoding: 'utf8' })
    assert.equal(first.status, 0, first.stderr)
    assert.equal((await stat(approvalPath)).mode & 0o777, 0o600)
    const second = spawnSync(process.execPath, args, { encoding: 'utf8' })
    assert.notEqual(second.status, 0)
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('exporter transform applies, verifies, restores, and reapplies exact bytes in sandbox', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'karo-transform-'))
  const exporter = path.join(directory, 'atius-vault-export-env')
  const backup = path.join(directory, 'exporter.backup')
  const original = '#!/usr/bin/env bash\nset -euo pipefail\nprintf \"%s\\\\n\" \"existing-profile\"\n'
  await writeFile(exporter, original)
  await chmod(exporter, 0o700)
  const beforeSha = digestObject(Buffer.from(original).toString('base64'))
  const crypto = await import('node:crypto')
  const exactBeforeSha = crypto.createHash('sha256').update(original).digest('hex')
  assert.notEqual(beforeSha, exactBeforeSha)
  const common = [
    TRANSFORM,
    '--file',
    exporter,
    '--backup',
    backup,
    '--expected-before-sha256',
    exactBeforeSha,
    '--sandbox',
  ]
  const env = { ...process.env, KARO_TEST_CONTEXT: 'candidate' }
  try {
    const apply = spawnSync('python3', [common[0], 'apply', ...common.slice(1)], {
      encoding: 'utf8',
      env,
    })
    assert.equal(apply.status, 0, apply.stderr)
    const applied = JSON.parse(apply.stdout)
    assert.equal(applied.markerCount, 1)
    const verify = spawnSync(
      'python3',
      [common[0], 'verify', ...common.slice(1), '--expected-installed-sha256', applied.installedSha256],
      { encoding: 'utf8', env },
    )
    assert.equal(verify.status, 0, verify.stderr)
    const restore = spawnSync(
      'python3',
      [common[0], 'restore', ...common.slice(1), '--expected-installed-sha256', applied.installedSha256],
      { encoding: 'utf8', env },
    )
    assert.equal(restore.status, 0, restore.stderr)
    assert.equal(await readFile(exporter, 'utf8'), original)
    const reapply = spawnSync('python3', [common[0], 'reapply', ...common.slice(1)], {
      encoding: 'utf8',
      env,
    })
    assert.equal(reapply.status, 0, reapply.stderr)
    assert.equal(JSON.parse(reapply.stdout).installedSha256, applied.installedSha256)
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('hydration verifier emits only field names and never the piped secret', () => {
  const input = [
    "export KEYCLOAK_BASE_URL='http://127.0.0.1:8180'",
    "export KEYCLOAK_REALM='atius'",
    "export KEYCLOAK_READONLY_CLIENT_ID='keycloak-admin-readonly'",
    "export KEYCLOAK_READONLY_CLIENT_SECRET='test-secret'",
    '',
  ].join('\n')
  const result = spawnSync('python3', [SECRET_PIPE, 'verify-exports'], {
    input,
    encoding: 'utf8',
  })
  assert.equal(result.status, 0, result.stderr)
  assert.doesNotMatch(result.stdout, /test-secret/)
  assert.deepEqual(JSON.parse(result.stdout).fieldNames, CONTRACT.vaultFields)
})

test('live adapter ordering is fail-closed and secret-safe by static contract', async () => {
  const source = await readFile(LIVE_ADAPTER, 'utf8')
  const orderedTokens = [
    'assert_recovery_metadata',
    'authenticate_recovery_once',
    'assert_client_absent',
    'assert_vault_metadata_absent',
    'capture_remote_preimage',
    'create_client_and_roles',
    'write_vault_secret',
    'apply_exporter_transform apply',
    'assert_profile_hydration_and_inventory',
    'rollback_owned_resources',
    'assert_rollback_readback',
    'apply_exporter_transform reapply',
  ]
  let offset = source.indexOf('CURRENT_STEP="recovery-metadata-validate"')
  assert.ok(offset >= 0)
  for (const token of orderedTokens) {
    const next = source.indexOf(token, offset)
    assert.ok(next >= offset, `missing or out-of-order token: ${token}`)
    offset = next + token.length
  }
  assert.match(source, /trap on_error ERR/)
  assert.match(source, /rollback_owned_resources/)
  assert.match(source, /source "\$\{RECOVERY_ENV\}"/)
  assert.match(source, /export KC_CLI_PASSWORD=/)
  assert.doesNotMatch(source, /--password/)
  assert.doesNotMatch(source, /--secret/)
  assert.match(source, /client-secret"[\s\S]*\| "\$\{SECRET_PIPE\}"/)
  assert.match(source, /kv delete -versions=/)
  assert.doesNotMatch(source, /metadata delete/)
})

test('runner cannot create or import its separate approval producer', async () => {
  const source = await readFile(RUNNER, 'utf8')
  assert.doesNotMatch(source, /create-keycloak-admin-readonly-approval/)
  assert.doesNotMatch(source, /from\s+['"].*approval/)
})

test('shell and Python helpers pass syntax checks', () => {
  const shell = spawnSync('bash', ['-n', LIVE_ADAPTER], { encoding: 'utf8' })
  assert.equal(shell.status, 0, shell.stderr)
  for (const script of [TRANSFORM, SECRET_PIPE]) {
    const python = spawnSync('python3', ['-m', 'py_compile', script], {
      encoding: 'utf8',
      env: { ...process.env, PYTHONPYCACHEPREFIX: path.join(os.tmpdir(), 'karo-pycache') },
    })
    assert.equal(python.status, 0, python.stderr)
  }
})
