#!/usr/bin/env node
import { spawnSync } from 'node:child_process'
import { readFile, realpath, rm, stat } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import {
  CANDIDATE_STEP_IDS,
  CONTRACT,
  INTENDED_MUTATIONS,
  LIVE_STEP_IDS,
  atomicWritePrivateJson,
  digestObject,
  inspectMetadata,
  sha256File,
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
const SOURCE_FILES = [
  'scripts/provision-keycloak-admin-readonly.mjs',
  'scripts/lib/keycloak-admin-readonly-contract.mjs',
  'scripts/lib/keycloak-admin-readonly-live.sh',
  'scripts/lib/keycloak-admin-readonly-exporter-transform.py',
  'scripts/lib/keycloak-admin-readonly-secret-pipe.py',
  'scripts/tests/keycloak-admin-readonly.test.mjs',
  'scripts/fixtures/keycloak-admin-readonly/topology-no-secret.json',
  'docs/security/keycloak-admin-readonly-provisioning.md',
]

function parseArgs(argv) {
  const [mode, ...rest] = argv
  if (!['candidate', 'apply'].includes(mode)) throw new Error('usage: provision-keycloak-admin-readonly.mjs candidate|apply [options]')
  const options = { mode }
  for (let index = 0; index < rest.length; index += 1) {
    const item = rest[index]
    if (item === '--rollback-reapply') {
      options.rollbackReapply = true
      continue
    }
    if (!item.startsWith('--') || rest[index + 1] === undefined) throw new Error(`invalid argument near ${item}`)
    options[item.slice(2)] = rest[index + 1]
    index += 1
  }
  return options
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, 'utf8'))
}

async function currentSourceManifest() {
  const files = []
  for (const relativePath of SOURCE_FILES) {
    const absolutePath = path.join(REPO_ROOT, relativePath)
    files.push({ path: relativePath, sha256: await sha256File(absolutePath) })
  }
  return files
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
  const cpuMaxPath = path.join('/sys/fs/cgroup', unified[2], 'cpu.max')
  return readFile(cpuMaxPath, 'utf8')
}

