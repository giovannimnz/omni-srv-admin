import { createHash } from 'node:crypto'
import { constants as fsConstants } from 'node:fs'
import {
  chmod,
  lstat,
  mkdir,
  open,
  readFile,
  realpath,
  rename,
  stat,
} from 'node:fs/promises'
import path from 'node:path'

export const ALLOWED_CLOCK_SKEW_MS = 30_000
export const MAX_APPROVAL_TTL_MS = 900_000
export const MAX_LIVE_PREFLIGHT_AGE_MS = 120_000
export const OPERATION_MODE = 'provision-and-drill'

export const ARTIFACT_PATHS = Object.freeze({
  candidate:
    '/home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-keycloak-readonly-candidate.json',
  livePreflight: '/run/keycloak-admin-readonly.preflight.json',
  approval: '/run/keycloak-admin-readonly.approval.json',
  liveReport:
    '/var/lib/atius-keycloak-admin-readonly/evidence/keycloak-admin-readonly-live.json',
  operationRoot: '/var/lib/atius-keycloak-admin-readonly/operations',
  scratchRoot: '/run',
  retainedBackupPrefix: '/var/backups/atius-vault-export-env.keycloak-admin-readonly.',
})

export const CONTRACT = Object.freeze({
  schemaVersion: '2',
  profile: 'keycloak-admin-readonly',
  vaultPath: 'kv/atius/keycloak/admin-readonly',
  vaultFields: [
    'KEYCLOAK_BASE_URL',
    'KEYCLOAK_READONLY_CLIENT_ID',
    'KEYCLOAK_READONLY_CLIENT_SECRET',
    'KEYCLOAK_REALM',
  ],
  baseUrl: 'http://127.0.0.1:8180',
  realm: 'atius',
  clientId: 'keycloak-admin-readonly',
  recoveryEnvPath: '/etc/keycloak/recovery-admin.env',
  recoveryEnvFields: [
    'KC_RECOVERY_ADMIN_PASSWORD',
    'KC_RECOVERY_ADMIN_USERNAME',
  ],
  exporterPath: '/usr/local/sbin/atius-vault-export-env',
  vaultPutHelperPath: '/usr/local/sbin/atius-vault-kv-put-json',
  roles: [
    'realm-management/query-clients',
    'realm-management/view-clients',
  ],
  client: {
    clientId: 'keycloak-admin-readonly',
    protocol: 'openid-connect',
    clientAuthenticatorType: 'client-secret',
    enabled: true,
    publicClient: false,
    bearerOnly: false,
    standardFlowEnabled: false,
    directAccessGrantsEnabled: false,
    implicitFlowEnabled: false,
    serviceAccountsEnabled: true,
    fullScopeAllowed: false,
    redirectUris: [],
    webOrigins: [],
    attributes: {},
  },
})

export const SOURCE_FILES = Object.freeze([
  'scripts/provision-keycloak-admin-readonly.mjs',
  'scripts/create-keycloak-admin-readonly-approval.mjs',
  'scripts/lib/keycloak-admin-readonly-contract.mjs',
  'scripts/lib/keycloak-admin-readonly-live.sh',
  'scripts/lib/keycloak-admin-readonly-exporter-transform.py',
  'scripts/lib/keycloak-admin-readonly-operation-state.py',
  'scripts/lib/keycloak-admin-readonly-secret-pipe.py',
  'scripts/lib/keycloak-admin-readonly-vault-cas-put.py',
  'scripts/tests/keycloak-admin-readonly.test.mjs',
  'scripts/fixtures/keycloak-admin-readonly/topology-no-secret.json',
  'docs/security/keycloak-admin-readonly-provisioning.md',
])

export const CANDIDATE_STEP_IDS = Object.freeze([
  'contract-exactness',
  'topology-metadata',
  'recovery-env-metadata',
  'vault-path-absence-metadata',
  'approval-separation',
  'sandbox-apply-rollback',
  'secret-hygiene',
  'intended-mutation-manifest',
])

