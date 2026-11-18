
#!/usr/bin/env bash

# ==========================================================
# LLM RESEARCH LAB - VAST.AI AUTOMATIC STARTUP
#
# PyTorch + CUDA + Jupyter + SSH + Ollama + Qwen3
#
# Python environment: /venv/main
# Ollama API:         http://127.0.0.1:11434
# Project directory:  /workspace/llm-research-lab
# ==========================================================

mkdir -p /workspace

# Run initialization asynchronously so the original
# Vast.ai entrypoint can start Jupyter and SSH.
(
    set -Eeuo pipefail

    echo "======================================"
    echo "LLM Research Lab initialization"
    date -u
    echo "======================================"

    PYTHON="/venv/main/bin/python"
    OLLAMA_URL="http://127.0.0.1:11434"
    MODEL="qwen3:4b"

    export OLLAMA_HOST="127.0.0.1:11434"

    # ------------------------------------------
    # 1. Prepare research directories
    # ------------------------------------------

    mkdir -p /workspace/llm-research-lab
    mkdir -p /workspace/llm-research-lab/notebooks
    mkdir -p /workspace/llm-research-lab/results

    # ------------------------------------------
    # 2. Check Python and PyTorch/CUDA
    # ------------------------------------------

    echo "[1/6] Checking Python and CUDA..."

    if [ ! -x "$PYTHON" ]; then
        echo "ERROR: Python not found at $PYTHON"
        exit 1
    fi

    "$PYTHON" -c '
import sys
print("Python:", sys.executable)
try:
    import torch
    print("PyTorch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))
except Exception as exc:
    print("PyTorch verification failed:", exc)
'

    # ------------------------------------------
    # 3. Install Python Ollama client
    # ------------------------------------------

    echo "[2/6] Checking Python Ollama package..."

    if ! "$PYTHON" -c "import ollama" >/dev/null 2>&1; then
        echo "Installing Python Ollama client..."

        "$PYTHON" -m pip install \
            --no-input \
            ollama
    fi

    "$PYTHON" -c '
from ollama import Client
print("Python Ollama client: OK")
'

    # ------------------------------------------
    # 4. Install Ollama server
    # ------------------------------------------

    echo "[3/6] Checking Ollama server installation..."

    if ! command -v ollama >/dev/null 2>&1; then

        echo "Installing Ollama server..."

        curl -fsSL --retry 3 \
            https://ollama.com/install.sh \
            -o /tmp/ollama-install.sh

        bash /tmp/ollama-install.sh
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

    if ! curl -fsS "$OLLAMA_URL/api/tags" \
        >/dev/null 2>&1; then

        echo "Launching Ollama..."

        nohup ollama serve \
            >> /workspace/ollama-server.log \
            2>&1 < /dev/null &
    fi

    echo "[5/6] Waiting for Ollama API..."

    READY=0

    for i in $(seq 1 60); do
        if curl -fsS "$OLLAMA_URL/api/tags" \
            >/dev/null 2>&1; then
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
    echo "======================================"

    ollama list
    date -u

) >> /workspace/ollama-setup.log 2>&1 < /dev/null &

# Preserve the original Vast.ai startup process.
exec entrypoint.sh
