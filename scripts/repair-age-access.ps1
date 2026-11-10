$ErrorActionPreference = 'Stop'

# Only this project's private key and its two parent folders are affected.
$keyRoot = Join-Path $env:LOCALAPPDATA 'CNCGuard'
$ageFolder = Join-Path $keyRoot 'age'
$keyFile = Join-Path $ageFolder 'keys.txt'
if (-not [System.IO.File]::Exists($keyFile)) {
    throw 'The existing age key was not found. No new key has been created.'
}
$before = [System.IO.File]::ReadAllBytes($keyFile)
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$system = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')

foreach ($directory in @($keyRoot, $ageFolder)) {
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $acl.SetOwner($identity)
    foreach ($sid in @($identity, $system)) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    [System.IO.Directory]::SetAccessControl($directory, $acl)
}
$fileAcl = New-Object System.Security.AccessControl.FileSecurity
$fileAcl.SetAccessRuleProtection($true, $false)
$fileAcl.SetOwner($identity)
foreach ($sid in @($identity, $system)) {
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')
    $fileAcl.AddAccessRule($rule)
}
[System.IO.File]::SetAccessControl($keyFile, $fileAcl)
$after = [System.IO.File]::ReadAllBytes($keyFile)
if ([Convert]::ToBase64String($before) -ne [Convert]::ToBase64String($after)) {
    throw 'Unexpected key content change detected.'
}
Write-Output 'Repaired explicit access for the current Windows user and SYSTEM. Existing key content unchanged.'
