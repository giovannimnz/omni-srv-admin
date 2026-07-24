import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import {
  chmod,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  stat,
  symlink,
  writeFile,
} from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  ARTIFACT_PATHS,
  CANDIDATE_STEP_IDS,
  CONTRACT,
  INTENDED_MUTATIONS,
  LIVE_STEP_IDS,
  OPERATION_MODE,
  SOURCE_FILES,
  atomicWritePrivateJson,
  buildTargetScope,
  canonicalJson,
  recomputeCandidateDigests,
  validateApproval,
  validateCandidate,
} from '../lib/keycloak-admin-readonly-contract.mjs'

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(TEST_DIR, '../..')
const TRANSFORM = path.join(REPO_ROOT, 'scripts/lib/keycloak-admin-readonly-exporter-transform.py')
const SECRET_PIPE = path.join(REPO_ROOT, 'scripts/lib/keycloak-admin-readonly-secret-pipe.py')
const STATE_HELPER = path.join(REPO_ROOT, 'scripts/lib/keycloak-admin-readonly-operation-state.py')
const LIVE_ADAPTER = path.join(REPO_ROOT, 'scripts/lib/keycloak-admin-readonly-live.sh')
const RUNNER = path.join(REPO_ROOT, 'scripts/provision-keycloak-admin-readonly.mjs')
const APPROVAL_PRODUCER = path.join(REPO_ROOT, 'scripts/create-keycloak-admin-readonly-approval.mjs')
const TEST_HARNESS = path.join(REPO_ROOT, 'scripts/tests/keycloak-admin-readonly-harness.mjs')

function topology(observedAt = '2026-07-24T03:00:00.000Z') {
  return {
    schemaVersion: '2',
    observedAt,
    observationClass: 'direct-current-metadata-no-secret',
    target: {
      host: 'atius-srv-1',
      runtime: 'native-systemd',
      baseUrl: CONTRACT.baseUrl,
      realm: CONTRACT.realm,
      keycloakVersion: '26.6.3',
    },
    recoveryEnv: {
      path: CONTRACT.recoveryEnvPath,
      exists: true,
      type: 'regular-file',
      mode: '600',
      owner: 'root',
      group: 'root',
      size: 92,
      fieldNames: [...CONTRACT.recoveryEnvFields],
      valuesRead: false,
      valuesRecorded: false,
    },
    exporter: {
      host: 'atius-srv-3',
      path: CONTRACT.exporterPath,
      mode: '700',
      owner: 'root',
      group: 'root',
      size: 3951,
      sha256: '1'.repeat(64),
      contentRead: false,
      contentRecorded: false,
    },
    vaultPutHelper: {
      host: 'atius-srv-3',
      path: CONTRACT.vaultPutHelperPath,
      mode: '700',
      owner: 'root',
      group: 'root',
      size: 755,
      sha256: '2'.repeat(64),
      contentRead: false,
      contentRecorded: false,
    },
    vaultPath: {
      path: CONTRACT.vaultPath,
      present: false,
      authenticatedMetadataRead: true,
      evidenceSource: 'direct-exact-vault-metadata-read',
      valuesRead: false,
    },
    keycloakClient: {
      clientId: CONTRACT.clientId,
      absenceStatus: 'UNKNOWN_AUTH',
      authenticatedRead: false,
    },
    secretsRecorded: false,
  }
}

function syntheticManifest() {
  return SOURCE_FILES.map((filePath, index) => ({
    path: filePath,
    sha256: index.toString(16).padStart(64, '0'),
  }))
}

