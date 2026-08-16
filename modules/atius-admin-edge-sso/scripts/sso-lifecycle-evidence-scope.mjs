export const FULL_LIFECYCLE_TARGET_IDS = Object.freeze([
  'sso',
  'ssh',
  'rdp',
  'oci',
  'talk',
  'admin-talk',
  'remote',
  'grafana',
  'portainer',
  'docker',
  'vpn',
  'adguard',
]);

export function resolveEvidenceScope(allTargets, rawSelection, allowSubset = false) {
  const selectedIds = [...new Set(String(rawSelection || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean))];
  const knownIds = new Set(allTargets.map(({ id }) => id));
  const missingRequiredIds = FULL_LIFECYCLE_TARGET_IDS.filter((id) => !knownIds.has(id));
  const unexpectedIds = [...knownIds].filter((id) => !FULL_LIFECYCLE_TARGET_IDS.includes(id));
  if (missingRequiredIds.length > 0 || unexpectedIds.length > 0 || knownIds.size !== allTargets.length) {
    throw new Error(`invalid full target registry missing=${missingRequiredIds.join(',') || '-'} unexpected=${unexpectedIds.join(',') || '-'} duplicates=${knownIds.size !== allTargets.length}`);
  }
  const unknownIds = selectedIds.filter((id) => !knownIds.has(id));
  if (unknownIds.length > 0) {
    throw new Error(`unknown E2E_TARGETS: ${unknownIds.join(',')}`);
  }
  if (selectedIds.length === 0) {
    return { targets: allTargets, scope: 'full', selectedIds: [...knownIds] };
  }
  if (!allowSubset) {
    throw new Error('subset evidence requires E2E_ALLOW_SUBSET_PASS=1 and never produces fleet PASS');
  }
  return {
    targets: allTargets.filter(({ id }) => selectedIds.includes(id)),
    scope: 'subset',
    selectedIds,
  };
}

export function lifecycleVerdict({ scope, sites, cycleCount, screenshotCount }) {
  const expectedCycles = sites.length * 2;
  const expectedScreenshots = sites.length * 8;
  const siteIds = sites.map(({ id }) => id);
  const siteIdSet = new Set(siteIds);
  const fullFleetSet = siteIds.length === FULL_LIFECYCLE_TARGET_IDS.length
    && siteIdSet.size === FULL_LIFECYCLE_TARGET_IDS.length
    && FULL_LIFECYCLE_TARGET_IDS.every((id) => siteIdSet.has(id));
  const complete = sites.length > 0
    && sites.every((site) => site.status === 'PASS')
    && cycleCount === expectedCycles
    && screenshotCount === expectedScreenshots;
  if (!complete) return 'FAIL';
  if (scope === 'full') return fullFleetSet ? 'PASS' : 'FAIL';
  return 'PASS_SUBSET';
}
