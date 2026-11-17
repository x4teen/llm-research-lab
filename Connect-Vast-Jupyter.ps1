param(
    [long]$InstanceId = 0,
    [int]$LocalPort = 18080,
    [int]$RemotePort = 8080
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$cli = Join-Path $HOME 'vast-cli-env\Scripts\vastai.exe'
$key = Join-Path $HOME '.ssh\vast_gpu'

if ($InstanceId -eq 0) {
    $idFile = Join-Path $root 'config\vast-instance.txt'
    if (-not (Test-Path -LiteralPath $idFile)) {
        throw 'Missing config/vast-instance.txt. Supply -InstanceId or create the file.'
    }
    $InstanceId = [long](Get-Content -LiteralPath $idFile -Raw).Trim()
}

if (-not (Test-Path -LiteralPath $cli)) { throw "Missing Vast.ai CLI: $cli" }
if (-not (Test-Path -LiteralPath $key)) { throw "Missing SSH key: $key" }

$json = & $cli show instance $InstanceId --raw
if ($LASTEXITCODE -ne 0 -or -not $json) { throw 'Vast.ai lookup failed.' }
$instance = $json | ConvertFrom-Json
if ($instance.actual_status -ne 'running') {
    throw "Instance $InstanceId is not running."
}

$ip = [string]$instance.public_ipaddr
$sshMapping = @($instance.ports.'22/tcp') |
    Where-Object { $_.HostIp -eq '0.0.0.0' } |
    Select-Object -First 1
if (-not $ip -or -not $sshMapping) {
    throw 'No direct SSH endpoint found for this instance.'
}
$sshPort = [int]$sshMapping.HostPort

Write-Host "Instance: $InstanceId | SSH: ${ip}:$sshPort"
Write-Host "Tunnel: localhost:$LocalPort -> Vast.ai 127.0.0.1:$RemotePort"
Write-Host 'Keep this terminal open while using VS Code Jupyter. Ctrl+C closes tunnel.'

# -N: tunnel only; -L: bind only to Windows loopback;
# ExitOnForwardFailure: fail promptly on an unavailable local port.
& ssh -N `
    -i $key `
    -o 'IdentitiesOnly=yes' `
    -o 'ExitOnForwardFailure=yes' `
    -o 'ServerAliveInterval=30' `
    -L "127.0.0.1:${LocalPort}:127.0.0.1:${RemotePort}" `
    -p $sshPort "root@$ip"

if ($LASTEXITCODE -ne 0) { throw "SSH tunnel exited with code $LASTEXITCODE" }