"""Shared settings, prompt text, and dev data for the NER experiments.

Keeping these in one place means baseline and Decomposed-QA differ only in
how the task is decomposed, not in model settings, type definitions, or data.
"""

import os

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


def micro_scores(totals: dict[str, int]) -> dict[str, float]:
    """Micro-averaged precision/recall/F1 from summed TP/FP/FN counts."""
    tp, fp, fn = totals["TP"], totals["FP"], totals["FN"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}
