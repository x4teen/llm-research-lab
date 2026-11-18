# Vast.ai Template Creation Notes

**Project:** LLM Research Lab  
**Template name:** `LLM Research Lab - PyTorch Jupyter Ollama Qwen`  
**Purpose:** Launch a fresh, replaceable NVIDIA GPU instance that supports remote Python execution from local VS Code, remote Jupyter kernels, Ollama, and Qwen3 4B.

> This is a **new-template creation guide**, not a recovery guide. Keep your known-good startup script separately as `deployment/vast/onstart.sh`. Do not paste credentials into the template, script, or Git repository.

## 1. Prerequisites

- Vast.ai account with billing enabled and an SSH **public** key registered.
- A tested `deployment/vast/onstart.sh` from this project.
- Local Vast.ai CLI configured with an API key, and a working SSH private key on each trusted desktop.
- The local `llm-research-lab` Git repository, including `Run-Vast.ps1` and `config/vast-instance.txt` (the latter stays local and is ignored by Git).

## 2. Create the template

1. Sign in to [Vast.ai Console](https://cloud.vast.ai/).
2. Open **Templates** and create a new template (or duplicate the official **PyTorch** template to preserve its defaults).
3. Give it the name shown above; set **Visibility: Private**.
4. Choose a known-good **Vast.ai PyTorch image** that provides Python, PyTorch, CUDA, Jupyter, and SSH. **Record the exact Docker image and tag** in the inventory below; do not rely on `latest`.
5. Select the **Jupyter Notebook + SSH** launch mode (wording may vary by console version).
6. Set disk allocation and ports as below. Configure any storage volume separately if the selected host supports it.
7. Paste the **entire content** of `deployment/vast/onstart.sh` into the **On-start Script** field. Confirm that its final call preserves the original `entrypoint.sh` for the chosen image.
8. Save the template. A template edit affects **new instances**, not ones already running.

### Recommended settings

| Field | Starting value | Notes |
|---|---|---|
| Template name | `LLM Research Lab - PyTorch Jupyter Ollama Qwen` | Private |
| Docker image | *Record exact tested image:tag* | Keep Python/CUDA compatibility reproducible |
| Launch mode | Jupyter Notebook + SSH | Preserve the image's normal service startup |
| GPU | One compatible NVIDIA GPU | Choose when renting; 24 GB VRAM is comfortable for Qwen3 4B |
| Container disk | 30-50 GB | Allow room for CUDA/Python tooling, caches, and model downloads |
| Jupyter | Image/template default (historically port 8080) | Confirm actual protocol, token, and port after deploy |
| SSH | Container port 22 with host-mapped TCP port | Mapped public port may change each instance |
| Ollama API | `127.0.0.1:11434` | **Do not expose publicly** |
| Default model | `qwen3:4b` | Pulled if missing by startup script |
| Remote Python | `/venv/main/bin/python` | Confirm this interpreter exists on the selected image |
| Workspace | `/workspace/llm-research-lab` | Instance disk is not automatically permanent |

**Storage warning:** A Vast.ai local volume is tied to a particular physical host. A new GPU instance on another host does not inherit that volume or any model downloads. Keep code on your local computer/GitHub and independently back up important outputs. If using a volume, verify its mount location and lifecycle before relying on it.

## 3. Requirements for `onstart.sh`

The accompanying script should:

1. Preserve Jupyter/SSH startup by invoking the image's original `entrypoint.sh` correctly.
2. Run custom installation asynchronously so that an Ollama download does not block Jupyter/SSH startup.
3. Check that `/venv/main/bin/python` exists, and verify PyTorch/CUDA without replacing the image's CUDA-enabled PyTorch build.
4. Install the `ollama` **Python client** into the exact interpreter used by `Run-Vast.ps1`, if missing.
5. Install the Ollama **server** if missing, and start it bound to `127.0.0.1:11434`.
6. Wait for `http://127.0.0.1:11434/api/tags` to respond before pulling `qwen3:4b`.
7. Avoid unnecessary reinstallation or model downloads when the instance already has them.
8. Log setup to `/workspace/ollama-setup.log` and Ollama output to `/workspace/ollama-server.log`.
9. Exit with a clear error in the logs if a required step fails.

**Important:** Verify the chosen image actually uses `entrypoint.sh` and the On-start execution convention before deploying. Do not blindly transplant the script to a different Docker image. An On-start script may be invoked through Bash without needing `chmod +x` in the template editor.

## 4. Rent a fresh instance

1. Open **Templates**, select this saved template, and choose the action to deploy/rent with it.
2. Filter offers by GPU, VRAM, reliability, location, and available disk.
3. Select **on-demand** if you don't want interruptible capacity.
4. Confirm that **your private template** is attached to the offer before clicking **Rent**.
5. Wait for the instance status to become **running**; note the **new instance ID**.
6. Keep the old instance until you've saved any work that exists only on its disk.

A fresh instance can have a different **ID, public IP, and externally mapped SSH port**.

## 5. Verify the instance from SSH

On the remote Linux terminal:

```bash
nvidia-smi
/venv/main/bin/python -c 'import torch; print(torch.cuda.is_available())'
/venv/main/bin/python -c 'from ollama import Client; print("Python Ollama client ready")'

tail -n 60 /workspace/ollama-setup.log
curl -fsS http://127.0.0.1:11434/api/tags
ollama list
ollama run qwen3:4b 'Say hello from this GPU.'
ollama ps
jupyter server list
```

**Expected:** CUDA reports `True`; the Python Ollama client imports; Ollama's API responds; `qwen3:4b` appears in `ollama list`; inference succeeds. `ollama ps` only shows models currently loaded and can be empty before inference or after an idle timeout.

If something fails, check:

```bash
tail -n 100 /workspace/ollama-setup.log
tail -n 100 /workspace/ollama-server.log
```

## 6. Connect from any Windows desktop

Install/configure the Vast.ai CLI and register that desktop's SSH **public** key. Your local project remains authoritative; remote servers are replaceable execution targets.

Update the instance ID in the **local** file:

```text
config/vast-instance.txt
```

Put only the current numeric instance ID there, for example `12345678` (illustrative). Ensure the file is ignored by Git.

### Run local `.py` code on remote Python/GPU

In a PowerShell terminal at the repository root:

```powershell
.\Run-Vast.ps1 -Script 'src/test_gpu.py'
```

Your script should query the Vast.ai CLI, discover the current public IP and mapped SSH port, copy the required source files, then execute the chosen script using `/venv/main/bin/python`. It must not require hardcoded IP addresses.

### Use local notebooks with the remote Jupyter kernel

1. Start the project's `Connect-Vast-Jupyter.ps1` tunnel, which discovers the current instance via `config/vast-instance.txt`.
2. Keep the tunnel terminal running. Use the **local forwarded port printed by the script** (previously `18080`, not `8080`).
3. In local VS Code, open a `.ipynb` file from `notebooks/`.
4. Select **Existing Jupyter Server**, enter the tunneled URL and authenticate with the current Jupyter token, then choose the remote Python kernel.
5. Test `torch.cuda.is_available()`. Notebook contents stay on Windows, but filesystem calls inside cells operate on the **remote Linux machine**.

A remote Jupyter endpoint may use HTTPS with a self-signed certificate. Inspect the Jupyter extension's Output logs if kernel discovery hangs; prefer a correctly trusted endpoint instead of disabling certificate checking globally.

## 7. Repository layout and security

```text
llm-research-lab/
  deployment/
    vast/
      onstart.sh
      template-notes.md
  config/
    vast-instance.txt    # local only; ignore in Git
  notebooks/
  src/
  experiments/
  results/
  Run-Vast.ps1
  Connect-Vast-Jupyter.ps1
```

- Commit `onstart.sh`, `template-notes.md`, source code, and notebooks after reviewing for secrets.
- **Never commit** Vast.ai API keys, SSH private keys, Jupyter tokens, `.env` files, or credentials embedded in scripts.
- Do not assume `/workspace` is persistent just because the directory exists.
- Before destroying a Pod/instance, push local work and transfer any **remote-only** results to durable storage.

## 8. Template inventory — fill in after the first successful deployment

| Item | Verified value |
|---|---|
| Template name | LLM Research Lab - PyTorch Jupyter Ollama Qwen |
| Exact Docker image/tag | ______________________________ |
| Python path | `/venv/main/bin/python` (verify) |
| Jupyter port / HTTP or HTTPS | ______________________________ |
| Jupyter startup mechanism | ______________________________ |
| SSH launch mode | Jupyter + SSH |
| Container disk allocation | ______________________________ |
| Additional storage and mount | ______________________________ |
| Ollama version | ______________________________ |
| Qwen model digest/version | ______________________________ |
| Date last verified | ______________________________ |

## 9. Troubleshooting quick reference

| Symptom | Check |
|---|---|
| `ModuleNotFoundError: ollama` | Install the **Python client** into `/venv/main/bin/python`, not a different `python` |
| Ollama CLI exists but no models | Use `ollama list`; inspect startup log; run `ollama pull qwen3:4b` if missing |
| `ollama ps` empty | Normal unless a model is currently loaded |
| Ollama API connection refused | Check server log and `curl http://127.0.0.1:11434/api/tags` |
| Jupyter unavailable | Confirm original `entrypoint.sh` ran, actual Jupyter port/protocol, and SSH tunnel |
| VS Code stuck detecting kernels | Check Jupyter token, certificate, registered kernels, and extension logs |
| SSH connection fails | Recheck instance ID, mapped port, and authorized public key |
| Docker build says no space left on device | Could be the **host's** Docker build storage; try another host before blaming On-start commands |
| New instance lacks notebooks/results | Restore from local GitHub or independent backup; ephemeral disks are not backups |

---

**Operating principle:** The template provisions a disposable compute environment; GitHub/local storage preserves the project. Keep `deployment/vast/onstart.sh` as the version-controlled source of truth for your Vast.ai startup configuration.
