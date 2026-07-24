#!/usr/bin/env node
import { randomUUID } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { chmod, lstat, mkdir, readFile, realpath, rm } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import {
  ARTIFACT_PATHS,
  CANDIDATE_STEP_IDS,
  CONTRACT,
  INTENDED_MUTATIONS,
  LIVE_STEP_IDS,
  OPERATION_MODE,
  SOURCE_FILES,
  assertCanonicalEqual,
  assertExactArtifactPath,
  assertPrivateRegularFile,
  atomicWritePrivateJson,
  buildTargetScope,
  inspectMetadata,
  operationStatePath,
  recomputeCandidateDigests,
  retainedBackupPath,
  sourceManifestForRoot,
  validateApproval,
  validateCandidate,
  validateTopology,
} from './lib/keycloak-admin-readonly-contract.mjs'

const SCRIPT_PATH = fileURLToPath(import.meta.url)
const REPO_ROOT = path.resolve(path.dirname(SCRIPT_PATH), '..')
const LIVE_ADAPTER = path.join(REPO_ROOT, 'scripts/lib/keycloak-admin-readonly-live.sh')
const TEST_PATH = path.join(REPO_ROOT, 'scripts/tests/keycloak-admin-readonly.test.mjs')
const DEFAULT_TOPOLOGY = path.join(
  REPO_ROOT,
  'scripts/fixtures/keycloak-admin-readonly/topology-no-secret.json',
)
const OPERATION_STATE_HELPER = path.join(
  REPO_ROOT,
  'scripts/lib/keycloak-admin-readonly-operation-state.py',
)

const MODE_OPTIONS = Object.freeze({
  candidate: new Set(['report', 'live-preflight']),
  preflight: new Set(['candidate', 'report']),
  apply: new Set(['candidate', 'approval', 'report', 'rollback-reapply']),
})

function parseArgs(argv) {
  const [mode, ...rest] = argv
  if (!MODE_OPTIONS[mode]) {
    throw new Error('usage: provision-keycloak-admin-readonly.mjs candidate|preflight|apply [options]')
  }
  const options = { mode }
  for (let index = 0; index < rest.length; index += 1) {
    const item = rest[index]
    if (item === '--rollback-reapply') {
      if (!MODE_OPTIONS[mode].has('rollback-reapply')) throw new Error(`${item} is invalid for ${mode}`)
      options.rollbackReapply = true
      continue
    }
    if (!item.startsWith('--') || rest[index + 1] === undefined) {
      throw new Error(`invalid argument near ${item}`)
    }
    const name = item.slice(2)
    if (!MODE_OPTIONS[mode].has(name)) throw new Error(`--${name} is invalid for ${mode}`)
    if (options[name] !== undefined) throw new Error(`duplicate --${name}`)
    options[name] = rest[index + 1]
    index += 1
  }
  return options
}

async function readJson(filePath, label) {
  await assertPrivateRegularFile(filePath, label)
  return JSON.parse(await readFile(filePath, 'utf8'))
}

function assertCpuQuota80(cpuMaxText) {
  const [quotaText, periodText] = cpuMaxText.trim().split(/\s+/)
  if (quotaText === 'max') throw new Error('candidate requires cgroup CPUQuota=80%')
  const quota = Number(quotaText)
  const period = Number(periodText)
  if (!Number.isFinite(quota) || !Number.isFinite(period) || quota / period > 0.800001) {
    throw new Error(`candidate CPU quota exceeds 0.8 CPU: ${quotaText}/${periodText}`)
  }
  return { cpuMax: `${quotaText} ${periodText}`, cpuQuota: '80%', maxCpu: quota / period }
}

async function readCurrentCpuMax() {
  const cgroup = await readFile('/proc/self/cgroup', 'utf8')
  const unified = cgroup
    .trim()
    .split('\n')
    .map((line) => line.split(':'))
    .find((parts) => parts[0] === '0' && parts[1] === '')
  if (!unified?.[2]?.startsWith('/')) throw new Error('cannot resolve current cgroup v2 path')
  return readFile(path.join('/sys/fs/cgroup', unified[2], 'cpu.max'), 'utf8')
}

function scanSecretLikeValue(value, label, findings, key = '') {
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanSecretLikeValue(item, `${label}[${index}]`, findings))
    return
  }
  if (value && typeof value === 'object') {
    for (const [childKey, child] of Object.entries(value)) {
      scanSecretLikeValue(child, `${label}.${childKey}`, findings, childKey)
    }
    return
  }
  if (
    /(?:^|_)(?:password|secret|access_token|refresh_token|root_token|private_key)(?:$|_)/i.test(key) &&
    value !== false &&
    value !== null &&
    value !== '' &&
    value !== 'process-memory-and-pipes-only'
  ) {
    findings.push(label)
  }
}

