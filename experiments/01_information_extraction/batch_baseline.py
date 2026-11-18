"""Single-question NER baseline over the dev dataset.

Run: python batch_baseline.py
Shares model settings, type definitions, and data with decomposed_qa.py via
ner_common.py so the two conditions differ only in task decomposition.
"""

import json
import time
from pathlib import Path

from ollama import Client

from evaluation import evaluate_ner
from ner_common import (
    DATASET,
    LABELS,
    MODEL,
    OLLAMA_HOST,
    OPTIONS,
    TYPE_DEFINITIONS,
    micro_scores,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SYSTEM = (
    "You extract named entities from a sentence.\n"
    + TYPE_DEFINITIONS
    + "List every entity of these types, copied exactly as it appears in the "
    'sentence, with its type. Reply as {"entities": [{"text": ..., "type": ...}]}; '
    "use [] if there are none."
)

# Constrains decoding to this structure, so no free-form keys can appear.
ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "type": {"type": "string", "enum": list(LABELS)},
                },
                "required": ["text", "type"],
            },
        }
    },
    "required": ["entities"],
}


def parse_prediction(raw: str, text: str) -> dict[str, str]:
    """Validate the model output and return an entity-to-type mapping."""
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("entities"), list):
        raise ValueError('Expected {"entities": [...]}')
    prediction: dict[str, str] = {}
    for item in parsed["entities"]:
        if not isinstance(item, dict):
            raise ValueError("Expected entity objects")
        name, label = item.get("text"), item.get("type")
        if not isinstance(name, str) or label not in LABELS:
            raise ValueError("Invalid entity text or type")
        if not name or name not in text:
            raise ValueError(f"Entity mention absent from input text: {name!r}")
        prediction[name] = label
    return prediction


def main() -> None:
    client = Client(host=OLLAMA_HOST)
    totals = {"TP": 0, "FP": 0, "FN": 0}
    records = []

    for sample in DATASET:
        print(f"\nProcessing {sample['id']}")
        start = time.perf_counter()
        response = client.chat(
            model=MODEL,
            think=False,
            format=ENTITY_SCHEMA,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Sentence: {sample['text']}"},
            ],
            options=OPTIONS,
        )
        elapsed = time.perf_counter() - start
        raw_output = response.message.content or ""

        error = None
        try:
            prediction = parse_prediction(raw_output, sample["text"])
        except (ValueError, TypeError) as exc:  # JSONDecodeError is a ValueError
            error = str(exc)
            prediction = {}
            print(f"Invalid output: {error}")

        scores = evaluate_ner(sample["gold"], prediction)
        for key in totals:
            totals[key] += scores[key]

        records.append({
            "id": sample["id"],
            "text": sample["text"],
            "gold": sample["gold"],
            "prediction": prediction,
            "valid": error is None,
            "error": error,
            "raw_output": raw_output,
            "scores": scores,
            "latency_seconds": elapsed,
            "generated_tokens": response.eval_count,
            "generation_duration_ns": response.eval_duration,
            "prompt_tokens": response.prompt_eval_count,
        })

        print(f"Prediction: {prediction}")
        print(f"TP={scores['TP']} FP={scores['FP']} FN={scores['FN']}")
        print(f"F1={scores['f1']:.4f}")

    micro = micro_scores(totals)
    print("\n=== DATASET RESULTS (baseline) ===")
    print(f"TP={totals['TP']}, FP={totals['FP']}, FN={totals['FN']}")
    print(f"Micro-Precision: {micro['precision']:.4f}")
    print(f"Micro-Recall:    {micro['recall']:.4f}")
    print(f"Micro-F1:        {micro['f1']:.4f}")
    print(f"Valid outputs:   {sum(r['valid'] for r in records)}/{len(records)}")
    print(f"Total latency:   {sum(r['latency_seconds'] for r in records):.2f}s")
    print(f"Generated tokens: {sum(r['generated_tokens'] or 0 for r in records)}")

    # Save all responses, including unsuccessful ones
    output_path = PROJECT_ROOT / "results" / "ner_dev_baseline.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=2, ensure_ascii=False)
    print(f"\nSaved results to: {output_path}")


if __name__ == "__main__":
    main()
