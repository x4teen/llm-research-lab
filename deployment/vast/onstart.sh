#!/usr/bin/env bash

# ==========================================================
# LLM RESEARCH LAB - PORTABLE AUTOMATIC STARTUP
#
# Python + (optional) PyTorch/CUDA + Ollama + Qwen3
#
# Designed for any Vast.ai image/host. Nothing below assumes a
# specific interpreter path or directory layout:
#   - Workspace: /workspace if writable, else $HOME
#   - Python:    same selection rules as deployment/remote/lab-env.sh
#                (/venv/main, conda, or system python3; a project
#                .venv is created when the base Python is
#                externally managed / not writable)
#   - Ollama API: http://127.0.0.1:11434 (loopback only)
#
# This file is pasted into the template's On-start Script field,
# so it must stay self-contained (the repo is not on the server yet).
# ==========================================================

if [ -d /workspace ] || mkdir -p /workspace 2>/dev/null; then
    if [ -w /workspace ]; then WORKSPACE=/workspace; else WORKSPACE="$HOME"; fi
else
    WORKSPACE="$HOME"
fi
PROJECT_DIR="$WORKSPACE/llm-research-lab"
SETUP_LOG="$WORKSPACE/ollama-setup.log"
SERVER_LOG="$WORKSPACE/ollama-server.log"
export WORKSPACE PROJECT_DIR SERVER_LOG