function candidate({
  generatedAt = '2026-07-24T03:00:01.000Z',
  observedAt = '2026-07-24T03:00:00.000Z',
  ready = false,
  sourceManifest = syntheticManifest(),
} = {}) {
  const topo = topology(observedAt)
  const liveObservedAt = new Date(new Date(generatedAt).getTime() - 500).toISOString()
  const livePreflight = ready
    ? {
        schemaVersion: '2',
        mode: 'authenticated-read-only-preflight',
        observedAt: liveObservedAt,
        authenticated: true,
        client: { clientId: CONTRACT.clientId, absent: true },
        vault: {
          path: CONTRACT.vaultPath,
          absent: true,
          authenticatedMetadataRead: true,
        },
        exporter: {
          path: CONTRACT.exporterPath,
          sha256: topo.exporter.sha256,
          mode: '700',
          owner: 'root',
          group: 'root',
        },
        secretsRecorded: false,
      }
    : null
  const value = {
    schemaVersion: '2',
    mode: 'candidate',
    generatedAt,
    finalVerdict: 'GO',
    liveProvisioning: false,
    humanApprovalRequired: true,
    recoveryAdminUsed: false,
    approvalReady: ready,
    livePreflightStatus: ready ? 'READY' : 'BLOCKED_AUTH',
    livePreflight,
    expectedStepIds: [...CANDIDATE_STEP_IDS],
    liveStepIds: [...LIVE_STEP_IDS],
    steps: CANDIDATE_STEP_IDS.map((id) => ({ id, status: 'PASS' })),
    contract: CONTRACT,
    targetScope: JSON.parse(JSON.stringify(buildTargetScope())),
    intendedLiveMutations: JSON.parse(JSON.stringify(INTENDED_MUTATIONS)),
    candidate: {
      digest: '',
      sourceDigest: '',
      preimageDigest: '',
      targetScopeDigest: '',
      sourceCommit: 'f'.repeat(40),
      sourceManifest,
    },
    preimage: {
      topology: topo,
      recoveryMetadata: {
        path: CONTRACT.recoveryEnvPath,
        type: 'regular-file',
        mode: '600',
        uid: 0,
        gid: 0,
        size: 92,
      },
      keycloakClient: ready
        ? {
            clientId: CONTRACT.clientId,
            absenceStatus: 'ABSENT',
            authenticatedRead: true,
            observedAt: livePreflight.observedAt,
          }
        : {
            clientId: CONTRACT.clientId,
            absenceStatus: 'UNKNOWN_AUTH',
            authenticatedRead: false,
          },
      vaultPath: {
        path: CONTRACT.vaultPath,
        absenceStatus: 'ABSENT',
        authenticatedMetadataRead: true,
        evidenceSource: 'direct-exact-vault-metadata-read',
        observedAt,
      },
    },
    cpuContainment: { cpuMax: '80000 100000', cpuQuota: '80%', maxCpu: 0.8 },
    approval: {
      present: false,
      producerSeparateFromRunner: true,
      operationMode: OPERATION_MODE,
    },
    rollback: { order: ['exporter', 'vault', 'keycloak'] },
    noSecretEvidence: { secretsRecorded: false },
    secretsRecorded: false,
  }
  Object.assign(value.candidate, recomputeCandidateDigests(value))
  return value
}

function approvalFor(value, overrides = {}) {
  const producer = value.candidate.sourceManifest.find(
    (entry) => entry.path === 'scripts/create-keycloak-admin-readonly-approval.mjs',
  )
  return {
    schemaVersion: '2',
    operationId: 'readonly-20260724-0001',
    operationMode: OPERATION_MODE,
    candidateDigest: value.candidate.digest,
    sourceDigest: value.candidate.sourceDigest,
    preimageDigest: value.candidate.preimageDigest,
    targetScopeDigest: value.candidate.targetScopeDigest,
    approvedForKeycloakProvision: true,
    profile: CONTRACT.profile,
    vaultPath: CONTRACT.vaultPath,
    realm: CONTRACT.realm,
    clientId: CONTRACT.clientId,
    issuedAt: '2026-07-24T03:00:01.000Z',
    expiresAt: '2026-07-24T03:15:01.000Z',
    approvedBy: 'sandbox-operator',
    producerPath:
      '/home/ubuntu/GitHub/omni-srv-admin/scripts/create-keycloak-admin-readonly-approval.mjs',
    producerSha256: producer.sha256,
    ...overrides,
  }
}