export const LIVE_STEP_IDS = Object.freeze([
  'approval-validate',
  'operation-claim',
  'recovery-metadata-validate',
  'recovery-authenticate',
  'preimage-client-absence',
  'preimage-vault-metadata-absence',
  'preimage-exporter-capture',
  'create-client',
  'assign-service-account-roles',
  'constrain-dedicated-client-scope',
  'exact-token-role-readback',
  'vault-secret-write',
  'exporter-transform',
  'profile-hydration-readback',
  'apply-readback',
  'rollback-drill',
  'rollback-readback',
  'reapply',
  'reapply-readback',
  'live-secret-scan',
])

export const INTENDED_MUTATIONS = Object.freeze([
  {
    order: 1,
    host: 'atius-srv-1',
    resource: 'Keycloak realm atius client keycloak-admin-readonly',
    identifier: 'precomputed operation UUID',
    action: 'CAS-like create-only with explicit UUID',
    rollback: 'delete only the precomputed UUID after exact clientId readback',
  },
  {
    order: 2,
    host: 'atius-srv-1',
    resource: 'Keycloak service-account realm-management role and client-scope mappings',
    identifier: 'service account derived from the precomputed client UUID',
    action: 'assign exactly query-clients and view-clients',
    rollback: 'client deletion removes operation-owned mappings',
  },
  {
    order: 3,
    host: 'atius-srv-3',
    resource: 'Vault kv/atius/keycloak/admin-readonly',
    identifier: 'CAS=0 expected KV v2 version 1',
    action: 'create-only through secret-safe stdin helper',
    rollback: 'soft-delete only expected version 1; metadata deletion forbidden',
  },
  {
    order: 4,
    host: 'atius-srv-3',
    resource: '/usr/local/sbin/atius-vault-export-env',
    identifier: 'exact preimage/installed SHA-256 plus retained O_EXCL backup',
    action: 'deterministic profile insertion',
    rollback: 'restore retained backup before rolling back Vault and Keycloak',
  },
])

export function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonicalize(value[key])]),
    )
  }
  return value
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalize(value))
}

export function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

export function digestObject(value) {
  return sha256(canonicalJson(value))
}

export async function sha256File(filePath) {
  return sha256(await readFile(filePath))
}

export async function sourceManifestForRoot(repoRoot) {
  const manifest = []
  for (const relativePath of SOURCE_FILES) {
    manifest.push({
      path: relativePath,
      sha256: await sha256File(path.join(repoRoot, relativePath)),
    })
  }
  return manifest
}

export async function inspectMetadata(filePath) {
  const fileStat = await lstat(filePath)
  return {
    path: filePath,
    type: fileStat.isFile() ? 'regular-file' : 'other',
    mode: (fileStat.mode & 0o777).toString(8).padStart(3, '0'),
    uid: fileStat.uid,
    gid: fileStat.gid,
    size: fileStat.size,
  }
}

export function assertExactSet(actual, expected, label) {
  const left = [...actual].sort()
  const right = [...expected].sort()
  if (canonicalJson(left) !== canonicalJson(right)) {
    throw new Error(`${label} must be exact: expected ${right.join(',')}; got ${left.join(',')}`)
  }
}

export function assertCanonicalEqual(actual, expected, label) {
  if (canonicalJson(actual) !== canonicalJson(expected)) {
    throw new Error(`${label} does not match the canonical contract`)
  }
}

function parseTimestamp(value, label, now, { futureSkewMs = ALLOWED_CLOCK_SKEW_MS } = {}) {
  const timestamp = new Date(value)
  if (!Number.isFinite(timestamp.getTime())) throw new Error(`${label} is invalid`)
  if (timestamp.getTime() > now.getTime() + futureSkewMs) {
    throw new Error(`${label} exceeds the allowed ${futureSkewMs / 1000}s clock skew`)
  }
  return timestamp
}

function collectObservedAt(value, label = '$', results = []) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectObservedAt(item, `${label}[${index}]`, results))
  } else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (key === 'observedAt') results.push({ label: `${label}.observedAt`, value: child })
      collectObservedAt(child, `${label}.${key}`, results)
    }
  }
  return results
}