function secretHygieneScan(textByFile, emittedObjects = []) {
  const findings = []
  const suspiciousValue =
    /\b(?:password|client_secret|access_token|refresh_token|root_token)\b\s*[:=]\s*["'][A-Za-z0-9+/=_-]{16,}["']/gi
  for (const [filePath, text] of textByFile) {
    if (suspiciousValue.test(text)) findings.push(filePath)
    suspiciousValue.lastIndex = 0
  }
  emittedObjects.forEach((value, index) => scanSecretLikeValue(value, `evidence[${index}]`, findings))
  if (findings.length) throw new Error(`secret-like values found in: ${findings.join(', ')}`)
}

async function currentSourceContext() {
  const sourceManifest = await sourceManifestForRoot(REPO_ROOT)
  const sourceTexts = new Map()
  for (const item of sourceManifest) {
    sourceTexts.set(item.path, await readFile(path.join(REPO_ROOT, item.path), 'utf8'))
  }
  const runnerSource = sourceTexts.get('scripts/provision-keycloak-admin-readonly.mjs')
  if (
    /from\s+['"][^'"]*approval[^'"]*['"]/.test(runnerSource) ||
    /spawnSync\([^)]*create-keycloak-admin-readonly-approval/s.test(runnerSource)
  ) {
    throw new Error('runner must not import or invoke the approval producer')
  }
  secretHygieneScan(sourceTexts)
  return { sourceManifest, sourceTexts }
}

function validateLivePreflightArtifact(preflight) {
  if (
    preflight.schemaVersion !== '2' ||
    preflight.mode !== 'authenticated-read-only-preflight' ||
    preflight.authenticated !== true ||
    preflight.secretsRecorded !== false ||
    preflight.client?.clientId !== CONTRACT.clientId ||
    preflight.client?.absent !== true ||
    preflight.vault?.path !== CONTRACT.vaultPath ||
    preflight.vault?.absent !== true ||
    preflight.vault?.authenticatedMetadataRead !== true ||
    preflight.exporter?.path !== CONTRACT.exporterPath ||
    !/^[a-f0-9]{64}$/.test(preflight.exporter?.sha256 ?? '')
  ) {
    throw new Error('live preflight artifact does not prove exact authenticated target absence')
  }
}

export async function buildCandidate(options) {
  if (!options.report) throw new Error('candidate requires --report')
  assertExactArtifactPath(options.report, ARTIFACT_PATHS.candidate, 'candidate report')
  const topology = await readJson(DEFAULT_TOPOLOGY, 'topology fixture')
  const now = new Date()
  validateTopology(topology, now)

  const recoveryMetadata = await inspectMetadata(CONTRACT.recoveryEnvPath)
  if (
    recoveryMetadata.type !== 'regular-file' ||
    recoveryMetadata.mode !== topology.recoveryEnv.mode ||
    recoveryMetadata.uid !== 0 ||
    recoveryMetadata.gid !== 0 ||
    recoveryMetadata.size !== topology.recoveryEnv.size
  ) {
    throw new Error('current recovery env metadata drifted from direct topology observation')
  }

  let livePreflight = null
  if (options['live-preflight']) {
    assertExactArtifactPath(
      options['live-preflight'],
      ARTIFACT_PATHS.livePreflight,
      'live preflight',
    )
    livePreflight = await readJson(options['live-preflight'], 'live preflight')
    validateLivePreflightArtifact(livePreflight)
    if (
      livePreflight.exporter.sha256 !== topology.exporter.sha256 ||
      livePreflight.exporter.mode !== topology.exporter.mode ||
      livePreflight.exporter.owner !== topology.exporter.owner ||
      livePreflight.exporter.group !== topology.exporter.group
    ) {
      throw new Error('live preflight exporter does not match current direct topology')
    }
  }

  const cpuContainment = assertCpuQuota80(await readCurrentCpuMax())
  const { sourceManifest, sourceTexts } = await currentSourceContext()
  const testRun = spawnSync(process.execPath, ['--test', TEST_PATH], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
    env: { ...process.env, KARO_TEST_CONTEXT: 'candidate' },
    maxBuffer: 4 * 1024 * 1024,
  })
  if (testRun.status !== 0) {
    throw new Error(`sandbox apply/rollback tests failed:\n${testRun.stderr || testRun.stdout}`)
  }

  const preimage = {
    topology,
    recoveryMetadata,
    keycloakClient: livePreflight
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
      observedAt: topology.observedAt,
    },
  }
  const targetScope = buildTargetScope()
  const generatedAtMs = Math.max(Date.now(), new Date(topology.observedAt).getTime())
  const report = {
    schemaVersion: '2',
    mode: 'candidate',
    generatedAt: new Date(generatedAtMs).toISOString(),
    finalVerdict: 'GO',
    liveProvisioning: false,
    humanApprovalRequired: true,
    recoveryAdminUsed: false,
    approvalReady: Boolean(livePreflight),
    livePreflightStatus: livePreflight ? 'READY' : 'BLOCKED_AUTH',
    livePreflight,
    expectedStepIds: [...CANDIDATE_STEP_IDS],
    liveStepIds: [...LIVE_STEP_IDS],
    steps: CANDIDATE_STEP_IDS.map((id) => ({ id, status: 'PASS' })),
    contract: CONTRACT,
    targetScope,
    intendedLiveMutations: INTENDED_MUTATIONS,
    candidate: {
      digest: '',
      sourceDigest: '',
      preimageDigest: '',
      targetScopeDigest: '',
      sourceCommit: '',
      sourceManifest,
    },
    preimage,
    cpuContainment,
    approval: {
      present: false,
      producerSeparateFromRunner: true,
      producerPath:
        '/home/ubuntu/GitHub/omni-srv-admin/scripts/create-keycloak-admin-readonly-approval.mjs',
      requiredMode: '0600',
      requiredCreateSemantics: 'O_EXCL|O_NOFOLLOW',
      operationMode: OPERATION_MODE,
      maxTtlSeconds: 900,
      allowedClockSkewSeconds: 30,
      requiredFlag: 'approvedForKeycloakProvision=true',
      boundFields: [
        'operationId',
        'candidateDigest',
        'sourceDigest',
        'preimageDigest',
        'targetScopeDigest',
        'producerPath',
        'producerSha256',
      ],
      oneTimeOperation: true,
    },
    rollback: {
      order: ['exporter', 'vault', 'keycloak'],
      automaticOnFailure: true,
      ownershipJournal: 'append-only and armed before each side effect',
      reapplyDrillRequired: true,
    },
    noSecretEvidence: {
      recoveryValuesReadByCandidate: false,
      vaultValuesReadByCandidate: false,
      exporterContentRecordedByCandidate: false,
      sourceFilesScanned: [...SOURCE_FILES],
      secretsRecorded: false,
    },
    nextGate: livePreflight
      ? 'Candidate is approval-ready for the exact short-lived provision-and-drill operation.'
      : 'Authorize one-shot recovery-admin use, then run authenticated read-only preflight before approval.',
    secretsRecorded: false,
  }
  const sourceCommitRun = spawnSync('git', ['rev-parse', 'HEAD'], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
  })
  if (sourceCommitRun.status !== 0) throw new Error('cannot determine owner source commit')
  report.candidate.sourceCommit = sourceCommitRun.stdout.trim()
  Object.assign(report.candidate, recomputeCandidateDigests(report))
  validateCandidate(report, new Date(generatedAtMs))
  secretHygieneScan(sourceTexts, [report])
  await atomicWritePrivateJson(options.report, report)
  return report
}

