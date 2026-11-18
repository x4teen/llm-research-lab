
param(
    [long]$InstanceId = 0,

    [Parameter(Mandatory = $true)]
    [string]$Script,

    # Remote project directory. Default: /workspace/llm-research-lab if
    # /workspace is writable on the server, otherwise ~/llm-research-lab.
    [string]$RemoteProject = "",

    [string]$User = "root"
)

$ErrorActionPreference = "Stop"

# 1. Portable local configuration
$localProject = $PSScriptRoot
. (Join-Path $localProject "deployment\vast\VastConnection.ps1")
$key = Get-VastSshKey

# 2. Resolve the current instance ID
$InstanceId = Resolve-VastInstanceId -ProjectRoot $localProject -InstanceId $InstanceId

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

# 4. Discover the server dynamically (direct SSH or Vast proxy)
$endpoint = Get-VastSshEndpoint -InstanceId $InstanceId
$port = $endpoint.Port
$target = "$User@$($endpoint.Host)"

$sshOptions = @(
    "-i", $key,
    "-o", "IdentitiesOnly=yes",
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=accept-new"
)
Write-Host "Connecting to instance $InstanceId at $($endpoint.Host):$port ($($endpoint.Route))"

# 5. Resolve and create the remote project directory
if (-not $RemoteProject) {
    # No double quotes: Windows PowerShell 5.1 mangles them for native exes.
    $probe = 'if [ -d /workspace ] && [ -w /workspace ]; then b=/workspace; else b=$HOME; fi; ' +
             'mkdir -p $b/llm-research-lab && echo $b/llm-research-lab'
    $RemoteProject = (& ssh @sshOptions -p $port $target $probe | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or -not $RemoteProject) {
        throw "Remote directory setup failed."
    }
    $RemoteProject = $RemoteProject.Trim()
} else {
    & ssh @sshOptions -p $port $target "mkdir -p '$RemoteProject'"
    if ($LASTEXITCODE -ne 0) { throw "Remote directory setup failed." }
}
if ($RemoteProject -notmatch '^/[A-Za-z0-9_./-]+$') {
    throw "Unexpected remote project path: $RemoteProject"
}
Write-Host "Remote project: $RemoteProject"

# 6. Transfer code and environment definition (not the whole repository)
foreach ($item in @("src", "experiments", "config", "deployment", "requirements.txt")) {
    $path = Join-Path $localProject $item
    if (Test-Path -LiteralPath $path) {
        Write-Host "Uploading: $item"
        & scp @sshOptions -P $port -r $path "${target}:${RemoteProject}/"
        if ($LASTEXITCODE -ne 0) {
            throw "File transfer failed: $item"
        }
    }
}

# 7. Prepare the remote Python environment and run the script.
#    lab-env.sh picks a usable interpreter on whatever image this is and
#    installs requirements.txt into it when needed.
$command = "bash '$RemoteProject/deployment/remote/lab-env.sh' run '$RemoteProject/$relativeScript'"
Write-Host "Executing $relativeScript on the remote server..."
& ssh @sshOptions -p $port $target $command
if ($LASTEXITCODE -ne 0) {
    throw "Remote Python execution failed."
}
Write-Host "Execution completed successfully."