export function assertExactArtifactPath(actualPath, expectedPath, label) {
  if (process.env.KARO_TEST_CONTEXT === 'candidate') {
    const testRoot = process.env.KARO_TEST_ROOT
    if (testRoot && path.resolve(actualPath).startsWith(`${path.resolve(testRoot)}${path.sep}`)) return
  }
  if (path.resolve(actualPath) !== expectedPath) {
    throw new Error(`${label} path must be exactly ${expectedPath}`)
  }
}

export function operationStatePath(operationId) {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$/.test(operationId ?? '')) {
    throw new Error('operationId is invalid')
  }
  return `${ARTIFACT_PATHS.operationRoot}/${operationId}/claim.json`
}

export function retainedBackupPath(operationId) {
  operationStatePath(operationId)
  return `${ARTIFACT_PATHS.retainedBackupPrefix}${operationId}.bak`
}

export function buildTargetScope() {
  return {
    schemaVersion: '1',
    operationMode: OPERATION_MODE,
    artifacts: ARTIFACT_PATHS,
    scratchPattern: '/run/keycloak-admin-readonly.<operationId>.<pid>',
    client: {
      host: 'atius-srv-1',
      baseUrl: CONTRACT.baseUrl,
      realm: CONTRACT.realm,
      clientId: CONTRACT.clientId,
      explicitUuidRequired: true,
    },
    vault: {
      host: 'atius-srv-3',
      path: CONTRACT.vaultPath,
      expectedCreateVersion: 1,
      cas: 0,
      expectedReapplyVersion: 2,
      reapplyCas: 1,
      metadataDeleteAllowed: false,
    },
    exporter: {
      host: 'atius-srv-3',
      path: CONTRACT.exporterPath,
      retainedBackupPrefix: ARTIFACT_PATHS.retainedBackupPrefix,
    },
    intendedMutations: INTENDED_MUTATIONS,
    liveStepIds: LIVE_STEP_IDS,
  }
}

export function validateTopology(topology, now = new Date()) {
  const failures = []
  if (topology.schemaVersion !== '2') failures.push('topology schemaVersion')
  parseTimestamp(topology.observedAt, 'topology observedAt', now)
  if (topology.observationClass !== 'direct-current-metadata-no-secret') {
    failures.push('observation class')
  }
  if (topology.target?.host !== 'atius-srv-1') failures.push('target host')
  if (topology.target?.runtime !== 'native-systemd') failures.push('runtime')
  if (topology.target?.baseUrl !== CONTRACT.baseUrl) failures.push('base URL')
  if (topology.target?.realm !== CONTRACT.realm) failures.push('realm')
  if (topology.target?.keycloakVersion !== '26.6.3') failures.push('Keycloak version')
  if (topology.recoveryEnv?.path !== CONTRACT.recoveryEnvPath) failures.push('recovery env path')
  if (topology.recoveryEnv?.exists !== true) failures.push('recovery env existence')
  if (topology.recoveryEnv?.mode !== '600') failures.push('recovery env mode')
  if (topology.recoveryEnv?.owner !== 'root' || topology.recoveryEnv?.group !== 'root') {
    failures.push('recovery env ownership')
  }
  try {
    assertExactSet(topology.recoveryEnv?.fieldNames ?? [], CONTRACT.recoveryEnvFields, 'recovery env fields')
  } catch {
    failures.push('recovery env field names')
  }
  if (topology.recoveryEnv?.valuesRead !== false || topology.recoveryEnv?.valuesRecorded !== false) {
    failures.push('recovery env value handling')
  }
  if (topology.exporter?.path !== CONTRACT.exporterPath) failures.push('exporter path')
  if (!/^[a-f0-9]{64}$/.test(topology.exporter?.sha256 ?? '')) failures.push('exporter sha256')
  if (topology.exporter?.mode !== '700') failures.push('exporter mode')
  if (topology.exporter?.owner !== 'root' || topology.exporter?.group !== 'root') {
    failures.push('exporter ownership')
  }
  if (topology.vaultPutHelper?.path !== CONTRACT.vaultPutHelperPath) failures.push('Vault put helper path')
  if (!/^[a-f0-9]{64}$/.test(topology.vaultPutHelper?.sha256 ?? '')) failures.push('Vault put helper sha256')
  if (topology.vaultPutHelper?.mode !== '700') failures.push('Vault put helper mode')
  if (
    topology.vaultPath?.path !== CONTRACT.vaultPath ||
    topology.vaultPath?.present !== false ||
    topology.vaultPath?.authenticatedMetadataRead !== true ||
    topology.vaultPath?.evidenceSource !== 'direct-exact-vault-metadata-read' ||
    topology.vaultPath?.valuesRead !== false
  ) {
    failures.push('direct exact Vault metadata absence')
  }
  if (
    topology.keycloakClient?.clientId !== CONTRACT.clientId ||
    topology.keycloakClient?.absenceStatus !== 'UNKNOWN_AUTH' ||
    topology.keycloakClient?.authenticatedRead !== false
  ) {
    failures.push('offline Keycloak client status')
  }
  if (topology.secretsRecorded !== false) failures.push('topology secret handling')
  if (failures.length) throw new Error(`topology contract failed: ${failures.join(', ')}`)
}