test('contract freezes exact client projection, roles, operation, source, and paths', () => {
  assert.equal(CONTRACT.schemaVersion, '2')
  assert.deepEqual(CONTRACT.client.attributes, {})
  assert.equal(CONTRACT.client.clientId, CONTRACT.clientId)
  assert.deepEqual(CONTRACT.roles, [
    'realm-management/query-clients',
    'realm-management/view-clients',
  ])
  assert.equal(OPERATION_MODE, 'provision-and-drill')
  assert.ok(SOURCE_FILES.includes('scripts/create-keycloak-admin-readonly-approval.mjs'))
  assert.ok(ARTIFACT_PATHS.liveReport.startsWith('/var/lib/atius-keycloak-admin-readonly/'))
})

test('canonicalization and digest recomputation are deterministic', () => {
  assert.equal(canonicalJson({ z: 1, a: { y: 2, x: 3 } }), '{"a":{"x":3,"y":2},"z":1}')
  const left = candidate()
  const right = JSON.parse(JSON.stringify(left))
  right.contract = Object.fromEntries(Object.entries(right.contract).reverse())
  assert.deepEqual(recomputeCandidateDigests(right), recomputeCandidateDigests(left))
})

test('offline candidate passes exactly eight gates but is not approval-ready', () => {
  const value = candidate()
  validateCandidate(value, new Date('2026-07-24T03:00:01.000Z'))
  assert.equal(value.expectedStepIds.length, 8)
  assert.equal(value.steps.filter((step) => step.status === 'PASS').length, 8)
  assert.equal(value.approvalReady, false)
  assert.equal(value.livePreflightStatus, 'BLOCKED_AUTH')
  assert.equal(value.preimage.keycloakClient.absenceStatus, 'UNKNOWN_AUTH')
})

test('ready candidate requires a fresh authenticated exact preflight', () => {
  const value = candidate({ ready: true })
  validateCandidate(value, new Date('2026-07-24T03:00:01.000Z'))
  assert.throws(
    () => validateCandidate(value, new Date('2026-07-24T03:03:01.000Z')),
    /older than 120 seconds/,
  )
})

test('chronology rejects future observations and generatedAt before observedAt', () => {
  const future = candidate({
    generatedAt: '2026-07-24T03:00:01.000Z',
    observedAt: '2026-07-24T03:01:00.000Z',
  })
  assert.throws(
    () => validateCandidate(future, new Date('2026-07-24T03:00:01.000Z')),
    /clock skew|generatedAt/,
  )
  const reversed = candidate({
    generatedAt: '2026-07-24T02:59:59.000Z',
    observedAt: '2026-07-24T03:00:00.000Z',
  })
  assert.throws(
    () => validateCandidate(reversed, new Date('2026-07-24T03:00:01.000Z')),
    /generatedAt/,
  )
  const nestedObservation = candidate()
  nestedObservation.preimage.vaultPath.observedAt = '2026-07-24T03:00:02.000Z'
  Object.assign(nestedObservation.candidate, recomputeCandidateDigests(nestedObservation))
  assert.throws(
    () => validateCandidate(nestedObservation, new Date('2026-07-24T03:00:02.000Z')),
    /generatedAt predates/,
  )
})

test('all direct observations reject recomputed stale metadata beyond 120 seconds', () => {
  const value = candidate({
    generatedAt: '2026-07-24T03:00:01.000Z',
    observedAt: '2020-01-01T00:00:00.000Z',
  })
  Object.assign(value.candidate, recomputeCandidateDigests(value))
  assert.throws(
    () => validateCandidate(value, new Date('2026-07-24T03:00:01.000Z')),
    /older than 120 seconds/,
  )

  const nested = candidate()
  nested.preimage.vaultPath.observedAt = '2026-07-24T02:57:59.999Z'
  Object.assign(nested.candidate, recomputeCandidateDigests(nested))
  assert.throws(
    () => validateCandidate(nested, new Date('2026-07-24T03:00:00.000Z')),
    /older than 120 seconds/,
  )
})

