import { createHash } from 'node:crypto'
import { chmod, lstat, mkdir, open, readFile, rename } from 'node:fs/promises'
import path from 'node:path'

export const CONTRACT = Object.freeze({
  schemaVersion: '1',
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
  },
})

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
    host: 'atius-srv-1',
    resource: 'Keycloak realm atius client keycloak-admin-readonly',
    action: 'create-only',
    rollback: 'delete only the UUID created by this operation',
  },
  {
    host: 'atius-srv-1',
    resource: 'Keycloak service-account realm-management role mappings',
    action: 'assign exactly query-clients and view-clients plus matching dedicated client scope',
    rollback: 'client deletion removes the operation-owned service account',
  },
  {
    host: 'atius-srv-3',
    resource: 'Vault kv/atius/keycloak/admin-readonly',
    action: 'create one KV v2 version through atius-vault-kv-put-json stdin',
    rollback: 'soft-delete only the version created by this operation',
  },
  {
    host: 'atius-srv-3',
    resource: '/usr/local/sbin/atius-vault-export-env',
    action: 'deterministic profile insertion after O_EXCL backup',
    rollback: 'restore the operation backup after exact hash checks',
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

export async function inspectMetadata(filePath) {
  const stat = await lstat(filePath)
  return {
    path: filePath,
    type: stat.isFile() ? 'regular-file' : 'other',
    mode: (stat.mode & 0o777).toString(8).padStart(3, '0'),
    uid: stat.uid,
    gid: stat.gid,
    size: stat.size,
  }
}

export function assertExactSet(actual, expected, label) {
  const left = [...actual].sort()
  const right = [...expected].sort()
  if (canonicalJson(left) !== canonicalJson(right)) {
    throw new Error(`${label} must be exact: expected ${right.join(',')}; got ${left.join(',')}`)
  }
}

export function validateTopology(topology) {
  const failures = []
  if (topology.schemaVersion !== '1') failures.push('topology schemaVersion')
  if (topology.target?.host !== 'atius-srv-1') failures.push('target host')
  if (topology.target?.runtime !== 'native-systemd') failures.push('runtime')
  if (topology.target?.baseUrl !== CONTRACT.baseUrl) failures.push('base URL')
  if (topology.target?.realm !== CONTRACT.realm) failures.push('realm')
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
  if (topology.exporter?.path !== CONTRACT.exporterPath) failures.push('exporter path')
  if (!/^[a-f0-9]{64}$/.test(topology.exporter?.sha256 ?? '')) failures.push('exporter sha256')
  if (topology.exporter?.mode !== '700') failures.push('exporter mode')
  if (topology.exporter?.owner !== 'root' || topology.exporter?.group !== 'root') {
    failures.push('exporter ownership')
  }
  if (topology.vaultPutHelper?.path !== CONTRACT.vaultPutHelperPath) failures.push('Vault put helper path')
  if (!/^[a-f0-9]{64}$/.test(topology.vaultPutHelper?.sha256 ?? '')) failures.push('Vault put helper sha256')
  if (topology.vaultPutHelper?.mode !== '700') failures.push('Vault put helper mode')
  if (topology.vaultPath?.path !== CONTRACT.vaultPath || topology.vaultPath?.present !== false) {
    failures.push('Vault path absence metadata')
  }
  if (failures.length) throw new Error(`topology contract failed: ${failures.join(', ')}`)
}

export function validateCandidate(candidate) {
  if (candidate.schemaVersion !== '1' || candidate.mode !== 'candidate') {
    throw new Error('candidate schema/mode mismatch')
  }
  if (
    candidate.finalVerdict !== 'GO' ||
    candidate.liveProvisioning !== false ||
    candidate.humanApprovalRequired !== true ||
    candidate.recoveryAdminUsed !== false ||
    candidate.secretsRecorded !== false
  ) {
    throw new Error('candidate is not an offline GO approval prerequisite')
  }
  assertExactSet(candidate.expectedStepIds ?? [], CANDIDATE_STEP_IDS, 'candidate step ids')
  assertExactSet(
    (candidate.steps ?? []).filter((step) => step.status === 'PASS').map((step) => step.id),
    CANDIDATE_STEP_IDS,
    'candidate PASS steps',
  )
  for (const field of ['digest', 'sourceDigest', 'preimageDigest', 'targetScopeDigest']) {
    if (!/^[a-f0-9]{64}$/.test(candidate.candidate?.[field] ?? '')) {
      throw new Error(`candidate ${field} missing or invalid`)
    }
  }
  if (candidate.contract?.profile !== CONTRACT.profile || candidate.contract?.vaultPath !== CONTRACT.vaultPath) {
    throw new Error('candidate target contract mismatch')
  }
}

export function validateApproval(approval, candidate, now = new Date()) {
  validateCandidate(candidate)
  const mode = approval.operationMode
  if (!['provision-with-rollback-reapply', 'rollback-only'].includes(mode)) {
    throw new Error('approval operationMode is invalid')
  }
  if (
    approval.schemaVersion !== '1' ||
    approval.approvedForKeycloakProvision !== true ||
    approval.candidateDigest !== candidate.candidate.digest ||
    approval.sourceDigest !== candidate.candidate.sourceDigest ||
    approval.preimageDigest !== candidate.candidate.preimageDigest ||
    approval.targetScopeDigest !== candidate.candidate.targetScopeDigest ||
    approval.profile !== CONTRACT.profile ||
    approval.vaultPath !== CONTRACT.vaultPath ||
    approval.clientId !== CONTRACT.clientId ||
    approval.realm !== CONTRACT.realm
  ) {
    throw new Error('approval is not bound to the exact candidate/preimage/target')
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$/.test(approval.operationId ?? '')) {
    throw new Error('approval operationId is invalid')
  }
  const issuedAt = new Date(approval.issuedAt)
  const expiresAt = new Date(approval.expiresAt)
  const ttl = expiresAt.getTime() - issuedAt.getTime()
  if (!Number.isFinite(ttl) || ttl <= 0 || ttl > 900_000 || expiresAt <= now) {
    throw new Error('approval TTL is expired or exceeds 900 seconds')
  }
}

export async function atomicWritePrivateJson(outputPath, value, { exclusive = false } = {}) {
  await mkdir(path.dirname(outputPath), { recursive: true, mode: 0o700 })
  if (exclusive) {
    const handle = await open(outputPath, 'wx', 0o600)
    try {
      await handle.writeFile(`${JSON.stringify(value, null, 2)}\n`, { encoding: 'utf8' })
      await handle.sync()
    } finally {
      await handle.close()
    }
    await chmod(outputPath, 0o600)
    return
  }
  const tempPath = `${outputPath}.tmp-${process.pid}-${Date.now()}`
  const handle = await open(tempPath, 'wx', 0o600)
  try {
    await handle.writeFile(`${JSON.stringify(value, null, 2)}\n`, { encoding: 'utf8' })
    await handle.sync()
  } finally {
    await handle.close()
  }
  await chmod(tempPath, 0o600)
  await rename(tempPath, outputPath)
  await chmod(outputPath, 0o600)
}