function validateSourceManifest(sourceManifest) {
  assertExactSet(sourceManifest?.map((item) => item.path) ?? [], SOURCE_FILES, 'source manifest paths')
  if (
    !Array.isArray(sourceManifest) ||
    sourceManifest.some(
      (item) =>
        typeof item !== 'object' ||
        !SOURCE_FILES.includes(item.path) ||
        !/^[a-f0-9]{64}$/.test(item.sha256 ?? ''),
    )
  ) {
    throw new Error('source manifest contains invalid entries')
  }
}

export function recomputeCandidateDigests(candidate) {
  validateSourceManifest(candidate.candidate?.sourceManifest)
  assertCanonicalEqual(candidate.contract, CONTRACT, 'candidate contract')
  assertCanonicalEqual(candidate.targetScope, buildTargetScope(), 'candidate target scope')
  assertCanonicalEqual(candidate.intendedLiveMutations, INTENDED_MUTATIONS, 'candidate mutation manifest')
  assertExactSet(candidate.expectedStepIds ?? [], CANDIDATE_STEP_IDS, 'candidate step ids')
  assertExactSet(candidate.liveStepIds ?? [], LIVE_STEP_IDS, 'live step ids')
  const sourceDigest = digestObject(candidate.candidate.sourceManifest)
  const preimageDigest = digestObject(candidate.preimage)
  const targetScopeDigest = digestObject(candidate.targetScope)
  const digest = digestObject({
    contract: candidate.contract,
    sourceDigest,
    preimageDigest,
    targetScopeDigest,
    expectedStepIds: candidate.expectedStepIds,
    liveStepIds: candidate.liveStepIds,
    intendedMutations: candidate.intendedLiveMutations,
  })
  return { digest, sourceDigest, preimageDigest, targetScopeDigest }
}

