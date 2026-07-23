# Phase 53 Windows collector normalizer.
# This script is intentionally memory-only. Python performs authoritative schema,
# identity-policy, counter, tuple, window, and replay validation.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $ObservationJson
)

$ErrorActionPreference = 'Stop'
$forbidden = '(?i)(authorization|token|secret|private_key|payload|nonce|argv|stdout|stderr|credential|headers|environment|bearer\s+\S+|-----begin\s+)'
if ($ObservationJson -match $forbidden) {
    throw 'probe-secret-surface'
}

$observation = $ObservationJson | ConvertFrom-Json
if ($null -eq $observation) {
    throw 'probe-json-invalid'
}

$allowed = @(
    'schema_version',
    'transaction_id',
    'target_kind',
    'target',
    'started_at',
    'completed_at',
    'origins'
)
$actual = @($observation.PSObject.Properties.Name)
if (@($actual | Where-Object { $_ -notin $allowed }).Count -ne 0) {
    throw 'probe-schema-invalid'
}
if (@($allowed | Where-Object { $_ -notin $actual }).Count -ne 0) {
    throw 'probe-schema-invalid'
}

$observation | ConvertTo-Json -Compress -Depth 24
