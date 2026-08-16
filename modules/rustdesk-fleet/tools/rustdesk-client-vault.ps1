<#
PowerShell wrapper contract for the Phase 54 Windows client password channel.

The script is intentionally stdin-only and value-free on output.  The caller
must provide an approved Vault reference and pipe the ephemeral value on
stdin; no password parameter, environment lookup, transcript, or stdout
payload is accepted.  Installation and service changes remain delegated to a
later client-only backend after the Python preflight passes.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^kv/atius/rustdesk/targets/giovanni-w11-pc$')]
    [string] $VaultPath,

    [Parameter(Mandatory = $true)]
    [ValidateSet('permanent_password')]
    [string] $VaultField
)

$ErrorActionPreference = 'Stop'

if ($VaultField -ne 'permanent_password') {
    throw 'vault-field-invalid'
}

# Read only the injected ephemeral channel. Never enable a PowerShell
# transcript, emit
# the value, inspect environment variables, or accept a password argument.
$stdinValue = [Console]::In.ReadToEnd()
if ([string]::IsNullOrEmpty($stdinValue)) {
    throw 'stdin-secret-required'
}

try {
    $secureValue = ConvertTo-SecureString -String $stdinValue -AsPlainText -Force
    $stdinValue = $null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()

    # Only a redacted status object may cross the wrapper boundary.
    [PSCustomObject]@{
        state = 'READY_FOR_INJECTED_CLIENT_BACKEND'
        vault_path = $VaultPath
        field = $VaultField
        secret_material_present = $false
    } | ConvertTo-Json -Compress
}
finally {
    $secureValue = $null
    [GC]::Collect()
}