# Run initialization asynchronously so the image's own
# entrypoint can start Jupyter and SSH.
(
    set -Eeuo pipefail

    echo "======================================"
    echo "LLM Research Lab initialization"
    date -u
    echo "Workspace: $WORKSPACE"
    echo "======================================"

    OLLAMA_URL="http://127.0.0.1:11434"
    MODEL="qwen3:4b"
    LOCAL_VENV="$PROJECT_DIR/.venv"

    export OLLAMA_HOST="127.0.0.1:11434"

    as_root() {
        if [ "$(id -u)" = "0" ]; then "$@"
        elif command -v sudo >/dev/null 2>&1; then sudo -n "$@"
        else return 1
        fi
    }

    apt_install() {
        command -v apt-get >/dev/null 2>&1 || return 1
        as_root apt-get update -qq || true
        DEBIAN_FRONTEND=noninteractive as_root apt-get install -y -qq "$@"
    }

    # ------------------------------------------
    # 1. Prepare research directories
    # ------------------------------------------

    mkdir -p "$PROJECT_DIR/notebooks" "$PROJECT_DIR/results"

    # ------------------------------------------
    # 2. Select Python (same rules as lab-env.sh)
    # ------------------------------------------

    echo "[1/6] Selecting Python..."

    python_ok() {
        "$1" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" \
            >/dev/null 2>&1
    }

    python_installable() {
        "$1" - <<'PY' >/dev/null 2>&1
import os, sys, sysconfig
in_venv = sys.prefix != sys.base_prefix
is_conda = os.path.isdir(os.path.join(sys.prefix, "conda-meta"))
managed = os.path.exists(os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED"))
purelib = sysconfig.get_path("purelib")
writable = os.access(purelib if os.path.isdir(purelib) else sys.prefix, os.W_OK)
sys.exit(0 if writable and (in_venv or is_conda or not managed) else 1)
PY
    }

    PYTHON=""
    for c in "${LAB_PYTHON:-}" "$LOCAL_VENV/bin/python" /venv/main/bin/python \
             "${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}" /opt/conda/bin/python \
             python3 python; do
        [ -n "$c" ] || continue
        p="$(command -v "$c" 2>/dev/null || true)"
        if [ -n "$p" ] && python_ok "$p"; then PYTHON="$p"; break; fi
    done

    if [ -z "$PYTHON" ]; then
        echo "No Python >= 3.10 found; trying to install python3..."
        apt_install python3 python3-venv python3-pip || true
        PYTHON="$(command -v python3 || true)"
        [ -n "$PYTHON" ] && python_ok "$PYTHON" \
            || { echo "ERROR: no usable Python >= 3.10"; exit 1; }
    fi

    if ! python_installable "$PYTHON"; then
        echo "Base Python $PYTHON is not pip-installable; creating $LOCAL_VENV"
        if ! "$PYTHON" -m venv --system-site-packages "$LOCAL_VENV"; then
            ver="$("$PYTHON" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
            apt_install "python${ver}-venv" || apt_install python3-venv
            rm -rf "$LOCAL_VENV"
            "$PYTHON" -m venv --system-site-packages "$LOCAL_VENV"
        fi
        PYTHON="$LOCAL_VENV/bin/python"
    fi

    if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
        "$PYTHON" -m ensurepip --upgrade
    fi

    mkdir -p "$PROJECT_DIR/.lab-env"
    echo "$PYTHON" > "$PROJECT_DIR/.lab-env/python"

    "$PYTHON" -c '
import sys
print("Python:", sys.executable, sys.version.split()[0])
try:
    import torch
    print("PyTorch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))
except Exception as exc:
    print("PyTorch not available / verification failed:", exc)
'

    # ------------------------------------------
    # 3. Install core Python packages
    #    (full requirements.txt is installed by lab-env.sh
    #     on the first Run-Vast.ps1 call)
    # ------------------------------------------

    echo "[2/6] Checking Python packages (ollama, datasets)..."

    for pkg in ollama datasets; do
        if ! "$PYTHON" -c "import $pkg" >/dev/null 2>&1; then
            echo "Installing $pkg..."
            "$PYTHON" -m pip install --no-input --disable-pip-version-check "$pkg"
        fi
    done

    "$PYTHON" -c '
import datasets
from ollama import Client
print("Python Ollama client: OK")
print("Python datasets package:", datasets.__version__)
'

    # ------------------------------------------
    # 4. Install Ollama server
    # ------------------------------------------

    echo "[3/6] Checking Ollama server installation..."

    if ! command -v ollama >/dev/null 2>&1; then
        echo "Installing Ollama server..."

        command -v curl >/dev/null 2>&1 || apt_install curl ca-certificates
        # The installer unpacks .tar.zst archives on recent releases.
        command -v zstd >/dev/null 2>&1 || apt_install zstd || true

        curl -fsSL --retry 3 \
            https://ollama.com/install.sh \
            -o /tmp/ollama-install.sh

        as_root bash /tmp/ollama-install.sh
    fi

    if ! command -v ollama >/dev/null 2>&1; then
        echo "ERROR: Ollama executable not found."
        exit 1
    fi

    echo "Ollama executable: $(command -v ollama)"

    # ------------------------------------------
    # 5. Start Ollama API
    # ------------------------------------------

    echo "[4/6] Starting Ollama API if necessary..."

    if ! curl -fsS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
        echo "Launching Ollama..."
        nohup ollama serve >> "$SERVER_LOG" 2>&1 < /dev/null &
    fi

    echo "[5/6] Waiting for Ollama API..."

    READY=0
    for i in $(seq 1 60); do
        if curl -fsS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
            READY=1
            break
        fi
        sleep 2
    done

    if [ "$READY" -ne 1 ]; then
        echo "ERROR: Ollama API did not become ready."
        exit 1
    fi

    echo "Ollama API: READY"

    # ------------------------------------------
    # 6. Ensure Qwen model is available
    # ------------------------------------------

    echo "[6/6] Checking model $MODEL..."

    if ! ollama show "$MODEL" >/dev/null 2>&1; then
        echo "Downloading $MODEL..."
        ollama pull "$MODEL"
    else
        echo "$MODEL already downloaded."
    fi

    echo ""
    echo "======================================"
    echo "LLM Research Lab READY"
    echo "Python: $PYTHON"
    echo "======================================"

    ollama list
    date -u

) >> "$SETUP_LOG" 2>&1 < /dev/null &

# Hand control to the image's own startup process, if it has one.
# (Vast.ai PyTorch images use entrypoint.sh; other images may not.)
if command -v entrypoint.sh >/dev/null 2>&1; then
    exec entrypoint.sh
fi
