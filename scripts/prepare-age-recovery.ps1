$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security

# Export only a Windows-user-bound encrypted recovery blob, never plaintext.
$projectRoot = Split-Path -Parent $PSScriptRoot
$keyFile = Join-Path $env:LOCALAPPDATA 'CNCGuard\age\keys.txt'
$destination = Join-Path $projectRoot 'secrets\recovery\age-key.dpapi'
$keyBytes = [System.IO.File]::ReadAllBytes($keyFile)
$encrypted = [System.Security.Cryptography.ProtectedData]::Protect(
    $keyBytes, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
$verified = [System.Security.Cryptography.ProtectedData]::Unprotect(
    $encrypted, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
if ([Convert]::ToBase64String($keyBytes) -ne [Convert]::ToBase64String($verified)) {
    throw 'Windows recovery verification failed; nothing has been exported.'
}
[System.IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
[System.IO.File]::WriteAllBytes($destination, $encrypted)
[Array]::Clear($keyBytes, 0, $keyBytes.Length)
[Array]::Clear($verified, 0, $verified.Length)
Write-Output 'Created and verified Windows CurrentUser-encrypted recovery. No plaintext key exported.'
