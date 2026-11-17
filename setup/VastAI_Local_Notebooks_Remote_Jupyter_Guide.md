# LLM Research Lab: Run Local VS Code Notebooks on a Vast.ai GPU

**Purpose:** Keep `.ipynb` notebooks in your Windows Git repository, but execute notebook cells using the Python environment, PyTorch/CUDA GPU, and Ollama/Qwen services on whichever Vast.ai instance you rent.

**Platform:** Windows PowerShell, VS Code with Python and Jupyter extensions, Vast.ai PyTorch/Jupyter instance, SSH key authentication.

> **Key distinction:** This workflow uses **VS Code's connection to an existing Jupyter server**, not VS Code Remote-SSH and not `Run-Vast.ps1`. The notebook file stays on your local drive. The kernel executes remotely; its current working directory, files, imports, GPU, and `127.0.0.1` refer to Vast.ai.

## 1. Expected directory layout

On your Windows computer:

```text
E:\Dev\llm-research-lab\
├── config\
│   └── vast-instance.txt     # Your current Vast.ai instance ID; do not commit
├── notebooks\
│   └── 01_test_remote_gpu.ipynb
├── src\
├── experiments\
├── Run-Vast.ps1              # For .py scripts; separate from notebook workflow
└── Connect-Vast-Jupyter.ps1  # Tunnel script provided below
```

Create the folder and instance-ID file if needed:

```powershell
New-Item -ItemType Directory -Force -Path '.\notebooks', '.\config' | Out-Null
Set-Content '.\config\vast-instance.txt' '61002212' # Replace with CURRENT instance ID
```

Add to `.gitignore`:

```gitignore
config/vast-instance.txt
.ipynb_checkpoints/
```

## 2. One-time desktop prerequisites

1. Install **VS Code** and the **Python** and **Jupyter** extensions (Microsoft).
2. Install the Vast.ai CLI into your established desktop virtual environment, if needed:

   ```powershell
   py -m venv "$HOME\vast-cli-env"
   & "$HOME\vast-cli-env\Scripts\python.exe" -m pip install --upgrade vastai
   & "$HOME\vast-cli-env\Scripts\vastai.exe" set api-key
   ```

   Use your own Vast.ai API key; do not put it in this repository.
3. Make sure you have your private SSH key at `$HOME\.ssh\vast_gpu` and that its matching **public** key is authorized for the rented instance. Do not copy private keys into Git.
4. Check that `ssh`, `git`, and the Vast.ai CLI are available:

   ```powershell
   ssh -V
   git --version
   & "$HOME\vast-cli-env\Scripts\vastai.exe" show instances --raw
   ```

If your CLI is a function from your PowerShell profile, the scripts below call the `vastai.exe` executable directly so they also work in `-NoProfile` shells.

## 3. Verify the Jupyter server on Vast.ai

Your Vast.ai PyTorch/Jupyter template usually has a managed Jupyter server listening at **port 8080 using HTTPS**. Connect with your existing SSH method and run:

```bash
jupyter server list
```

You should see the running server URL with its authentication token. **Treat that token as a password; never save it in Git or paste it into chat.**

On Vast.ai, check the remote Python kernel environment:

```bash
/venv/main/bin/python -c "import torch; print('CUDA:', torch.cuda.is_available())"
/venv/main/bin/python -m pip show ipykernel ollama
```

If required, install kernel dependencies in the **remote** environment:

```bash
/venv/main/bin/python -m pip install ipykernel ollama
```

If your image uses a different interpreter, use that interpreter instead of `/venv/main/bin/python`.

## 4. Create a portable PowerShell tunnel script

Save this as `Connect-Vast-Jupyter.ps1` in the repository root:

```powershell
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
```

**Security:** The tunnel is bound to `127.0.0.1` on Windows. Do **not** publicly expose Jupyter's port or Ollama's `11434` port. SSH host-key verification still applies; confirm new fingerprints through a trusted channel on first contact, and investigate any unexpected host-key change.

## 5. Start the tunnel from Windows

In a **local PowerShell terminal** within the project folder:

```powershell
cd 'E:\Dev\llm-research-lab'
.\Connect-Vast-Jupyter.ps1
```

Or explicitly choose a different rented instance:

```powershell
.\Connect-Vast-Jupyter.ps1 -InstanceId 61002212
```

