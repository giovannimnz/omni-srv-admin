-- CVE/USN and Ubuntu Pro security reporting snapshots.
-- This schema stores evidence and normalized fields, not Pro tokens.

CREATE TABLE IF NOT EXISTS "TbSecurityFindings" (
    id BIGSERIAL PRIMARY KEY,
    host_id TEXT NOT NULL REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    package_name TEXT,
    cve_id TEXT,
    usn_id TEXT,
    priority TEXT,
    origin TEXT,
    status TEXT NOT NULL DEFAULT 'observed',
    fix_available BOOLEAN,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    CHECK (finding_type IN ('summary', 'cve', 'usn', 'package', 'repository')),
    CHECK (status IN ('observed', 'not-affected', 'affected', 'fixed', 'unknown', 'blocked'))
);

CREATE INDEX IF NOT EXISTS "IdxTbSecurityFindingsHostCreated"
    ON "TbSecurityFindings"(host_id, created_at DESC);

CREATE INDEX IF NOT EXISTS "IdxTbSecurityFindingsCve"
    ON "TbSecurityFindings"(cve_id)
    WHERE cve_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS "IdxTbSecurityFindingsPackage"
    ON "TbSecurityFindings"(package_name, host_id)
    WHERE package_name IS NOT NULL;

