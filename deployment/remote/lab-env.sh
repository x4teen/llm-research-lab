#!/usr/bin/env bash
# ==========================================================
# LLM RESEARCH LAB - PORTABLE REMOTE PYTHON ENVIRONMENT
#
# Works on any Linux server (any Vast.ai image, or none):
#   1. Finds a usable Python >= 3.10.
#   2. If that Python cannot accept pip installs (system Python,
#      PEP 668 "externally managed", read-only site-packages),
#      creates <project>/.venv with --system-site-packages so the
#      image's CUDA-enabled PyTorch is still visible.
#   3. Ensures pip, then installs requirements.txt only when it
#      changed (hash stamp), so repeat runs are fast.
#
# Usage (from anywhere):
#   bash deployment/remote/lab-env.sh setup            # prepare only
#   bash deployment/remote/lab-env.sh python           # print interpreter path
#   bash deployment/remote/lab-env.sh run SCRIPT [ARGS...]
#
# Override the interpreter choice with LAB_PYTHON=/path/to/python.
# ==========================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
STATE_DIR="$PROJECT_DIR/.lab-env"
LOCAL_VENV="$PROJECT_DIR/.venv"
REQUIREMENTS="$PROJECT_DIR/requirements.txt"
MIN_PY="3.10"

log() { echo "[lab-env] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# Python >= MIN_PY that actually runs.
python_ok() {
    "$1" -c "import sys; sys.exit(0 if sys.version_info >= (${MIN_PY/./,}) else 1)" \
        >/dev/null 2>&1
}

# True if pip may install into this interpreter's environment.
python_installable() {
    "$1" - <<'PY' >/dev/null 2>&1
import os, sys, sysconfig
in_venv = sys.prefix != sys.base_prefix
is_conda = os.path.isdir(os.path.join(sys.prefix, "conda-meta"))
managed = os.path.exists(
    os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED")
)
purelib = sysconfig.get_path("purelib")
writable = os.access(purelib if os.path.isdir(purelib) else sys.prefix, os.W_OK)
sys.exit(0 if writable and (in_venv or is_conda or not managed) else 1)
PY
}

find_base_python() {
    local candidates=()
    [ -n "${LAB_PYTHON:-}" ] && candidates+=("$LAB_PYTHON")
    candidates+=("$LOCAL_VENV/bin/python")         # created on an earlier run
    candidates+=("/venv/main/bin/python")          # Vast.ai PyTorch images
    [ -n "${VIRTUAL_ENV:-}" ] && candidates+=("$VIRTUAL_ENV/bin/python")
    [ -n "${CONDA_PREFIX:-}" ] && candidates+=("$CONDA_PREFIX/bin/python")
    candidates+=("/opt/conda/bin/python")          # conda-based images
    candidates+=("python3" "python")

    local c path
    for c in "${candidates[@]}"; do
        path="$(command -v "$c" 2>/dev/null || true)"
        [ -n "$path" ] || continue
        if python_ok "$path"; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

create_local_venv() {
    local base="$1"
    log "Creating $LOCAL_VENV from $base (system site-packages visible)"
    if ! "$base" -m venv --system-site-packages "$LOCAL_VENV" >&2; then
        # Debian/Ubuntu split venv into a separate package.
        if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
            local ver
            ver="$("$base" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
            log "Installing python${ver}-venv via apt-get"
            apt-get update -qq >&2
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
                "python${ver}-venv" >&2 \
                || DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv >&2
            rm -rf "$LOCAL_VENV"
            "$base" -m venv --system-site-packages "$LOCAL_VENV" >&2
        else
            die "Cannot create a virtual environment with $base. Install python3-venv or set LAB_PYTHON."
        fi
    fi
}

resolve_python() {
    local base
    base="$(find_base_python)" \
        || die "No Python >= $MIN_PY found. Install one or set LAB_PYTHON."

    if python_installable "$base"; then
        echo "$base"
        return 0
    fi

    create_local_venv "$base"
    python_installable "$LOCAL_VENV/bin/python" \
        || die "Created $LOCAL_VENV but it is not writable."
    echo "$LOCAL_VENV/bin/python"
}

ensure_pip() {
    local py="$1"
    if ! "$py" -m pip --version >/dev/null 2>&1; then
        log "pip missing; bootstrapping with ensurepip"
        "$py" -m ensurepip --upgrade >&2 \
            || die "pip unavailable for $py and ensurepip failed."
    fi
}

ensure_requirements() {
    local py="$1"
    [ -f "$REQUIREMENTS" ] || { log "No requirements.txt; skipping installs"; return 0; }

    local key stamp want
    key="$(echo "$py" | cksum | cut -d' ' -f1)"
    stamp="$STATE_DIR/requirements-$key.stamp"
    want="$(cksum < "$REQUIREMENTS" | cut -d' ' -f1)"

    if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$want" ]; then
        return 0
    fi

    log "Installing requirements into $py"
    "$py" -m pip install --no-input --disable-pip-version-check \
        -r "$REQUIREMENTS" >&2
    echo "$want" > "$stamp"
}

setup() {
    mkdir -p "$STATE_DIR"

    # Serialize with any concurrent setup (e.g. the on-start script).
    if command -v flock >/dev/null 2>&1; then
        exec 9>"$STATE_DIR/lock"
        flock 9
    fi

    local py
    py="$(resolve_python)"
    ensure_pip "$py"
    ensure_requirements "$py"
    echo "$py" > "$STATE_DIR/python"
    echo "$py"
}

cmd="${1:-setup}"
shift || true

case "$cmd" in
    setup)
        py="$(setup)"
        log "Python ready: $py"
        ;;
    python)
        setup
        ;;
    run)
        [ $# -ge 1 ] || die "Usage: lab-env.sh run SCRIPT [ARGS...]"
        py="$(setup)"
        log "Python: $py"
        cd "$PROJECT_DIR"
        exec "$py" "$@"
        ;;
    *)
        die "Unknown command: $cmd (use setup | python | run)"
        ;;
esac
