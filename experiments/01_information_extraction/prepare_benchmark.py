
"""Prepare a frozen 100-example CoNLL-2003 test benchmark.

Uses a fixed random seed and preserves gold character spans.
Does not run a language model or display test sentences.

The `datasets` package is installed automatically into the running
interpreter if missing (see ner_common.ensure_package), so this runs on a
fresh Vast.ai instance via Run-Vast.ps1.
"""

import json
import random
from pathlib import Path

from bio_to_spans import bio_to_char_spans
from ner_common import (
    CONLL_DATASET_ID as DATASET_ID,
    CONLL_REVISION as REVISION,
    load_conll,
    load_conll_label_map,
)

SEED = 42
SAMPLE_SIZE = 100

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT_ROOT / "data" / "evaluation" / "conll2003_test_100.json"


def main():
    # Never silently replace an existing frozen benchmark.
    if OUTPUT.exists():
        raise FileExistsError(
            f"Benchmark already exists: {OUTPUT}\n"
            "Keep the existing file to preserve reproducibility."
        )

    # Installs `datasets` (and huggingface_hub) if missing.
    dataset = load_conll()["test"]
    id2label = load_conll_label_map()

    rng = random.Random(SEED)
    indices = sorted(
        rng.sample(range(len(dataset)), SAMPLE_SIZE)
    )

    records = []

    for index in indices:
        sample = dataset[index]

        tags = [
            id2label[tag]
            for tag in sample["tags"]
        ]

        text, entities = bio_to_char_spans(
            sample["tokens"], tags
        )

        # Check each gold span before saving.
        for entity in entities:
            assert (
                text[entity["start"]:entity["end"]]
                == entity["text"]
            )

        records.append({
            "id": f"conll2003_test_{index:05d}",
            "source_index": index,
            "text": text,
            "gold": entities,
        })

    benchmark = {
        "dataset": DATASET_ID,
        "revision": REVISION,
        "split": "test",
        "seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "text_policy": "single-space token joining",
        "span_policy": "zero-based, end-exclusive",
        "label_set": ["PER", "ORG", "LOC", "MISC"],
        "records": records,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "x", encoding="utf-8") as file:
        json.dump(
            benchmark,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("Benchmark created successfully")
    print(f"Source split size: {len(dataset)}")
    print(f"Selected examples: {len(records)}")
    print(f"Random seed: {SEED}")
    print(f"Unique IDs: {len(set(indices))}")
    print(f"Saved to: {OUTPUT}")
    print("No model predictions generated.")


if __name__ == "__main__":
    main()