async function assertCurrentSourceMatches(candidate) {
  const current = await sourceManifestForRoot(REPO_ROOT)
  assertCanonicalEqual(current, candidate.candidate.sourceManifest, 'current owner source manifest')
  const recomputed = recomputeCandidateDigests(candidate)
  if (recomputed.sourceDigest !== candidate.candidate.sourceDigest) {
    throw new Error('current owner source digest drifted after candidate review')
  }
}

async function runReadOnlyPreflight(options) {
  for (const required of ['candidate', 'report']) {
    if (!options[required]) throw new Error(`preflight requires --${required}`)
  }
  if (process.getuid?.() !== 0) throw new Error('authenticated preflight must run as root')
  assertExactArtifactPath(options.candidate, ARTIFACT_PATHS.candidate, 'candidate')
  assertExactArtifactPath(options.report, ARTIFACT_PATHS.livePreflight, 'live preflight report')
  const candidate = await readJson(options.candidate, 'candidate')
  validateCandidate(candidate)
  if (candidate.approvalReady !== false || candidate.livePreflightStatus !== 'BLOCKED_AUTH') {
    throw new Error('preflight requires the offline BLOCKED_AUTH candidate')
  }
  await assertCurrentSourceMatches(candidate)
  const topology = candidate.preimage.topology
  const scratchResult = `/run/keycloak-admin-readonly.preflight.${process.pid}.result.json`
  const live = spawnSync(
    '/usr/bin/bash',
    [
      LIVE_ADAPTER,
      '--mode',
      'preflight',
      '--expected-exporter-sha256',
      topology.exporter.sha256,
      '--expected-put-helper-sha256',
      topology.vaultPutHelper.sha256,
      '--result',
      scratchResult,
    ],
    { cwd: REPO_ROOT, encoding: 'utf8', maxBuffer: 2 * 1024 * 1024 },
  )
  let report
  try {
    report = await readJson(scratchResult, 'preflight scratch result')
  } finally {
    await rm(scratchResult, { force: true })
  }
  if (live.status !== 0) throw new Error(`authenticated preflight failed: ${live.stderr.trim()}`)
  validateLivePreflightArtifact(report)
  await atomicWritePrivateJson(options.report, report)
  return report
}