function secretHygieneScan(textByFile) {
  const findings = []
  const suspiciousValue =
    /\b(?:password|client_secret|secret|access_token|refresh_token)\b\s*[:=]\s*["'][A-Za-z0-9+/=_-]{20,}["']/gi
  for (const [filePath, text] of textByFile) {
    if (suspiciousValue.test(text)) findings.push(filePath)
    suspiciousValue.lastIndex = 0
  }
  if (findings.length) throw new Error(`secret-like values found in: ${findings.join(', ')}`)
}

export async function buildCandidate(options) {
  if (!options.report) throw new Error('candidate requires --report')
  if (!options['preapproval-evidence']) throw new Error('candidate requires --preapproval-evidence')
  const topologyPath = await realpath(options.topology ?? DEFAULT_TOPOLOGY)
  const topology = await readJson(topologyPath)
  validateTopology(topology)

  const recoveryMetadata = await inspectMetadata(CONTRACT.recoveryEnvPath)
  if (
    recoveryMetadata.type !== 'regular-file' ||
    recoveryMetadata.mode !== topology.recoveryEnv.mode ||
    recoveryMetadata.uid !== 0 ||
    recoveryMetadata.gid !== 0 ||
    recoveryMetadata.size !== topology.recoveryEnv.size
  ) {
    throw new Error('live recovery env metadata drifted from the no-secret topology observation')
  }

  const preapprovalPath = await realpath(options['preapproval-evidence'])
  const preapproval = await readJson(preapprovalPath)
  if (
    preapproval.keycloakPreflight?.existingKeycloakCredentialFieldsFound !== 0 ||
    preapproval.requiredHumanProvisioning?.profile !== CONTRACT.profile ||
    preapproval.requiredHumanProvisioning?.vaultPath !== CONTRACT.vaultPath
  ) {
    throw new Error('preapproval evidence does not prove the exact absent credential prerequisite')
  }

  const cpuContainment = assertCpuQuota80(await readCurrentCpuMax())
  const sourceManifest = await currentSourceManifest()
  const sourceTexts = new Map()
  for (const item of sourceManifest) {
    sourceTexts.set(item.path, await readFile(path.join(REPO_ROOT, item.path), 'utf8'))
  }
  const runnerSource = sourceTexts.get('scripts/provision-keycloak-admin-readonly.mjs')
  if (/from\s+['"].*approval/.test(runnerSource)) {
    throw new Error('runner must not import, invoke, or name the approval producer')
  }

  const testRun = spawnSync(process.execPath, ['--test', TEST_PATH], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
    env: { ...process.env, KARO_TEST_CONTEXT: 'candidate' },
    maxBuffer: 2 * 1024 * 1024,
  })
  if (testRun.status !== 0) {
    throw new Error(`sandbox apply/rollback tests failed:\n${testRun.stderr || testRun.stdout}`)
  }
  secretHygieneScan(sourceTexts)

  const sourceDigest = digestObject(sourceManifest)
  const preimage = {
    topology,
    recoveryMetadata,
    vaultAbsenceEvidence: {
      reportPath: path.relative('/home/ubuntu/GitHub/vpn-atius/home-proxy', preapprovalPath),
      generatedAt: preapproval.generatedAt,
      vaultLeafRecordsChecked: preapproval.keycloakPreflight.vaultLeafRecordsChecked,
      existingKeycloakCredentialFieldsFound:
        preapproval.keycloakPreflight.existingKeycloakCredentialFieldsFound,
    },
  }
  const preimageDigest = digestObject(preimage)
  const targetScopeDigest = digestObject(INTENDED_MUTATIONS)
  const candidateBasis = {
    contract: CONTRACT,
    sourceDigest,
    preimageDigest,
    targetScopeDigest,
    expectedStepIds: CANDIDATE_STEP_IDS,
    liveStepIds: LIVE_STEP_IDS,
    intendedMutations: INTENDED_MUTATIONS,
  }
  const candidateDigest = digestObject(candidateBasis)
  const sourceCommitRun = spawnSync('git', ['rev-parse', 'HEAD'], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
  })
  if (sourceCommitRun.status !== 0) throw new Error('cannot determine owner source commit')

  const report = {
    schemaVersion: '1',
    mode: 'candidate',
    generatedAt: new Date().toISOString(),
    finalVerdict: 'GO',
    liveProvisioning: false,
    humanApprovalRequired: true,
    recoveryAdminUsed: false,
    expectedStepIds: [...CANDIDATE_STEP_IDS],
    steps: CANDIDATE_STEP_IDS.map((id) => ({ id, status: 'PASS' })),
    contract: {
      profile: CONTRACT.profile,
      vaultPath: CONTRACT.vaultPath,
      vaultFields: CONTRACT.vaultFields,
      baseUrl: CONTRACT.baseUrl,
      realm: CONTRACT.realm,
      clientId: CONTRACT.clientId,
      client: CONTRACT.client,
      exactRoles: CONTRACT.roles,
    },
    candidate: {
      digest: candidateDigest,
      sourceDigest,
      preimageDigest,
      targetScopeDigest,
      sourceCommit: sourceCommitRun.stdout.trim(),
      sourceManifest,
    },
    preimage,
    cpuContainment,
    approval: {
      present: false,
      producerSeparateFromRunner: true,
      requiredMode: '0600',
      requiredCreateSemantics: 'O_EXCL',
      maxTtlSeconds: 900,
      requiredFlag: 'approvedForKeycloakProvision=true',
      boundFields: ['operationId', 'candidateDigest', 'sourceDigest', 'preimageDigest', 'targetScopeDigest'],
      oneTimeOperation: true,
    },
    intendedLiveMutations: INTENDED_MUTATIONS,
    rollback: {
      keycloak: 'delete only operation-created UUID after exact clientId/operation validation',
      vault: 'soft-delete only operation-created KV version; metadata deletion excluded',
      exporter: 'restore O_EXCL backup after installed/preimage hash validation',
      automaticOnFailure: true,
      reapplyDrillRequired: true,
    },
    noSecretEvidence: {
      recoveryValuesReadByCandidate: false,
      vaultValuesReadByCandidate: false,
      exporterContentReadByCandidate: false,
      secretsRecorded: false,
    },
    nextGate:
      'Human must authorize one-shot recovery-admin use for provision + rollback/reapply scope.',
    secretsRecorded: false,
  }
  validateCandidate(report)
  await atomicWritePrivateJson(options.report, report)
  return report
}