test('tampering topology or exporter SHA with stale digests fails', () => {
  for (const mutate of [
    (value) => {
      value.preimage.topology.exporter.sha256 = 'e'.repeat(64)
    },
    (value) => {
      value.preimage.topology.target.realm = 'master'
    },
  ]) {
    const value = candidate()
    mutate(value)
    assert.throws(
      () => validateCandidate(value, new Date('2026-07-24T03:00:01.000Z')),
      /topology contract|recomputed canonical inputs/,
    )
  }
})

test('tampering mutation manifest, target path, or step set with stale digests fails', () => {
  const mutations = [
    (value) => {
      value.intendedLiveMutations[0].action = 'update'
    },
    (value) => {
      value.targetScope.artifacts.approval = '/tmp/approval.json'
    },
    (value) => {
      value.expectedStepIds[0] = 'forged-step'
    },
  ]
  for (const mutate of mutations) {
    const value = candidate()
    mutate(value)
    assert.throws(
      () => validateCandidate(value, new Date('2026-07-24T03:00:01.000Z')),
      /canonical|exact|recomputed/,
    )
  }
})

test('approval accepts only provision-and-drill and enforces fresh non-future TTL', () => {
  const value = candidate({ ready: true })
  const now = new Date('2026-07-24T03:00:01.000Z')
  validateApproval(approvalFor(value), value, now)
  assert.throws(
    () => validateApproval(approvalFor(value, { operationMode: 'rollback-only' }), value, now),
    /provision-and-drill/,
  )
  assert.throws(
    () =>
      validateApproval(
        approvalFor(value, {
          issuedAt: '2099-01-01T00:00:00Z',
          expiresAt: '2099-01-01T00:15:00Z',
        }),
        value,
        now,
      ),
    /clock skew|future-issued/,
  )
  assert.throws(
    () =>
      validateApproval(
        approvalFor(value, { expiresAt: '2026-07-24T03:15:02.000Z' }),
        value,
        now,
      ),
    /900 seconds/,
  )
})

test('approval producer path/hash is bound and stale candidate strings cannot bypass recomputation', () => {
  const value = candidate({ ready: true })
  const now = new Date('2026-07-24T03:00:01.000Z')
  assert.throws(
    () => validateApproval(approvalFor(value, { producerSha256: '0'.repeat(64) }), value, now),
    /producer/,
  )
  value.preimage.vaultPath.path = 'kv/atius/keycloak/forged'
  assert.throws(() => validateApproval(approvalFor(value), value, now), /recomputed/)
})

test('private writer uses O_EXCL and refuses preexisting/symlink targets', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'karo-exclusive-'))
  await chmod(directory, 0o700)
  const target = path.join(directory, 'operation.json')
  const canary = path.join(directory, 'canary.json')
  try {
    await atomicWritePrivateJson(target, { operationId: 'one' })
    assert.equal((await stat(target)).mode & 0o777, 0o600)
    await assert.rejects(atomicWritePrivateJson(target, { operationId: 'two' }), /EEXIST/)
    await writeFile(canary, 'unchanged')
    const link = path.join(directory, 'link.json')
    await symlink(canary, link)
    await assert.rejects(atomicWritePrivateJson(link, { changed: true }), /EEXIST/)
    assert.equal(await readFile(canary, 'utf8'), 'unchanged')
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('external producer rejects forged test context and attacker-selected paths', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'karo-approval-'))
  await chmod(directory, 0o700)
  const candidatePath = path.join(directory, 'candidate.json')
  const approvalPath = path.join(directory, 'approval.json')
  const value = candidate({ ready: true })
  await writeFile(candidatePath, `${JSON.stringify(value)}\n`, { mode: 0o600 })
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
  const env = { ...process.env, KARO_TEST_CONTEXT: 'candidate', KARO_TEST_ROOT: directory }
  try {
    const result = spawnSync(process.execPath, args, { encoding: 'utf8', env })
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /reject KARO_TEST|path must be exactly/)
    await assert.rejects(stat(approvalPath), /ENOENT/)
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('approval validation refuses an offline BLOCKED_AUTH candidate', () => {
  const value = candidate()
  assert.throws(
    () => validateApproval(approvalFor(value), value, new Date('2026-07-24T03:00:01.000Z')),
    /not approval-ready/,
  )
})

