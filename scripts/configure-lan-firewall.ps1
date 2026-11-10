$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$resultPath = Join-Path $projectRoot 'config\lan-firewall-result.json'
try {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Windows requires administrator approval to apply these firewall rules.'
    }
    $plan = Get-Content -LiteralPath (Join-Path $projectRoot 'config\lan-firewall.json') -Raw | ConvertFrom-Json
    # Own names only: unrelated firewall rules and the global policy are preserved.
    $blockName = 'CNCGuard-LAN-Block-Other-Networks'
    $allowName = 'CNCGuard-LAN-Allow-Group'
    foreach ($name in @($blockName, $allowName)) {
        Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    }
    New-NetFirewallRule -Name $blockName -DisplayName 'CNC Guard - block other networks' -Group 'CNC Guard' -Direction Inbound -Action Block -Enabled True -Profile Any -Protocol TCP -LocalAddress $plan.ip -LocalPort $plan.ports -RemoteAddress $plan.blocked_remote_ranges | Out-Null
    New-NetFirewallRule -Name $allowName -DisplayName 'CNC Guard - allow group LAN' -Group 'CNC Guard' -Direction Inbound -Action Allow -Enabled True -Profile Any -Protocol TCP -LocalAddress $plan.ip -LocalPort $plan.ports -RemoteAddress $plan.subnet | Out-Null
    @{ok=$true;ip=$plan.ip;subnet=$plan.subnet;ports=$plan.ports} | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    Write-Output 'Applied firewall access for the group subnet; other remote IPv4 networks blocked on these ports.'
} catch {
    @{ok=$false;error=$_.Exception.Message} | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    Write-Error $_.Exception.Message
    exit 1
}