async function applyLive(options) {
  for (const required of ['candidate', 'approval', 'report']) {
    if (!options[required]) throw new Error(`apply requires --${required}`)
  }
  if (!options.rollbackReapply) throw new Error('apply requires --rollback-reapply')
  if (process.getuid?.() !== 0) throw new Error('apply must run as root')

  const candidatePath = await realpath(options.candidate)
  const approvalPath = await realpath(options.approval)
  const candidate = await readJson(candidatePath)
  const approval = await readJson(approvalPath)
  validateApproval(approval, candidate)
  const approvalStat = await stat(approvalPath)
  if ((approvalStat.mode & 0o777) !== 0o600) throw new Error('approval artifact must be mode 0600')

  const currentManifest = await currentSourceManifest()
  if (digestObject(currentManifest) !== candidate.candidate.sourceDigest) {
    throw new Error('owner source digest drifted after candidate review')
  }
  const topology = candidate.preimage?.topology
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

  const statePath = `/var/lib/atius-keycloak-admin-readonly/operations/${approval.operationId}.json`
  const claim = {
    schemaVersion: '1',
    operationId: approval.operationId,
    status: 'claimed',
    claimedAt: new Date().toISOString(),
    candidateDigest: candidate.candidate.digest,
    approvalPath,
    secretsRecorded: false,
  }
  await atomicWritePrivateJson(statePath, claim, { exclusive: true })

  const scratchResult = `/run/keycloak-admin-readonly.${approval.operationId}.result.json`
  const live = spawnSync(
    'bash',
    [
      LIVE_ADAPTER,
      '--mode',
      'apply',
      '--operation-id',
      approval.operationId,
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
    liveReport = await readJson(scratchResult)
  } catch {
    liveReport = {
      schemaVersion: '1',
      mode: 'live-failure',
      finalVerdict: 'NO-GO',
      operationId: approval.operationId,
      failedStep: 'live-adapter-no-report',
      automaticRollback: { attempted: true, succeeded: false },
      secretsRecorded: false,
    }
  } finally {
    await rm(scratchResult, { force: true })
  }
  const report = {
    ...liveReport,
    candidate: {
      digest: candidate.candidate.digest,
      sourceDigest: candidate.candidate.sourceDigest,
      preimageDigest: candidate.candidate.preimageDigest,
      targetScopeDigest: candidate.candidate.targetScopeDigest,
    },
    approval: {
      operationId: approval.operationId,
      operationMode: approval.operationMode,
      approvedBy: approval.approvedBy,
      issuedAt: approval.issuedAt,
      expiresAt: approval.expiresAt,
    },
    secretsRecorded: false,
  }
  await atomicWritePrivateJson(options.report, report)
  await atomicWritePrivateJson(statePath, {
    ...claim,
    status: live.status === 0 && report.finalVerdict === 'GO' ? 'completed' : 'failed-rolled-back',
    completedAt: new Date().toISOString(),
    report: options.report,
    automaticRollback: report.automaticRollback ?? null,
    finalClientUuid: report.finalReapply?.clientUuid ?? null,
    finalVaultVersion: report.finalReapply?.vaultVersion ?? null,
  })
  if (live.status !== 0 || report.finalVerdict !== 'GO') {
    throw new Error(`live operation failed closed at ${report.failedStep ?? 'unknown step'}`)
  }
  return report
}

export async function main(argv = process.argv.slice(2)) {
  const options = parseArgs(argv)
  if (options.mode === 'candidate') return buildCandidate(options)
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
          secretsRecorded: false,
        })}\n`,
      )
    })
    .catch((error) => {
      process.stderr.write(`NO-GO: ${error.message}\n`)
      process.exitCode = 1
    })
}