function validateLivePreflight(candidate, generatedAt, now) {
  const preflight = candidate.livePreflight
  if (candidate.approvalReady === false) {
    if (candidate.livePreflightStatus !== 'BLOCKED_AUTH' || preflight !== null) {
      throw new Error('offline candidate must be BLOCKED_AUTH with no asserted live preflight')
    }
    if (
      candidate.preimage?.keycloakClient?.clientId !== CONTRACT.clientId ||
      candidate.preimage?.keycloakClient?.absenceStatus !== 'UNKNOWN_AUTH' ||
      candidate.preimage?.keycloakClient?.authenticatedRead !== false
    ) {
      throw new Error('offline candidate may not assert Keycloak client absence')
    }
    return
  }
  if (candidate.approvalReady !== true || candidate.livePreflightStatus !== 'READY') {
    throw new Error('candidate approval readiness is invalid')
  }
  const observedAt = parseTimestamp(preflight?.observedAt, 'live preflight observedAt', now)
  if (generatedAt < observedAt) throw new Error('candidate generatedAt predates live preflight')
  if (now.getTime() - observedAt.getTime() > MAX_LIVE_PREFLIGHT_AGE_MS) {
    throw new Error('live preflight is older than 120 seconds')
  }
  if (
    preflight.authenticated === true &&
    preflight.client?.clientId === CONTRACT.clientId &&
    preflight.client?.absent === true &&
    preflight.vault?.path === CONTRACT.vaultPath &&
    preflight.vault?.absent === true &&
    preflight.vault?.authenticatedMetadataRead === true &&
    preflight.exporter?.path === CONTRACT.exporterPath &&
    preflight.exporter?.sha256 === candidate.preimage?.topology?.exporter?.sha256 &&
    preflight.exporter?.mode === '700' &&
    preflight.exporter?.owner === 'root' &&
    preflight.exporter?.group === 'root'
  ) {
    return
  }
  throw new Error('live preflight does not prove the exact fresh target absence/preimage')
}

export function validateCandidate(candidate, now = new Date()) {
  if (candidate.schemaVersion !== '2' || candidate.mode !== 'candidate') {
    throw new Error('candidate schema/mode mismatch')
  }
  if (
    candidate.finalVerdict !== 'GO' ||
    candidate.liveProvisioning !== false ||
    candidate.humanApprovalRequired !== true ||
    candidate.recoveryAdminUsed !== false ||
    candidate.secretsRecorded !== false
  ) {
    throw new Error('candidate is not an offline GO harness prerequisite')
  }
  const generatedAt = parseTimestamp(candidate.generatedAt, 'candidate generatedAt', now)
  validateTopology(candidate.preimage?.topology, now)
  const observedTimestamps = collectObservedAt(candidate)
  if (observedTimestamps.length === 0) throw new Error('candidate has no direct observations')
  for (const observation of observedTimestamps) {
    const observedAt = parseTimestamp(observation.value, observation.label, now)
    if (generatedAt < observedAt) {
      throw new Error(`candidate generatedAt predates ${observation.label}`)
    }
  }
  assertExactSet(
    (candidate.steps ?? []).filter((step) => step.status === 'PASS').map((step) => step.id),
    CANDIDATE_STEP_IDS,
    'candidate PASS steps',
  )
  const recomputed = recomputeCandidateDigests(candidate)
  for (const [field, value] of Object.entries(recomputed)) {
    if (candidate.candidate?.[field] !== value) {
      throw new Error(`candidate ${field} does not match recomputed canonical inputs`)
    }
  }
  validateLivePreflight(candidate, generatedAt, now)
  return recomputed
}

export function validateApproval(approval, candidate, now = new Date()) {
  const recomputed = validateCandidate(candidate, now)
  if (candidate.approvalReady !== true || candidate.livePreflightStatus !== 'READY') {
    throw new Error('candidate is not approval-ready; authenticated live preflight is required')
  }
  if (approval.operationMode !== OPERATION_MODE) {
    throw new Error(`approval operationMode must be exactly ${OPERATION_MODE}`)
  }
  const producerEntry = candidate.candidate.sourceManifest.find(
    (entry) => entry.path === 'scripts/create-keycloak-admin-readonly-approval.mjs',
  )
  if (
    approval.schemaVersion !== '2' ||
    approval.approvedForKeycloakProvision !== true ||
    approval.candidateDigest !== recomputed.digest ||
    approval.sourceDigest !== recomputed.sourceDigest ||
    approval.preimageDigest !== recomputed.preimageDigest ||
    approval.targetScopeDigest !== recomputed.targetScopeDigest ||
    approval.profile !== CONTRACT.profile ||
    approval.vaultPath !== CONTRACT.vaultPath ||
    approval.clientId !== CONTRACT.clientId ||
    approval.realm !== CONTRACT.realm ||
    approval.producerPath !==
      '/home/ubuntu/GitHub/omni-srv-admin/scripts/create-keycloak-admin-readonly-approval.mjs' ||
    approval.producerSha256 !== producerEntry?.sha256
  ) {
    throw new Error('approval is not bound to the recomputed candidate/preimage/target/producer')
  }
  operationStatePath(approval.operationId)
  const issuedAt = parseTimestamp(approval.issuedAt, 'approval issuedAt', now)
  const expiresAt = parseTimestamp(approval.expiresAt, 'approval expiresAt', now, {
    futureSkewMs: MAX_APPROVAL_TTL_MS + ALLOWED_CLOCK_SKEW_MS,
  })
  const ttl = expiresAt.getTime() - issuedAt.getTime()
  const age = now.getTime() - issuedAt.getTime()
  if (
    ttl <= 0 ||
    ttl > MAX_APPROVAL_TTL_MS ||
    expiresAt <= now ||
    age < -ALLOWED_CLOCK_SKEW_MS ||
    age > MAX_APPROVAL_TTL_MS
  ) {
    throw new Error('approval is future-issued, stale, expired, or exceeds 900 seconds')
  }
  return recomputed
}

