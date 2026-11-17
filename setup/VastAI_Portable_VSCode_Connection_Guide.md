# LLM Research Lab — Portable VS Code to Vast.ai Connection Guide

**Objective:** Keep Python source files and notebooks on your Windows desktop while running Python scripts on whichever Vast.ai GPU instance you rent. The setup discovers the current server IP address and SSH port from an instance ID, copies your code for execution, and displays results inside VS Code.

## 1. Architecture

```text
Windows desktop                              Vast.ai GPU instance
VS Code + Git repository                     Linux + Python + PyTorch/CUDA
E:\Dev\llm-research-lab                     /workspace/llm-research-lab
       |                                            ^
       | PowerShell + Vast.ai CLI + SSH/SCP         |
       +--------------------------------------------+
                          |
                    Ollama + Qwen
                 http://127.0.0.1:11434
```

- **Windows:** Your authoritative source files, VS Code, Git and GitHub authentication.
- **Vast.ai:** A disposable *execution copy* of selected source directories, the Python interpreter, GPU, and Ollama models.
- **GitHub:** Version control and remote backup for the source repository.
- **Connection:** Supply a new instance ID each time; the CLI discovers the host IP and mapped SSH port.

This is a **copy-and-execute** workflow, not VS Code Remote-SSH or an integrated remote debugger. The standard Python-extension Run button is not the Code Runner Run Code command configured below.

## 2. One-time setup on each Windows computer

Install:

1. [VS Code](https://code.visualstudio.com/)
2. [Git for Windows](https://git-scm.com/downloads/win)
3. [Python for Windows](https://www.python.org/downloads/windows/)
4. [Code Runner VS Code extension](https://marketplace.visualstudio.com/items?itemName=formulahendry.code-runner)
5. Windows OpenSSH client (usually preinstalled)

Verify in Windows PowerShell:

```powershell
git --version
python --version
ssh -V
```

### Clone your GitHub repository

After configuring **this desktop's** GitHub SSH authentication:

```powershell
git clone git@github.com:YOUR_USERNAME/llm-research-lab.git
cd llm-research-lab
```

The repository may live on **any local drive**. The execution script uses `$PSScriptRoot`, so you do not need to hardcode `E:\Dev`.

### Install the Vast.ai CLI in a dedicated virtual environment

```powershell
python -m venv "$HOME\vast-cli-env"
& "$HOME\vast-cli-env\Scripts\python.exe" -m pip install --upgrade vastai
& "$HOME\vast-cli-env\Scripts\vastai.exe" --help
& "$HOME\vast-cli-env\Scripts\vastai.exe" set api-key
```

The API-key prompt hides input. Retrieve your key from [Vast.ai](https://cloud.vast.ai/), and never save it in Git or put it directly into a shell command.

Test authentication:

```powershell
& "$HOME\vast-cli-env\Scripts\vastai.exe" show instances --raw
```

### Generate and register an SSH key

```powershell
New-Item -ItemType Directory -Path "$HOME\.ssh" -Force | Out-Null
ssh-keygen -t ed25519 -f "$HOME\.ssh\vast_gpu"
Get-Content "$HOME\.ssh\vast_gpu.pub" | Set-Clipboard
```

Register the **public** key in your Vast.ai account, and make sure it is enabled for the instance you rent. Protect `vast_gpu` (the private key). If it already exists on a computer, do not overwrite it; use the existing authorized pair or create a differently named key.

## 3. Store your current instance ID locally

Create `config/vast-instance.txt` in the local repository. Put just the numeric ID on one line:

```text
61002212
```

This is an **example**. Replace it with your currently running instance ID. Add to `.gitignore`:

```gitignore
config/vast-instance.txt
```

On each new GPU rental, update this one text file; do not change the Run button configuration.

## 4. Create `Run-Vast.ps1` in the repository root

The following script accepts a Windows path from VS Code, validates that the selected `.py` file belongs to the local project, obtains connection details, uploads the `src`, `experiments`, and `config` directories, and runs the selected file using the remote Python interpreter.

> Assumptions: direct SSH is enabled on Vast.ai, the desktop's public key is authorized, and the remote interpreter is `/venv/main/bin/python`. If you rent an image with a different Python environment, edit `$python` accordingly.

```powershell
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
```

**Security:** `StrictHostKeyChecking=accept-new` trusts first-seen host keys but rejects changed keys. Verify the host fingerprint before first acceptance when feasible. This script does not send your GitHub keys or your Vast.ai API key to the GPU server, but it **does copy files under `config/`**; keep secrets out of that directory. It does not remove stale remote files or automatically retrieve generated output files.

## 5. Set up Code Runner in VS Code

Create `.vscode/settings.json` inside the repository:

```json
{
  "code-runner.executorMap": {
    "python": "powershell.exe -NoProfile -File \"$workspaceRoot\\Run-Vast.ps1\" -Script \"$fullFileName\""
  },
  "code-runner.runInTerminal": true,
  "code-runner.saveFileBeforeRun": true
}
```

Use **Code Runner: Run Code** (`Ctrl+Alt+N`) while a Python file is open. Do not use the Python extension's ordinary **Run Python File** button; that typically invokes the selected local interpreter.

If your version of Code Runner does not expand `$workspaceRoot`, replace that portion with the full local path to `Run-Vast.ps1` for that computer.

## 6. Test remote execution

Create `src/test_gpu.py`:

```python
import torch
from ollama import Client

print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

client = Client(host="http://127.0.0.1:11434")
response = client.chat(
    model="qwen3:4b",
    messages=[
        {"role": "user", "content": "Explain transformer attention briefly."}
    ],
    think=False,
)
print(response.message.content)
```

Open this file in VS Code and choose **Run Code**, or test the PowerShell script directly from the repository root:

```powershell
.\Run-Vast.ps1 -Script "src/test_gpu.py"
```

Expected flow: the CLI discovers the host, SSH connects, SCP uploads code, `/venv/main/bin/python` executes the file, and CUDA and Qwen output appear in the local terminal.

### Remote prerequisites

The Vast.ai image needs PyTorch with CUDA, a running Ollama API at `127.0.0.1:11434`, the `qwen3:4b` model, and the Python Ollama client in the **same environment used by `$python`**:

```bash
/venv/main/bin/python -m pip install ollama
ollama list
curl -fsS http://127.0.0.1:11434/api/tags
```

## 7. Switching to a different GPU

1. Start a fresh Vast.ai instance with your PyTorch/Ollama template.
2. Ensure your desktop's SSH **public** key is authorized.
3. Verify the remote Python interpreter, CUDA, Ollama API, and Qwen model.
4. Replace the number in `config/vast-instance.txt`.
5. Open your local `.py` file and press **Ctrl+Alt+N**.

You do **not** need to hardcode the new public IP or mapped SSH port.

## 8. Common troubleshooting

| Error | Likely cause | Resolution |
|---|---|---|
| `vastai is not recognized` | PowerShell started with `-NoProfile` | Use the full `$HOME\vast-cli-env\Scripts\vastai.exe` path as in this script |
| `Permission denied (publickey)` | Public key not authorized for the instance | Confirm key registration and correct private key |
| `No module named ollama` | Client not installed in `/venv/main` | `/venv/main/bin/python -m pip install ollama` |
| Connection refused on 11434 | Ollama server is down | Check/start `ollama serve` and inspect logs |
| Model not found | Qwen hasn't been downloaded | `ollama pull qwen3:4b` |
| `CUDA available: False` | GPU/PyTorch issue | Run `nvidia-smi` and check PyTorch installation |
| Selected file rejected | Filename outside project, or disallowed characters | Keep scripts inside repository with simple filenames |
| Data not found | Only code directories are copied | Transfer required datasets separately |
| Results disappear with instance | Output written only on remote disk | Copy outputs back or upload to independent storage |

## 9. GitHub workflow on Windows

```powershell
git pull
# Edit code, test against Vast.ai
git status
git add .
git commit -m "Update research experiment"
git push
```

The GPU instance does not require GitHub credentials for this workflow, because you upload the selected code using SSH.

## 10. Important limitations and next steps

- This is **remote script execution**, not local execution against a magically mounted remote Python interpreter.
- Your source remains locally authoritative, but an execution copy runs remotely.
- Local notebook files (`.ipynb`) require a **separate remote-Jupyter-kernel connection** if you want to execute cells remotely while editing the notebook locally.
- Remote-generated output is not automatically downloaded. Consider adding an explicit `scp` retrieval step for `/workspace/llm-research-lab/results`.
- Keep credentials outside the project, and review `src/`, `experiments/`, and `config/` before synchronizing.
- The remote image may change between rentals; record required packages in `requirements.txt` and provision them on each new instance.

**Bottom line:** VS Code and GitHub stay on your Windows computer. The Vast.ai instance is an interchangeable execution server, selected by changing one instance ID.
