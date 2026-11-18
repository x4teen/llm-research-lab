"""Shared settings, prompt text, data, and helpers for the NER experiments.

Keeping these in one place means baseline and Decomposed-QA differ only in
how the task is decomposed, not in model settings, type definitions, or data.

Third-party packages used only by some scripts (datasets) are imported inside
the functions that need them, so importing this module stays lightweight.
"""

import importlib
import json
import os
import subprocess
import sys

MODEL = "qwen3:4b"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
LABELS = ("Person", "Organization", "Location")
OPTIONS = {"temperature": 0, "num_predict": 256}

TYPE_DEFINITIONS = (
    "Entity types:\n"
    "- Person: names of specific people (not job titles or pronouns).\n"
    "- Organization: companies, institutions, agencies, teams.\n"
    "- Location: cities, countries, regions, landmarks.\n"
)

# Small development dataset — not the held-out benchmark
DATASET = [
    {
        "id": "dev_001",
        "text": "Microsoft CEO Satya Nadella visited London.",
        "gold": {
            "Microsoft": "Organization",
            "Satya Nadella": "Person",
            "London": "Location",
        },
    },
    {
        "id": "dev_002",
        "text": "Tim Cook met Sundar Pichai at Google.",
        "gold": {
            "Tim Cook": "Person",
            "Sundar Pichai": "Person",
            "Google": "Organization",
        },
    },
    {
        "id": "dev_003",
        "text": "Amazon opened an office in Berlin.",
        "gold": {
            "Amazon": "Organization",
            "Berlin": "Location",
        },
    },
    {
        "id": "dev_004",
        "text": "Marie Curie worked in Paris.",
        "gold": {
            "Marie Curie": "Person",
            "Paris": "Location",
        },
    },
    {
        "id": "dev_005",
        "text": "The engineer reviewed the report yesterday.",
        "gold": {},
    },
]


def ensure_package(import_name: str, pip_name: str | None = None) -> None:
    """Install a package into the running interpreter if it is missing.

    On Vast.ai via Run-Vast.ps1 the running interpreter is /venv/main/bin/python.
    """
    try:
        importlib.import_module(import_name)
    except ImportError:
        package = pip_name or import_name
        print(f"Installing missing package: {package} into {sys.executable}", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--no-input", package]
        )
        # Make the freshly installed package importable in this process.
        importlib.invalidate_caches()


# CoNLL-2003. tner/conll2003 ships a loading script, which datasets>=4.0 no
# longer runs; the Hub's auto-converted Parquet branch loads on every version.
CONLL_DATASET_ID = "tner/conll2003"
CONLL_REVISION = "refs/convert/parquet"


def load_conll():
    """Load CoNLL-2003 (train/validation/test), installing datasets if needed."""
    ensure_package("datasets")
    from datasets import load_dataset

    return load_dataset(CONLL_DATASET_ID, revision=CONLL_REVISION)


def load_conll_label_map() -> dict[int, str]:
    """Return {tag_id: tag_name}; CoNLL tags are stored as integers."""
    ensure_package("datasets")  # provides huggingface_hub
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(CONLL_DATASET_ID, "dataset/label.json", repo_type="dataset")
    with open(path, encoding="utf-8") as file:
        label2id = json.load(file)
    return {idx: name for name, idx in label2id.items()}


def micro_scores(totals: dict[str, int]) -> dict[str, float]:
    """Micro-averaged precision/recall/F1 from summed TP/FP/FN counts."""
    tp, fp, fn = totals["TP"], totals["FP"], totals["FN"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}