async function ensurePrivateParent(outputPath) {
  const parent = path.dirname(outputPath)
  await mkdir(parent, { recursive: true, mode: 0o700 })
  const parentStat = await lstat(parent)
  if (!parentStat.isDirectory() || parentStat.isSymbolicLink()) {
    throw new Error(`unsafe artifact parent: ${parent}`)
  }
  const resolvedParent = await realpath(parent)
  if (resolvedParent !== path.resolve(parent)) {
    throw new Error(`artifact parent contains a symlink: ${parent}`)
  }
  return resolvedParent
}

export async function atomicWritePrivateJson(outputPath, value, { exclusive = true } = {}) {
  if (!exclusive) throw new Error('non-exclusive evidence writes are forbidden')
  const resolvedParent = await ensurePrivateParent(outputPath)
  const resolvedOutput = path.join(resolvedParent, path.basename(outputPath))
  const flags =
    fsConstants.O_CREAT |
    fsConstants.O_EXCL |
    fsConstants.O_WRONLY |
    (fsConstants.O_NOFOLLOW ?? 0)
  const handle = await open(resolvedOutput, flags, 0o600)
  try {
    await handle.writeFile(`${JSON.stringify(value, null, 2)}\n`, { encoding: 'utf8' })
    await handle.sync()
  } finally {
    await handle.close()
  }
  await chmod(resolvedOutput, 0o600)
}

export async function atomicReplacePrivateJson(outputPath, value) {
  const resolvedParent = await ensurePrivateParent(outputPath)
  const resolvedOutput = path.join(resolvedParent, path.basename(outputPath))
  const existing = await lstat(resolvedOutput)
  if (!existing.isFile() || existing.isSymbolicLink() || (existing.mode & 0o777) !== 0o600) {
    throw new Error(`refusing to replace unsafe state artifact: ${outputPath}`)
  }
  const tempPath = `${resolvedOutput}.tmp-${process.pid}-${Date.now()}`
  const flags =
    fsConstants.O_CREAT |
    fsConstants.O_EXCL |
    fsConstants.O_WRONLY |
    (fsConstants.O_NOFOLLOW ?? 0)
  const handle = await open(tempPath, flags, 0o600)
  try {
    await handle.writeFile(`${JSON.stringify(value, null, 2)}\n`, { encoding: 'utf8' })
    await handle.sync()
  } finally {
    await handle.close()
  }
  await chmod(tempPath, 0o600)
  await rename(tempPath, resolvedOutput)
  const parentHandle = await open(resolvedParent, fsConstants.O_RDONLY)
  try {
    await parentHandle.sync()
  } finally {
    await parentHandle.close()
  }
}

export async function assertPrivateRegularFile(filePath, label) {
  const fileStat = await lstat(filePath)
  if (!fileStat.isFile() || fileStat.isSymbolicLink() || (fileStat.mode & 0o777) !== 0o600) {
    throw new Error(`${label} must be a non-symlink regular file with mode 0600`)
  }
  return stat(filePath)
}
