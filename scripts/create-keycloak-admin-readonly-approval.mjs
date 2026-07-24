#!/usr/bin/env node
import { realpath, stat } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import {
  CONTRACT,
  atomicWritePrivateJson,
  validateCandidate,
} from './lib/keycloak-admin-readonly-contract.mjs'

function parseArgs(argv) {
  const options = {}
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index]
    const value = argv[index + 1]
    if (!key?.startsWith('--') || value === undefined) throw new Error(`invalid argument near ${key ?? '<end>'}`)
    options[key.slice(2)] = value
  }
  return options
}

const options = parseArgs(process.argv.slice(2))
for (const required of ['candidate', 'output', 'operation-id', 'approved-by', 'ttl-seconds']) {
  if (!options[required]) throw new Error(`missing --${required}`)
}

const ttlSeconds = Number(options['ttl-seconds'])
if (!Number.isInteger(ttlSeconds) || ttlSeconds < 1 || ttlSeconds > 900) {
  throw new Error('--ttl-seconds must be an integer from 1 through 900')
}

const candidatePath = await realpath(options.candidate)
const candidate = JSON.parse(await BunlessRead(candidatePath))
validateCandidate(candidate)

const issuedAt = new Date()
const expiresAt = new Date(issuedAt.getTime() + ttlSeconds * 1000)
const producerPath = await realpath(fileURLToPath(import.meta.url))
const approval = {
  schemaVersion: '1',
  operationId: options['operation-id'],
  operationMode: options['operation-mode'] ?? 'provision-with-rollback-reapply',
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
}

await atomicWritePrivateJson(options.output, approval, { exclusive: true })
const outputStat = await stat(options.output)
if ((outputStat.mode & 0o777) !== 0o600) throw new Error('approval artifact mode is not 0600')
process.stdout.write(`${JSON.stringify({ created: true, output: options.output, operationId: approval.operationId })}\n`)

async function BunlessRead(filePath) {
  const { readFile } = await import('node:fs/promises')
  return readFile(filePath, 'utf8')
}
