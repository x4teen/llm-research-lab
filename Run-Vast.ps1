
param(
    [long]$InstanceId = 0,

    [Parameter(Mandatory = $true)]
    [string]$Script
)

$ErrorActionPreference = "Stop"

# 1. Portable local configuration
$localProject = $PSScriptRoot
$remoteProject = "/workspace/llm-research-lab"
$key = Join-Path $HOME ".ssh\vast_gpu"
$vastai = Join-Path $HOME "vast-cli-env\Scripts\vastai.exe"
$python = "/venv/main/bin/python"

# 2. Resolve the current instance ID
if ($InstanceId -eq 0) {
    $configFile = Join-Path $localProject "config\vast-instance.txt"
    if (-not (Test-Path -LiteralPath $configFile)) {
        throw "Missing config/vast-instance.txt"
    }
    $InstanceId = [long](Get-Content -LiteralPath $configFile -Raw).Trim()
}

if (-not (Test-Path -LiteralPath $vastai)) {
    throw "Vast.ai CLI not found: $vastai"
}
if (-not (Test-Path -LiteralPath $key)) {
    throw "SSH private key not found: $key"
}

# 3. Validate the local script and compute its relative path
$projectRoot = [IO.Path]::GetFullPath($localProject).TrimEnd('\')
$scriptPath = if ([IO.Path]::IsPathRooted($Script)) {
    [IO.Path]::GetFullPath($Script)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $Script))
}

$prefix = $projectRoot + '\'
if (-not $scriptPath.StartsWith(
    $prefix, [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Script must be inside the project directory."
}
if (-not $scriptPath.EndsWith(
    ".py", [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Only Python scripts are supported."
}
if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
    throw "Python script not found: $scriptPath"
}

$relativeScript = $scriptPath.Substring($prefix.Length).Replace('\', '/')
if ($relativeScript -notmatch '^[A-Za-z0-9_./-]+$') {
    throw "Use file and folder names without spaces or shell-special characters."
}
Write-Host "Script: $relativeScript"

# 4. Discover the GPU server dynamically
$instanceJson = & $vastai show instance $InstanceId --raw
if ($LASTEXITCODE -ne 0) {
    throw "Could not retrieve Vast.ai instance $InstanceId."
}
$instance = $instanceJson | ConvertFrom-Json
if ($instance.actual_status -ne "running") {
    throw "Vast.ai instance is not running."
}

$ip = $instance.public_ipaddr
$mapping = @($instance.ports.'22/tcp') |
    Where-Object { $_.HostIp -eq "0.0.0.0" } |
    Select-Object -First 1
if (-not $ip -or -not $mapping) {
    throw "No direct SSH connection is available."
}
$port = [int]$mapping.HostPort
$target = "root@$ip"

$sshOptions = @(
    "-i", $key,
    "-o", "IdentitiesOnly=yes",
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=accept-new"
)
Write-Host "Connecting to instance $InstanceId at ${ip}:${port}"

# 5. Create the remote project directory
& ssh @sshOptions -p $port $target "mkdir -p '$remoteProject'"
if ($LASTEXITCODE -ne 0) {
    throw "Remote directory setup failed."
}

# 6. Transfer code (not the whole repository)
foreach ($folder in @("src", "experiments", "config")) {
    $path = Join-Path $localProject $folder
    if (Test-Path -LiteralPath $path) {
        Write-Host "Uploading: $folder"
        & scp @sshOptions -P $port -r $path "${target}:${remoteProject}/"
        if ($LASTEXITCODE -ne 0) {
            throw "File transfer failed: $folder"
        }
    }
}

# 7. Execute the remote interpreter
$remoteScript = "$remoteProject/$relativeScript"
$command = "cd '$remoteProject' && '$python' '$remoteScript'"
Write-Host "Executing $relativeScript on the remote GPU..."
& ssh @sshOptions -p $port $target $command
if ($LASTEXITCODE -ne 0) {
    throw "Remote Python execution failed."
}
Write-Host "Execution completed successfully."