test('governed entrypoints reject arbitrary report and approval paths before writes', () => {
  const candidateAttempt = spawnSync(
    process.execPath,
    [RUNNER, 'candidate', '--report', '/tmp/forbidden-keycloak-candidate.json'],
    { encoding: 'utf8' },
  )
  assert.notEqual(candidateAttempt.status, 0)
  assert.match(candidateAttempt.stderr, /path must be exactly/)
  const approvalAttempt = spawnSync(
    process.execPath,
    [
      APPROVAL_PRODUCER,
      '--candidate',
      ARTIFACT_PATHS.candidate,
      '--output',
      '/tmp/forbidden-keycloak-approval.json',
      '--operation-id',
      'readonly-forbidden-path-0001',
      '--approved-by',
      'sandbox',
      '--ttl-seconds',
      '900',
    ],
    { encoding: 'utf8' },
  )
  assert.notEqual(approvalAttempt.status, 0)
  assert.match(approvalAttempt.stderr, /path must be exactly/)
})

test('explicit harness mints the exporter sandbox root internally', () => {
  const result = spawnSync(process.execPath, [TEST_HARNESS, 'exporter'], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  assert.equal(JSON.parse(result.stdout).backupMode, 0o600)
})

test('artifact secret scan catches synthetic leaked scalar and accepts clean evidence', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'karo-secret-scan-'))
  const clean = path.join(directory, 'clean.json')
  const leaked = path.join(directory, 'leaked.json')
  const syntheticLeak = ['synthetic', 'super', 'secret', 'material', '12345'].join('-')
  await writeFile(clean, JSON.stringify({ secretsRecorded: false, clientSecretTransport: 'process-memory-and-pipes-only' }))
  await writeFile(leaked, JSON.stringify({ client_secret: syntheticLeak }))
  try {
    const pass = spawnSync('python3', [SECRET_PIPE, 'scan-artifacts', '--path', clean], {
      encoding: 'utf8',
    })
    assert.equal(pass.status, 0, pass.stderr)
    const fail = spawnSync('python3', [SECRET_PIPE, 'scan-artifacts', '--path', leaked], {
      encoding: 'utf8',
    })
    assert.notEqual(fail.status, 0)
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('exact client projection strips only frozen access metadata and rejects configuration extras', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'karo-client-projection-'))
  const expectedPath = path.join(directory, 'expected.json')
  const expected = {
    id: '11111111-1111-4111-8111-111111111111',
    ...JSON.parse(JSON.stringify(CONTRACT.client)),
  }
  await writeFile(expectedPath, JSON.stringify(expected))
  try {
    const valid = spawnSync(
      'python3',
      [SECRET_PIPE, 'exact-client-projection', '--expected', expectedPath],
      {
        input: JSON.stringify({ ...expected, access: { view: true, manage: true } }),
        encoding: 'utf8',
      },
    )
    assert.equal(valid.status, 0, valid.stderr)
    assert.deepEqual(JSON.parse(valid.stdout).strippedServerMetadata, ['access'])

    for (const mutate of [
      (value) => {
        value.rootUrl = 'https://forbidden.example'
      },
      (value) => {
        value.secret = 'opaque-secret-must-not-be-returned'
      },
      (value) => {
        value.authenticationFlowBindingOverrides = {}
      },
      (value) => {
        value.attributes.unexpected = 'true'
      },
      (value) => {
        value.redirectUris = ['https://forbidden.example/callback']
      },
      (value) => {
        value.webOrigins = ['https://forbidden.example']
      },
    ]) {
      const actual = JSON.parse(JSON.stringify(expected))
      mutate(actual)
      const rejected = spawnSync(
        'python3',
        [SECRET_PIPE, 'exact-client-projection', '--expected', expectedPath],
        { input: JSON.stringify(actual), encoding: 'utf8' },
      )
      assert.notEqual(rejected.status, 0)
    }
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('recursive secret scan catches opaque material, encodings, and fingerprint under innocuous keys', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'karo-material-scan-'))
  const nested = path.join(directory, 'scratch', 'journal', 'readback')
  await mkdir(nested, { recursive: true })
  const material = 'opaque-value-without-secret-key-9f7c'
  const variants = [
    material,
    Buffer.from(material).toString('base64'),
    Buffer.from(material).toString('base64url'),
    encodeURIComponent(material),
    Buffer.from(material).toString('hex'),
    createHash('sha256').update(material).digest('hex'),
  ]
  try {
    const cleanPath = path.join(nested, 'clean.json')
    await writeFile(cleanPath, JSON.stringify({ payload: 'unrelated-opaque-value' }))
    const clean = spawnSync(
      'python3',
      [SECRET_PIPE, 'scan-artifacts', '--secret-material-stdin', '--path', directory],
      { input: Buffer.from(`${material}\0`) },
    )
    assert.equal(clean.status, 0, clean.stderr.toString())
    assert.ok(JSON.parse(clean.stdout.toString()).scannedFiles.includes(cleanPath))

    for (const [index, variant] of variants.entries()) {
      const leakedPath = path.join(nested, `opaque-${index}.json`)
      await writeFile(leakedPath, JSON.stringify({ payload: variant }))
      const leaked = spawnSync(
        'python3',
        [SECRET_PIPE, 'scan-artifacts', '--secret-material-stdin', '--path', directory],
        { input: Buffer.from(`${material}\0`) },
      )
      assert.notEqual(leaked.status, 0)
      assert.doesNotMatch(leaked.stderr.toString(), new RegExp(material))
      await rm(leakedPath)
    }
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('forged KARO test environment cannot reach production or sandbox paths', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'karo-forged-root-'))
  await chmod(directory, 0o700)
  const operations = path.join(directory, 'operations')
  const operationId = 'readonly-forgedroot-0001'
  const operationDirectory = path.join(operations, operationId)
  await mkdir(operationDirectory, { recursive: true, mode: 0o700 })
  await chmod(operations, 0o700)
  await chmod(operationDirectory, 0o700)
  const env = {
    ...process.env,
    KARO_TEST_CONTEXT: 'runner-v1',
    KARO_TEST_PARENT_PID: String(process.pid),
    KARO_TEST_ROOT: directory,
    KARO_TEST_OPERATION_ROOT: operations,
  }
  try {
    const runner = spawnSync(
      process.execPath,
      [RUNNER, 'candidate', '--report', path.join(directory, 'candidate.json')],
      { encoding: 'utf8', env },
    )
    assert.notEqual(runner.status, 0)
    assert.match(runner.stderr, /reject KARO_TEST/)

    const live = spawnSync(
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
        path.join(directory, 'result.json'),
      ],
      { encoding: 'utf8', env },
    )
    assert.notEqual(live.status, 0)
    assert.match(live.stderr, /explicit internally rooted harness|identity mismatch/)

    const exporter = path.join(directory, 'exporter')
    const backup = path.join(directory, 'backup')
    await writeFile(exporter, '#!/usr/bin/env bash\n', { mode: 0o700 })
    const transform = spawnSync(
      'python3',
      [
        TRANSFORM,
        'preview',
        '--file',
        exporter,
        '--backup',
        backup,
        '--expected-before-sha256',
        '0'.repeat(64),
        '--sandbox',
      ],
      { encoding: 'utf8', env },
    )
    assert.notEqual(transform.status, 0)
    assert.match(transform.stderr, /direct parent|identity mismatch/)

    const journal = spawnSync(
      'python3',
      [
        STATE_HELPER,
        'event',
        '--operation-id',
        operationId,
        '--event-file',
        '001-client-armed.json',
      ],
      {
        input: JSON.stringify({ operationId, status: 'armed', secretsRecorded: false }),
        encoding: 'utf8',
        env,
      },
    )
    assert.notEqual(journal.status, 0)
    assert.match(journal.stderr, /identity mismatch/)
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('explicit harness journal refuses duplicate append-only events', () => {
  const result = spawnSync(process.execPath, [TEST_HARNESS, 'journal'], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  assert.deepEqual(JSON.parse(result.stdout), {
    scenario: 'journal',
    firstStatus: 0,
    secondStatus: 1,
  })
})

test('failure injection arms ownership before each side effect and rolls back in reverse order', async () => {
  const cases = [
    ['create-client', ['keycloak']],
    ['assign-service-account-roles', ['keycloak']],
    ['constrain-dedicated-client-scope', ['keycloak']],
    ['vault-secret-write-v1', ['vault', 'keycloak']],
    ['exporter-apply', ['exporter', 'vault', 'keycloak']],
  ]
  for (const [boundary, expectedOrder] of cases) {
    const result = spawnSync(process.execPath, [TEST_HARNESS, 'failure', boundary], {
      encoding: 'utf8',
    })
    assert.equal(result.status, 0, result.stderr)
    const failure = JSON.parse(result.stdout)
    assert.notEqual(failure.status, 0)
    assert.deepEqual(failure.order, expectedOrder)
    assert.equal(failure.rollbackSucceeded, true)
  }
})

test('live adapter statically uses reverse rollback and never sources recovery env', async () => {
  const source = await readFile(LIVE_ADAPTER, 'utf8')
  const rollback = source.slice(
    source.indexOf('rollback_owned_resources()'),
    source.indexOf('write_failure_result()'),
  )
  assert.ok(rollback.indexOf('rollback_exporter') < rollback.indexOf('rollback_vault'))
  assert.ok(rollback.indexOf('rollback_vault') < rollback.indexOf('rollback_keycloak'))
  assert.doesNotMatch(source, /source "\$\{RECOVERY_ENV\}"/)
  assert.match(source, /journal_event "\$\{FORWARD_EVENT_PREFIX\}10-client-armed/)
  assert.match(source, /journal_event "\$\{event_prefix\}-vault-armed/)
  assert.match(source, /journal_event "\$\{event_prefix\}-exporter-armed/)
})

test('runner binds but cannot import or execute the approval producer', async () => {
  const source = await readFile(RUNNER, 'utf8')
  assert.doesNotMatch(source, /import .*create-keycloak-admin-readonly-approval/)
  assert.doesNotMatch(source, /spawnSync\([^)]*create-keycloak-admin-readonly-approval/s)
  assert.match(source, /producerSha256/)
})

test('approval and apply re-read fresh metadata before claim or mutation', async () => {
  const runner = await readFile(RUNNER, 'utf8')
  const producer = await readFile(APPROVAL_PRODUCER, 'utf8')
  const live = await readFile(LIVE_ADAPTER, 'utf8')
  assert.match(producer, /validateCurrentRecoveryMetadata\(candidate\)/)
  assert.ok(
    runner.indexOf('await validateCurrentRecoveryMetadata(candidate)') <
      runner.indexOf('await createOperationClaim('),
  )
  assert.ok(
    live.indexOf('assert_recovery_metadata') <
      live.indexOf('create_client_and_roles'),
  )
  assert.ok(
    live.indexOf('assert_vault_metadata_absent') <
      live.indexOf('create_client_and_roles'),
  )
})

test('shell, Node, and Python helpers pass syntax checks', () => {
  for (const script of [RUNNER, APPROVAL_PRODUCER, TEST_HARNESS]) {
    const result = spawnSync(process.execPath, ['--check', script], { encoding: 'utf8' })
    assert.equal(result.status, 0, result.stderr)
  }
  const shell = spawnSync('bash', ['-n', LIVE_ADAPTER], { encoding: 'utf8' })
  assert.equal(shell.status, 0, shell.stderr)
  for (const script of [TRANSFORM, SECRET_PIPE, STATE_HELPER]) {
    const python = spawnSync('python3', ['-m', 'py_compile', script], {
      encoding: 'utf8',
      env: { ...process.env, PYTHONPYCACHEPREFIX: path.join(os.tmpdir(), 'karo-pycache') },
    })
    assert.equal(python.status, 0, python.stderr)
  }
})
