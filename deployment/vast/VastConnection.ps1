# Shared Vast.ai connection helpers. Dot-source from a script:
#   . (Join-Path $PSScriptRoot 'deployment\vast\VastConnection.ps1')
#
# Nothing here assumes a particular server: the instance ID, IP, SSH
# port and route (direct or Vast proxy) are discovered at run time.

function Get-VastCli {
    $candidates = @(
        $env:VASTAI_CLI,
        (Join-Path $HOME 'vast-cli-env\Scripts\vastai.exe')
    ) | Where-Object { $_ }
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    $onPath = Get-Command vastai -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    throw 'Vast.ai CLI not found. Install it, add it to PATH, or set $env:VASTAI_CLI.'
}

function Get-VastSshKey {
    $key = if ($env:VAST_SSH_KEY) { $env:VAST_SSH_KEY } else { Join-Path $HOME '.ssh\vast_gpu' }
    if (-not (Test-Path -LiteralPath $key)) {
        throw "SSH private key not found: $key (set `$env:VAST_SSH_KEY to override)"
    }
    return $key
}

function Resolve-VastInstanceId {
    param([string]$ProjectRoot, [long]$InstanceId = 0)
    if ($InstanceId -ne 0) { return $InstanceId }
    $configFile = Join-Path $ProjectRoot 'config\vast-instance.txt'
    if (-not (Test-Path -LiteralPath $configFile)) {
        throw 'Missing config/vast-instance.txt. Supply -InstanceId or create the file.'
    }
    return [long](Get-Content -LiteralPath $configFile -Raw).Trim()
}

# Returns @{ Host; Port; Route } for SSH. Prefers the direct mapped port
# and falls back to Vast's SSH proxy, which every instance offers.
function Get-VastSshEndpoint {
    param([Parameter(Mandatory = $true)][long]$InstanceId)

    $cli = Get-VastCli
    $json = & $cli show instance $InstanceId --raw
    if ($LASTEXITCODE -ne 0 -or -not $json) {
        throw "Could not retrieve Vast.ai instance $InstanceId."
    }
    $instance = ($json | Out-String) | ConvertFrom-Json
    if ($instance.actual_status -ne 'running') {
        throw "Vast.ai instance $InstanceId is not running (status: $($instance.actual_status))."
    }

    $ip = [string]$instance.public_ipaddr
    $direct = $null
    if ($instance.ports -and $instance.ports.'22/tcp') {
        $direct = @($instance.ports.'22/tcp') |
            Where-Object { $_.HostPort } |
            Sort-Object { if ($_.HostIp -eq '0.0.0.0') { 0 } else { 1 } } |
            Select-Object -First 1
    }
    if ($ip -and $direct) {
        return @{ Host = $ip.Trim(); Port = [int]$direct.HostPort; Route = 'direct' }
    }
    if ($instance.ssh_host -and $instance.ssh_port) {
        return @{ Host = [string]$instance.ssh_host; Port = [int]$instance.ssh_port; Route = 'proxy' }
    }
    throw "No SSH endpoint (direct or proxy) found for instance $InstanceId."
}