The script queries the **current** public IP and mapped SSH port from Vast.ai each time. No permanent server address is required.

Keep the PowerShell window running. It intentionally does not display a remote shell prompt.

Default tunnel mapping:

```text
Windows 127.0.0.1:18080  --encrypted SSH-->  Vast.ai 127.0.0.1:8080
```

Since the preconfigured Vast.ai Jupyter server uses HTTPS, its local URL is typically **`https://localhost:18080`**, not HTTP. You can confirm this with `jupyter server list` on the remote server.

## 6. Link the local VS Code notebook to the remote Jupyter server

1. Open your **local** folder `E:\Dev\llm-research-lab` in VS Code. **Do not** use Remote-SSH to open the folder remotely.
2. Open or create `notebooks/01_test_remote_gpu.ipynb` on your local computer.
3. Click **Select Kernel** in the notebook's top-right corner.
4. Select **Select Another Kernel** → **Existing Jupyter Server** (wording varies with Jupyter extension version).
5. Enter the tunneled server address: **`https://localhost:18080`**. Supply the server token when prompted, or use the token-bearing URL returned by `jupyter server list`, replacing its remote host/port with `localhost:18080`. Treat the URL as secret.
6. Select the remote **Python 3 (ipykernel)** kernel. If necessary, confirm its interpreter is `/venv/main/bin/python`.

The notebook remains a Windows file; execution is on Vast.ai.

### HTTPS certificate troubleshooting

Vast.ai's preconfigured Jupyter server may present a self-signed certificate. Your browser might allow a one-time exception, but **VS Code's Jupyter extension can still reject the certificate**. Do not assume that a browser exception also configures VS Code.

If VS Code cannot securely connect, use the **loopback-only HTTP Jupyter alternative** in Section 7 rather than disabling global TLS certificate validation.

## 7. Reliable fallback: dedicated HTTP Jupyter server inside the SSH tunnel

This alternative avoids self-signed HTTPS issues while preserving encrypted transport through SSH. Use it **only through the loopback-bound SSH tunnel**, not as a publicly exposed server.

On the **remote Vast.ai Bash terminal**, first verify that port 8888 is unused:

```bash
ss -ltn | grep ':8888 ' || true
```

Start a separate authenticated Jupyter server listening exclusively on remote loopback:

```bash
mkdir -p /workspace/jupyter-runtime
nohup /venv/main/bin/python -m jupyter lab \
  --no-browser --ip=127.0.0.1 --port=8888 --port-retries=0 \
  --ServerApp.allow_root=True \
  --ServerApp.root_dir=/workspace \
  > /workspace/jupyter-runtime/jupyter-8888.log 2>&1 < /dev/null &
```

> Do not set an empty authentication token or disable Jupyter authentication. Jupyter should generate a token. A fresh server process may have a different token each time.

Check:

```bash
/venv/main/bin/python -m jupyter server list
```

On **Windows**, stop the original tunnel with `Ctrl+C` and start one forwarding to 8888:

```powershell
.\Connect-Vast-Jupyter.ps1 -RemotePort 8888 -LocalPort 18888
```

In VS Code, use **`http://127.0.0.1:18888`** as the existing Jupyter server URL, with the generated Jupyter token. Although the URL says HTTP, traffic between your Windows computer and Vast.ai is encrypted by SSH; access is restricted to your local loopback port.

Avoid launching duplicate servers on the same port. If this is a fresh instance, reinstall or activate the appropriate `jupyterlab` and `ipykernel` packages if needed.

## 8. Verify remote execution from a LOCAL notebook

In `notebooks/01_test_remote_gpu.ipynb`, execute:

```python
import os
import socket
import sys
import torch

print('Hostname:', socket.gethostname())
print('Python:', sys.executable)
print('Working directory:', os.getcwd())
print('CUDA available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('GPU:', torch.cuda.get_device_name(0))
    x = torch.randn((1024, 1024), device='cuda')
    print('Matrix location:', (x @ x).device)
```

Then verify local access to **remote** Ollama:

```python
from ollama import Client

# This 'localhost' belongs to the Vast.ai Jupyter kernel, NOT Windows.
client = Client(host='http://127.0.0.1:11434')
response = client.chat(
    model='qwen3:4b',
    messages=[{'role': 'user', 'content': 'Explain CUDA in one sentence.'}],
    think=False,
)
print(response.message.content)
```