async function createOperationClaim(approval, candidate, clientUuid) {
  const statePath = operationStatePath(approval.operationId)
  const stateDirectory = path.dirname(statePath)
  await mkdir(ARTIFACT_PATHS.operationRoot, { recursive: true, mode: 0o700 })
  await chmod(ARTIFACT_PATHS.operationRoot, 0o700)
  const operationRootStat = await lstat(ARTIFACT_PATHS.operationRoot)
  if (
    !operationRootStat.isDirectory() ||
    operationRootStat.isSymbolicLink() ||
    operationRootStat.uid !== 0 ||
    operationRootStat.gid !== 0 ||
    (await realpath(ARTIFACT_PATHS.operationRoot)) !== ARTIFACT_PATHS.operationRoot
  ) {
    throw new Error('operation root is not the exact root-owned non-symlink directory')
  }
  await mkdir(stateDirectory, { mode: 0o700 })
  const stateDirectoryStat = await lstat(stateDirectory)
  if (
    !stateDirectoryStat.isDirectory() ||
    stateDirectoryStat.isSymbolicLink() ||
    stateDirectoryStat.uid !== 0 ||
    stateDirectoryStat.gid !== 0
  ) {
    throw new Error('operation directory is not a root-owned non-symlink directory')
  }
  const claim = {
    schemaVersion: '2',
    operationId: approval.operationId,
    operationMode: OPERATION_MODE,
    status: 'claimed',
    claimedAt: new Date().toISOString(),
    candidateDigest: candidate.candidate.digest,
    approvalPath: ARTIFACT_PATHS.approval,
    reportPath: ARTIFACT_PATHS.liveReport,
    scratchRoot: ARTIFACT_PATHS.scratchRoot,
    clientUuid,
    expectedVaultVersion: 1,
    retainedExporterBackup: retainedBackupPath(approval.operationId),
    secretsRecorded: false,
  }
  await atomicWritePrivateJson(statePath, claim)
  return { claim, stateDirectory }
}

