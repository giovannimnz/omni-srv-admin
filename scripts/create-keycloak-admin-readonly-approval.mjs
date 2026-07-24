#!/usr/bin/env node
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  ARTIFACT_PATHS,
  CONTRACT,
  OPERATION_MODE,
  assertCanonicalEqual,
  assertExactArtifactPath,
  assertPrivateRegularFile,
  atomicWritePrivateJson,
  rejectTestEnvironment,
  sourceManifestForRoot,
  validateApproval,
  validateCandidate,
  validateCurrentRecoveryMetadata,
} from './lib/keycloak-admin-readonly-contract.mjs'

function parseArgs(argv) {
  const allowed = new Set([
    'candidate',
    'output',
    'operation-id',
    'operation-mode',
    'approved-by',
    'ttl-seconds',
  ])
  const options = {}
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index]
    const value = argv[index + 1]
    const name = key?.slice(2)
    if (!key?.startsWith('--') || value === undefined || !allowed.has(name)) {
      throw new Error(`invalid argument near ${key ?? '<end>'}`)
    }
    if (options[name] !== undefined) throw new Error(`duplicate --${name}`)
    options[name] = value
  }
  return options
}

rejectTestEnvironment()
const options = parseArgs(process.argv.slice(2))
for (const required of ['candidate', 'output', 'operation-id', 'approved-by', 'ttl-seconds']) {
  if (!options[required]) throw new Error(`missing --${required}`)
}
if ((options['operation-mode'] ?? OPERATION_MODE) !== OPERATION_MODE) {
  throw new Error(`--operation-mode must be exactly ${OPERATION_MODE}`)
}
assertExactArtifactPath(options.candidate, ARTIFACT_PATHS.candidate, 'candidate')
assertExactArtifactPath(options.output, ARTIFACT_PATHS.approval, 'approval')

const ttlSeconds = Number(options['ttl-seconds'])
if (!Number.isInteger(ttlSeconds) || ttlSeconds < 1 || ttlSeconds > 900) {
  throw new Error('--ttl-seconds must be an integer from 1 through 900')
}

await assertPrivateRegularFile(options.candidate, 'candidate')
const candidate = JSON.parse(await BunlessRead(options.candidate))
const issuedAt = new Date()
validateCandidate(candidate, issuedAt)
await validateCurrentRecoveryMetadata(candidate)
if (candidate.approvalReady !== true || candidate.livePreflightStatus !== 'READY') {
  throw new Error('candidate is not approval-ready; authenticated read-only preflight is required')
}

const producerPath = fileURLToPath(import.meta.url)
const repoRoot = path.resolve(path.dirname(producerPath), '..')
const currentManifest = await sourceManifestForRoot(repoRoot)
assertCanonicalEqual(
  currentManifest,
  candidate.candidate.sourceManifest,
  'current source manifest at approval production',
)
const producerEntry = currentManifest.find(
  (entry) => entry.path === 'scripts/create-keycloak-admin-readonly-approval.mjs',
)
if (!producerEntry) throw new Error('approval producer is absent from source manifest')

const expiresAt = new Date(issuedAt.getTime() + ttlSeconds * 1000)
const approval = {
  schemaVersion: '2',
  operationId: options['operation-id'],
  operationMode: OPERATION_MODE,
  candidateDigest: candidate.candidate.digest,
  sourceDigest: candidate.candidate.sourceDigest,
  preimageDigest: candidate.candidate.preimageDigest,
  targetScopeDigest: candidate.candidate.targetScopeDigest,
  approvedForKeycloakProvision: true,
  profile: CONTRACT.profile,
  vaultPath: CONTRACT.vaultPath,
  realm: CONTRACT.realm,
  clientId: CONTRACT.clientId,
  issuedAt: issuedAt.toISOString(),
  expiresAt: expiresAt.toISOString(),
  approvedBy: options['approved-by'],
  producerPath,
  producerSha256: producerEntry.sha256,
}

validateApproval(approval, candidate, issuedAt)
await atomicWritePrivateJson(options.output, approval)
process.stdout.write(
  `${JSON.stringify({
    created: true,
    output: options.output,
    operationId: approval.operationId,
    operationMode: approval.operationMode,
  })}\n`,
)

async function BunlessRead(filePath) {
  const { readFile } = await import('node:fs/promises')
  return readFile(filePath, 'utf8')
}