If the Python import fails, install it **on Vast.ai in the kernel's interpreter**, not on Windows:

```python
%pip install ollama
```

Restart the remote notebook kernel if necessary.

## 9. Important: Local notebooks, remote files

Your local notebook can contain text and code but its **cells run remotely**, so:

- `Path('data/example.csv')` refers to a directory on Vast.ai, **not** `E:\Dev\llm-research-lab\data` on Windows.
- Python libraries must exist in the Vast.ai kernel's environment.
- Files created by code (`results/output.csv`, checkpoints, images) are saved on Vast.ai unless explicitly downloaded.
- The notebook file itself is saved to the **local Git repository** when you press `Ctrl+S` in VS Code.

For data-heavy research, explicitly upload the required datasets using `scp`, `rsync` where supported, object storage, or your existing `Run-Vast.ps1` synchronization logic. To bring results back, download them via `scp` or your chosen storage service. Do not assume local and remote folders share a filesystem.

Example of copying a local dataset to Vast.ai using the dynamically discovered SSH endpoint is possible, but do not hardcode an old IP or port. You can extend the portable connection script to handle uploads/downloads after the notebook connection is proven.

## 10. Switching GPU instances

When renting another Vast.ai host:

1. Ensure your new instance has Jupyter, a compatible Python kernel, GPU drivers/PyTorch, Ollama, and Qwen available.
2. Ensure the SSH public key for this Windows desktop is registered on that instance.
3. Replace the numeric value in `config/vast-instance.txt`, or supply `-InstanceId` explicitly.
4. Stop the old SSH tunnel (`Ctrl+C`), run `Connect-Vast-Jupyter.ps1` again, and reconnect the existing Jupyter server in VS Code.
5. Re-run the GPU and Ollama checks. The notebook files themselves need no changes.

The Jupyter authentication token may change with a new server; obtain the new one using `jupyter server list`.

## 11. Troubleshooting

| Symptom | What to check |
|---|---|
| `Missing config/vast-instance.txt` | Create it under repo `config/`, or pass `-InstanceId`. |
| `vastai.exe` not found | Verify `$HOME\vast-cli-env\Scripts\vastai.exe`; reinstall if necessary. |
| `Permission denied (publickey)` | The corresponding SSH public key may not be authorized on the new instance. |
| SSH tunnel immediately exits | Wrong mapped SSH port, stopped instance, occupied local port, or host-key problem. |
| Port `18080` already in use | Use `-LocalPort 18081` and update the VS Code URL. |
| VS Code rejects HTTPS certificate | Use the dedicated HTTP-over-SSH server (Section 7). |
| Jupyter token rejected | Obtain the active token from `jupyter server list`; check the correct server and port. |
| Kernel is local Windows Python | Re-select the **Existing Jupyter Server** and its remote kernel. |
| `ModuleNotFoundError` | Install the package into the remote kernel (`%pip install ...`). |
| `torch.cuda.is_available()` false | Check `nvidia-smi`, kernel interpreter, and remote PyTorch build. |
| Ollama connection refused | On Vast.ai check `curl http://127.0.0.1:11434/api/tags`; start `ollama serve` if needed. |
| Qwen model unavailable | Run `ollama list`; pull the appropriate model if not present. |
| Notebook can't read a Windows file | Upload the dataset to remote storage or rewrite the notebook to use a remote-accessible location. |

## 12. Security and persistence checklist

- Keep Vast.ai API keys, SSH private keys, and Jupyter tokens outside GitHub.
- Use SSH port forwarding bound to Windows loopback, not a publicly exposed notebook endpoint.
- Verify host keys on first connection and investigate unexpected changes.
- Do not disable TLS verification globally to work around a self-signed Jupyter certificate.
- Save notebooks in the local `notebooks/` directory and commit them to GitHub.
- Back up any remote-generated results before terminating Vast.ai instances.

## Daily quick-start

```powershell
# On Windows, from your local repository
cd 'E:\Dev\llm-research-lab'
Get-Content '.\config\vast-instance.txt'
.\Connect-Vast-Jupyter.ps1
```

Keep that tunnel terminal open. In **local VS Code**, open `notebooks/*.ipynb` and select the existing remote Jupyter server at `https://localhost:18080` (or `http://localhost:18888` if using the dedicated HTTP tunnel). All notebook execution will then take place on Vast.ai.