async function applyLive(options) {
  for (const required of ['candidate', 'approval', 'report']) {
    if (!options[required]) throw new Error(`apply requires --${required}`)
  }
  if (!options.rollbackReapply) throw new Error('apply requires --rollback-reapply')
  if (process.getuid?.() !== 0) throw new Error('apply must run as root')
  assertExactArtifactPath(options.candidate, ARTIFACT_PATHS.candidate, 'candidate')
  assertExactArtifactPath(options.approval, ARTIFACT_PATHS.approval, 'approval')
  assertExactArtifactPath(options.report, ARTIFACT_PATHS.liveReport, 'live report')
  const candidate = await readJson(options.candidate, 'candidate')
  const approval = await readJson(options.approval, 'approval')
  validateApproval(approval, candidate)
  await assertCurrentSourceMatches(candidate)
  const producerPath = path.join(
    REPO_ROOT,
    'scripts/create-keycloak-admin-readonly-approval.mjs',
  )
  const producerEntry = candidate.candidate.sourceManifest.find(
    (entry) => entry.path === 'scripts/create-keycloak-admin-readonly-approval.mjs',
  )
  const currentProducer = (await sourceManifestForRoot(REPO_ROOT)).find(
    (entry) => entry.path === 'scripts/create-keycloak-admin-readonly-approval.mjs',
  )
  if (
    approval.producerPath !== producerPath ||
    approval.producerSha256 !== producerEntry?.sha256 ||
    currentProducer?.sha256 !== producerEntry?.sha256
  ) {
    throw new Error('approval producer path/hash drifted')
  }
  const topology = candidate.preimage.topology
  validateTopology(topology)
  const recoveryMetadata = await inspectMetadata(CONTRACT.recoveryEnvPath)
  if (
    recoveryMetadata.mode !== '600' ||
    recoveryMetadata.uid !== 0 ||
    recoveryMetadata.gid !== 0 ||
    recoveryMetadata.size !== topology.recoveryEnv.size
  ) {
    throw new Error('recovery env metadata drift before operation claim')
  }

  const clientUuid = randomUUID()
  const { claim, stateDirectory } = await createOperationClaim(
    approval,
    candidate,
    clientUuid,
  )
  const scratchResult = `/run/keycloak-admin-readonly.${approval.operationId}.result.json`
  const live = spawnSync(
    '/usr/bin/bash',
    [
      LIVE_ADAPTER,
      '--mode',
      'apply',
      '--operation-id',
      approval.operationId,
      '--client-uuid',
      clientUuid,
      '--state-dir',
      stateDirectory,
      '--expected-exporter-sha256',
      topology.exporter.sha256,
      '--expected-put-helper-sha256',
      topology.vaultPutHelper.sha256,
      '--result',
      scratchResult,
      '--rollback-reapply',
    ],
    { cwd: REPO_ROOT, encoding: 'utf8', maxBuffer: 2 * 1024 * 1024 },
  )

  let liveReport
  try {
    liveReport = await readJson(scratchResult, 'live scratch result')
  } catch {
    liveReport = {
      schemaVersion: '2',
      mode: 'live-failure',
      finalVerdict: 'NO-GO',
      operationId: approval.operationId,
      failedStep: 'live-adapter-no-report',
      automaticRollback: { attempted: false, succeeded: false },
      secretsRecorded: false,
    }
  } finally {
    await rm(scratchResult, { force: true })
  }
  const report = {
    ...liveReport,
    candidate: recomputeCandidateDigests(candidate),
    approval: {
      operationId: approval.operationId,
      operationMode: approval.operationMode,
      approvedBy: approval.approvedBy,
      issuedAt: approval.issuedAt,
      expiresAt: approval.expiresAt,
      producerPath: approval.producerPath,
      producerSha256: approval.producerSha256,
    },
    operationState: {
      claim: path.join(stateDirectory, 'claim.json'),
      journalDirectory: stateDirectory,
    },
    secretsRecorded: false,
  }
  secretHygieneScan(new Map(), [report])
  await atomicWritePrivateJson(options.report, report)
  const rollbackSucceeded = report.automaticRollback?.succeeded === true
  const status =
    live.status === 0 && report.finalVerdict === 'GO'
      ? 'completed'
      : rollbackSucceeded
        ? 'failed-rollback-complete'
        : 'rollback-incomplete-manual-recovery-required'
  const terminal = {
    schemaVersion: '2',
    operationId: approval.operationId,
    status,
    completedAt: new Date().toISOString(),
    report: ARTIFACT_PATHS.liveReport,
    automaticRollback: report.automaticRollback ?? null,
    secretsRecorded: false,
  }
  const terminalRun = spawnSync(
    '/usr/bin/python3',
    [OPERATION_STATE_HELPER, 'terminal', '--operation-id', approval.operationId],
    { input: `${JSON.stringify(terminal)}\n`, encoding: 'utf8' },
  )
  if (terminalRun.status !== 0) {
    throw new Error(`failed to persist immutable operation terminal: ${terminalRun.stderr.trim()}`)
  }
  if (live.status !== 0 || report.finalVerdict !== 'GO') {
    throw new Error(`live operation failed closed at ${report.failedStep ?? 'unknown step'} (${status})`)
  }
  return report
}

export async function main(argv = process.argv.slice(2)) {
  const options = parseArgs(argv)
  if (options.mode === 'candidate') return buildCandidate(options)
  if (options.mode === 'preflight') return runReadOnlyPreflight(options)
  return applyLive(options)
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main()
    .then((result) => {
      process.stdout.write(
        `${JSON.stringify({
          mode: result.mode,
          finalVerdict: result.finalVerdict,
          report: parseArgs(process.argv.slice(2)).report,
          liveProvisioning: result.liveProvisioning ?? result.mode !== 'candidate',
          approvalReady: result.approvalReady ?? null,
          livePreflightStatus: result.livePreflightStatus ?? null,
          secretsRecorded: false,
        })}\n`,
      )
    })
    .catch((error) => {
      process.stderr.write(`NO-GO: ${error.message}\n`)
      process.exitCode = 1
    })
}
