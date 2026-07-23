#!/usr/bin/env node

import { constants } from 'node:fs'
import { access, chmod, mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'

const EXPECTED_SURFACES = Object.freeze({
  'skill-main': '/home/ubuntu/.codex/skills/atius-sso/SKILL.md',
  'skill-source-of-truth':
    '/home/ubuntu/.codex/skills/atius-sso/references/source-of-truth.md',
  'skill-lifecycle-acceptance':
    '/home/ubuntu/.codex/skills/atius-sso/references/lifecycle-acceptance.md',
  'manual-index':
    '/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-manual-index.md',
  'operations-manual':
    '/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-operations-manual.md',
  'wide-sso':
    '/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-wide-sso.md',
  'application-playbook':
    '/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-application-playbook.md',
  'owner-lifecycle-matrix':
    '/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-lifecycle-matrix.md',
})

const EXPECTED_STAGE_IDS = Object.freeze([
  'entry',
  'login',
  'logout-complete',
  're-enter',
  'return',
])

const EXPECTED_DECISION_IDS = Object.freeze(
  Array.from({ length: 18 }, (_, index) => `D-${String(index + 1).padStart(2, '0')}`),
)

const NEUTRAL = Object.freeze({
  heading: 'Sessão Atius ativa',
  body: 'Você entrou com sucesso. Nenhum aplicativo de destino foi informado. Você pode fechar esta aba.',
  destinationLabel: 'Destino seguro',
  value: 'Nenhum destino selecionado',
  url: 'https://sso.atius.com.br/login',
})

const DOCUMENT_CHECKS = Object.freeze([
  {
    id: 'DOC-CANONICAL-LOGIN',
    test: text =>
      text.includes('/login') &&
      /\b(canonical|can[oô]nic[oa]|human|humana)\b/i.test(text),
  },
  {
    id: 'DOC-INTERNAL-SO-COMPATIBILITY',
    test: text =>
      text.includes('/sso') &&
      /\b(internal|controlled compatibility|compatibilidade controlada|compatibility)\b/i.test(
        text,
      ) &&
      /\b(internal rewrite|internal proxy|minimal proxy|proxy m[ií]nimo|rewrite interno)\b/i.test(
        text,
      ),
  },
  {
    id: 'DOC-VALIDATED-DESTINATION-LIFECYCLE',
    test: text =>
      ['entry', 'login', 'logout-complete', 're-entry', 'return'].every(term =>
        text.toLowerCase().includes(term),
      ) &&
      ['valid', 'missing', 'rejected'].every(term => text.toLowerCase().includes(term)),
  },
  {
    id: 'DOC-EXACT-NEUTRAL-TUPLE',
    test: text =>
      Object.values(NEUTRAL).every(value => text.includes(value)) &&
      (/\b(no|absent|sem)\b.{0,120}\b(application|aplica[cç][aã]o)\b.{0,60}\b(control|controle)/is.test(
        text,
      ) ||
        /\b(application|aplica[cç][aã]o)\b.{0,60}\b(control|controle)\b.{0,40}\b(absent|none|ausente)/is.test(
          text,
        )),
  },
  {
    id: 'DOC-POST-ONLY-CENTRAL-LOGOUT',
    test: text =>
      text.includes('/api/sso/logout') && /\bPOST(?:-only)?\b/i.test(text),
  },
  {
    id: 'DOC-REAL-BROWSER-ORIGIN',
    test: text =>
      text.includes('Origin') && /\b(real browser|browser-generated|browser supplies|incoming browser)\b/i.test(text),
  },
  {
    id: 'DOC-JSON-CONTENT-TYPE',
    test: text => text.includes('Content-Type: application/json'),
  },
  {
    id: 'DOC-SESSION-BOUND-ONE-TIME-CSRF',
    test: text =>
      text.includes('X-CSRF-Token') &&
      /\b(session-bound|authenticated-session|sess[aã]o)\b/i.test(text) &&
      /\b(one-time|uma vez|uso [uú]nico)\b/i.test(text),
  },
  {
    id: 'DOC-EXACT-MINIMAL-LOGOUT-OWNERSHIP',
    test: text =>
      (text.includes('exact/minimal') ||
        /\b(exact operation|minimal operation|opera[cç][aã]o exata)\b/i.test(
          text,
        )) &&
      /\b(general\s+ATS\s+API|ATS\s+API\s+generally|ATS\s+APIs\s+generally|API\s+ATS\s+geral)\b/i.test(
        text,
      ),
  },
  {
    id: 'DOC-ROLLBACK-AND-READBACK',
    test: text =>
      /\brollback\b/i.test(text) && /\breadback\b/i.test(text),
  },
  {
    id: 'DOC-RUNTIME-PROMOTION-PENDING',
    test: text =>
      text.includes('10-04') &&
      text.includes('10-05') &&
      /\b(planned|pending|absent|evidence|evid[eê]ncia)\b/i.test(text),
  },
  {
    id: 'DOC-FULL-GBRAIN-SLUG',
    test: text =>
      text.includes('aisecondbrain/30-recursos/atius/sso-atius-guia-canonico'),
  },
  {
    id: 'DOC-REFERENCED-PATHS-EXIST',
    test: () => true,
  },
])

const CONTRACT_CHECKS = Object.freeze([
  'CONTRACT-CANONICAL-ROUTING',
  'CONTRACT-EXACT-LIFECYCLE-STAGES',
  'CONTRACT-EXACT-NEUTRAL-TUPLE',
  'CONTRACT-POST-ORIGIN-JSON-CSRF-LOGOUT',
  'CONTRACT-FAIL-CLOSED-NEGATIVES',
  'CONTRACT-EXACT-DECISION-SET',
  'AUDITOR-FORBIDDEN-PATTERN-SELFTEST',
])

const FORBIDDEN_PATTERNS = Object.freeze([
  {
    id: 'FORBID-EXTERNAL-LOGIN-TO-SSO',
    pattern: /\/login[^\n]{0,120}(?:308|301|302|307)\b[^\n]{0,120}\/sso/i,
  },
  {
    id: 'FORBID-SSO-HUMAN-CANONICAL',
    pattern:
      /(?:human|humana|humano)[^\n]{0,80}(?:canonical|can[oô]nic[oa])[^\n]{0,80}\/sso|\/sso[^\n]{0,80}(?:human|humana|humano)[^\n]{0,80}(?:canonical|can[oô]nic[oa])/i,
    allowNegated: true,
  },
  {
    id: 'FORBID-IMPLICIT-TRADE-FALLBACK',
    pattern:
      /(?:fallback|default)[^\n]{0,80}trade\.atius\.com\.br[^\n]{0,80}(?:when missing|quando ausente|implicit|impl[ií]cit)/i,
  },
  {
    id: 'FORBID-MUTATING-GET-LOGOUT',
    pattern:
      /(?:GET\s+(?:https:\/\/sso\.atius\.com\.br)?\/api\/sso\/logout|export\s+async\s+function\s+GET)/i,
  },
  {
    id: 'FORBID-FORGED-ALLOWED-ORIGIN-EXAMPLE',
    pattern:
      /(?:-H\s+['"]Origin:\s*https:\/\/(?:sso|adguard)\.atius\.com\.br|['"]Origin['"]\s*:\s*['"]https:\/\/(?:sso|adguard)\.atius\.com\.br)/i,
  },
  {
    id: 'FORBID-FIRST-REDIRECT-APPROVAL',
    pattern:
      /(?:first|primeiro)\s+(?:redirect|redirecionamento)[^\n]{0,80}(?:is|e|é)\s+(?:sufficient|approval|aceite|aprova[cç][aã]o)/i,
  },
  {
    id: 'FORBID-GENERAL-ATS-API-PROXY',
    pattern:
      /(?:proxy|proxied|publicar|expor)[^\n]{0,80}(?:whole|entire|general|geral)[^\n]{0,30}ATS API/i,
  },
  {
    id: 'FORBID-STALE-SHORT-GBRAIN-SLUG',
    pattern:
      /\bgbrain\s+get\s+sso-atius-guia-canonico\b/i,
  },
])

const SECRET_PATTERNS = Object.freeze([
  {
    id: 'SECRET-PRIVATE-KEY',
    pattern: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
  },
  {
    id: 'SECRET-CLOUD-ACCESS-KEY',
    pattern: /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/,
  },
  {
    id: 'SECRET-BEARER-VALUE',
    pattern: /\bBearer\s+[A-Za-z0-9_-]{20,}(?:\.[A-Za-z0-9_-]{10,})*/i,
  },
  {
    id: 'SECRET-ASSIGNED-VALUE',
    pattern:
      /\b(?:password|senha|client_secret|api_key|access_token|csrf_token)\b\s*[:=]\s*["']?(?!<|\[|REDACTED|example|nome|field)[A-Za-z0-9+/_=-]{16,}/i,
  },
])

function fail(message) {
  throw new Error(message)
}

function parseArgs(argv) {
  const parsed = {}
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index]
    const value = argv[index + 1]
    if (!key?.startsWith('--') || !value || value.startsWith('--')) {
      fail(`invalid arguments near ${key ?? '<end>'}`)
    }
    if (parsed[key.slice(2)]) fail(`duplicate argument ${key}`)
    parsed[key.slice(2)] = value
  }
  if (!parsed.contract) fail('--contract is required')
  if (!parsed.report) fail('--report is required')
  return parsed
}

function sortedUnique(values) {
  return [...new Set(values)].sort()
}

function sameSet(left, right) {
  return (
    left.length === right.length &&
    sortedUnique(left).every((value, index) => value === sortedUnique(right)[index])
  )
}

function lineForIndex(text, index) {
  return text.slice(0, Math.max(0, index)).split('\n').length
}

function firstFinding(text, entry) {
  const flags = entry.pattern.flags.includes('g')
    ? entry.pattern.flags
    : `${entry.pattern.flags}g`
  const pattern = new RegExp(entry.pattern.source, flags)
  for (const match of text.matchAll(pattern)) {
    if (entry.allowNegated) {
      const lineStart = text.lastIndexOf('\n', match.index) + 1
      const lineEnd = text.indexOf('\n', match.index)
      const line = text.slice(lineStart, lineEnd < 0 ? text.length : lineEnd)
      const context = text.slice(Math.max(0, lineStart - 160), lineEnd)
      if (
        /\b(?:never|not|no|forbidden|forbid|prohibited|prohibit|rejects?|internal|controlled|nunca|n[aã]o|proibido|rejeita)\b/i.test(
          `${context}\n${line}`,
        )
      ) {
        continue
      }
    }
    return {
      id: entry.id,
      line: lineForIndex(text, match.index),
    }
  }
  return null
}

function forbiddenPatternSelfTest() {
  const samples = new Map([
    ['FORBID-EXTERNAL-LOGIN-TO-SSO', 'GET /login returns 308 Location: /sso'],
    ['FORBID-SSO-HUMAN-CANONICAL', 'Human canonical route: /sso'],
    [
      'FORBID-IMPLICIT-TRADE-FALLBACK',
      'Default trade.atius.com.br when missing is implicit.',
    ],
    ['FORBID-MUTATING-GET-LOGOUT', 'GET /api/sso/logout clears cookies'],
    [
      'FORBID-FORGED-ALLOWED-ORIGIN-EXAMPLE',
      "curl -H 'Origin: https://sso.atius.com.br'",
    ],
    ['FORBID-FIRST-REDIRECT-APPROVAL', 'First redirect is sufficient approval'],
    ['FORBID-GENERAL-ATS-API-PROXY', 'proxy the general ATS API'],
    ['FORBID-STALE-SHORT-GBRAIN-SLUG', 'gbrain get sso-atius-guia-canonico'],
  ])

  return FORBIDDEN_PATTERNS.every(entry => {
    const sample = samples.get(entry.id)
    return typeof sample === 'string' && firstFinding(sample, {
      ...entry,
      allowNegated: false,
    })
  })
}

function extractResolvableReferences(text) {
  const references = []
  for (const match of text.matchAll(/`([^`\n]+)`/g)) {
    const value = match[1]
    if (value.startsWith('/home/ubuntu/')) {
      references.push(value)
    } else if (
      value.startsWith('docs/domain/') ||
      value.startsWith('.planning/workstreams/')
    ) {
      references.push(resolve('/home/ubuntu/GitHub/omni-srv-admin', value))
    } else if (value.startsWith('references/')) {
      references.push(resolve('/home/ubuntu/.codex/skills/atius-sso', value))
    }
  }
  return sortedUnique(references)
}

function evaluateContract(contract) {
  const passed = []

  if (
    contract.humanLoginPath === '/login' &&
    contract.internalLoginPath === '/sso/login' &&
    contract.compatibilityPath === '/sso' &&
    contract.routing?.strategy === 'internal-rewrite-or-minimal-proxy' &&
    contract.routing?.visibleBrowserPath === '/login' &&
    contract.routing?.externalLoginToSsoRedirectAllowed === false &&
    contract.routing?.publicReturnToQueryAllowedAfterBootstrap === false
  ) {
    passed.push('CONTRACT-CANONICAL-ROUTING')
  }

  if (
    sameSet(contract.states ?? [], ['valid', 'missing', 'rejected']) &&
    sameSet(
      (contract.stages ?? []).map(stage => stage.id),
      EXPECTED_STAGE_IDS,
    )
  ) {
    passed.push('CONTRACT-EXACT-LIFECYCLE-STAGES')
  }

  if (
    contract.neutralSemantics?.heading === NEUTRAL.heading &&
    contract.neutralSemantics?.body === NEUTRAL.body &&
    contract.neutralSemantics?.destinationLabel === NEUTRAL.destinationLabel &&
    contract.neutralSemantics?.value === NEUTRAL.value &&
    contract.neutralSemantics?.url === NEUTRAL.url &&
    contract.neutralSemantics?.enterAgainPresent === false &&
    contract.neutralSemantics?.backPresent === false
  ) {
    passed.push('CONTRACT-EXACT-NEUTRAL-TUPLE')
  }

  if (
    contract.logout?.path === '/api/sso/logout' &&
    contract.logout?.method === 'POST' &&
    contract.logout?.contentType === 'application/json' &&
    sameSet(contract.logout?.requiredHeaders ?? [], [
      'Origin',
      'Content-Type',
      'X-CSRF-Token',
    ]) &&
    contract.logout?.csrf?.header === 'X-CSRF-Token' &&
    contract.logout?.csrf?.binding === 'authenticated-session' &&
    contract.logout?.csrf?.oneTime === true &&
    contract.logout?.fixedCompletionUrl === NEUTRAL.url
  ) {
    passed.push('CONTRACT-POST-ORIGIN-JSON-CSRF-LOGOUT')
  }

  if (
    sameSet(contract.logout?.failClosedCases ?? [], [
      'GET',
      'missing-origin',
      'wrong-origin',
      'wrong-content-type',
      'missing-csrf-token',
      'invalid-csrf-token',
      'reused-csrf-token',
    ]) &&
    (contract.negativeCases ?? []).length > 0
  ) {
    passed.push('CONTRACT-FAIL-CLOSED-NEGATIVES')
  }

  if (sameSet(contract.decisions ?? [], EXPECTED_DECISION_IDS)) {
    passed.push('CONTRACT-EXACT-DECISION-SET')
  }

  if (forbiddenPatternSelfTest()) {
    passed.push('AUDITOR-FORBIDDEN-PATTERN-SELFTEST')
  }

  return sortedUnique(passed)
}

async function pathExists(path) {
  try {
    await access(path, constants.R_OK)
    return true
  } catch {
    return false
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const contractPath = resolve(args.contract)
  const reportPath = resolve(args.report)
  const contract = JSON.parse(await readFile(contractPath, 'utf8'))

  if (contract.schemaVersion !== 1) fail('unsupported contract schemaVersion')
  if (contract.contractId !== 'atius-sso-destination-lifecycle-v1') {
    fail('unexpected contractId')
  }

  const expectedSurfaceIds = Object.keys(EXPECTED_SURFACES).sort()
  const expectedCheckIds = sortedUnique([
    ...CONTRACT_CHECKS,
    ...DOCUMENT_CHECKS.map(check => check.id),
  ])
  const observedSurfaceIds = []
  const perSurface = []
  const secretFindings = []
  const referenceFindings = []

  for (const surfaceId of expectedSurfaceIds) {
    const path = EXPECTED_SURFACES[surfaceId]
    if (!(await pathExists(path))) {
      perSurface.push({
        surfaceId,
        path,
        readable: false,
        passedCheckIds: [],
        missingCheckIds: DOCUMENT_CHECKS.map(check => check.id).sort(),
        forbiddenFindings: [],
      })
      continue
    }

    observedSurfaceIds.push(surfaceId)
    const text = await readFile(path, 'utf8')
    const missingReferences = []
    for (const reference of extractResolvableReferences(text)) {
      if (!(await pathExists(reference))) missingReferences.push(reference)
    }
    referenceFindings.push(
      ...missingReferences.map(reference => ({ surfaceId, reference })),
    )
    const passedCheckIds = DOCUMENT_CHECKS.filter(check =>
      check.id === 'DOC-REFERENCED-PATHS-EXIST'
        ? missingReferences.length === 0
        : check.test(text),
    ).map(check => check.id)
    const missingCheckIds = DOCUMENT_CHECKS.map(check => check.id).filter(
      id => !passedCheckIds.includes(id),
    )
    const forbiddenFindings = FORBIDDEN_PATTERNS.map(entry =>
      firstFinding(text, entry),
    ).filter(Boolean)
    const surfaceSecrets = SECRET_PATTERNS.map(entry =>
      firstFinding(text, entry),
    )
      .filter(Boolean)
      .map(finding => ({ surfaceId, ...finding }))

    secretFindings.push(...surfaceSecrets)
    perSurface.push({
      surfaceId,
      path,
      readable: true,
      passedCheckIds: sortedUnique(passedCheckIds),
      missingCheckIds: sortedUnique(missingCheckIds),
      forbiddenFindings,
      missingReferences,
    })
  }

  const contractPassedCheckIds = evaluateContract(contract)
  const documentCheckIdsPassingEverySurface = DOCUMENT_CHECKS.map(
    check => check.id,
  ).filter(checkId =>
    perSurface.every(
      result =>
        result.readable &&
        result.passedCheckIds.includes(checkId) &&
        result.forbiddenFindings.length === 0,
    ),
  )
  const observedCheckIds = sortedUnique([
    ...contractPassedCheckIds,
    ...documentCheckIdsPassingEverySurface,
  ])
  const missingIds = expectedCheckIds.filter(id => !observedCheckIds.includes(id))
  const unexpectedIds = observedCheckIds.filter(id => !expectedCheckIds.includes(id))
  const forbiddenFindingCount = perSurface.reduce(
    (total, surface) => total + surface.forbiddenFindings.length,
    0,
  )
  const verdict =
    sameSet(expectedSurfaceIds, observedSurfaceIds) &&
    sameSet(expectedCheckIds, observedCheckIds) &&
    missingIds.length === 0 &&
    unexpectedIds.length === 0 &&
    secretFindings.length === 0 &&
    referenceFindings.length === 0 &&
    forbiddenFindingCount === 0
      ? 'PASS'
      : 'FAIL'

  const report = {
    schemaVersion: 1,
    contractId: contract.contractId,
    contractPath,
    expectedSurfaceIds,
    observedSurfaceIds: sortedUnique(observedSurfaceIds),
    expectedCheckIds,
    observedCheckIds,
    missingIds,
    unexpectedIds,
    secretFindings,
    referenceFindings,
    forbiddenFindingCount,
    perSurface,
    verdict,
  }

  await mkdir(dirname(reportPath), { recursive: true, mode: 0o700 })
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, {
    mode: 0o600,
  })
  await chmod(reportPath, 0o600)

  console.log(
    JSON.stringify({
      verdict,
      surfaces: `${report.observedSurfaceIds.length}/${expectedSurfaceIds.length}`,
      checks: `${observedCheckIds.length}/${expectedCheckIds.length}`,
      missingIds,
      unexpectedIds,
      secretFindingCount: secretFindings.length,
      forbiddenFindingCount,
      report: reportPath,
    }),
  )

  if (verdict !== 'PASS') process.exitCode = 1
}

main().catch(error => {
  console.error(`atius-sso-lifecycle-audit: ${error.message}`)
  process.exitCode = 1
})
