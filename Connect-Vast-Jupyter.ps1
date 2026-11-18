param(
    [long]$InstanceId = 0,
    [int]$LocalPort = 18080,
    [int]$RemotePort = 8080
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
. (Join-Path $root 'deployment\vast\VastConnection.ps1')
$key = Get-VastSshKey

$InstanceId = Resolve-VastInstanceId -ProjectRoot $root -InstanceId $InstanceId
$endpoint = Get-VastSshEndpoint -InstanceId $InstanceId
$sshHost = $endpoint.Host
$sshPort = $endpoint.Port

Write-Host "Instance: $InstanceId | SSH: ${sshHost}:$sshPort ($($endpoint.Route))"
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
    -p $sshPort "root@$sshHost"

if ($LASTEXITCODE -ne 0) { throw "SSH tunnel exited with code $LASTEXITCODE" }