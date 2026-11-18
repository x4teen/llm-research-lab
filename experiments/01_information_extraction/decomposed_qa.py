"""Decomposed-QA named-entity recognition over the dev dataset.

Run: python decomposed_qa.py
Install: python -m pip install ollama

Use the Ollama URL reachable from the Python process (set OLLAMA_HOST, e.g.
http://127.0.0.1:11434 on the remote host, or a Windows SSH tunnel on 11435).
Shares model settings, type definitions, and data with batch_baseline.py via
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
    "You extract named entities from a sentence, one entity type at a time.\n"
    + TYPE_DEFINITIONS
    + "List only entities of the requested type, copied exactly as they appear "
    'in the sentence. Reply as {"entities": [...]}; use [] if there are none.'
)

# The question names the type, so the model returns names only and cannot
# attach the wrong type. Constrained decoding rules out free-form keys.
ENTITY_SCHEMA = {
    "type": "object",
    "properties": {"entities": {"type": "array", "items": {"type": "string"}}},
    "required": ["entities"],
}


def parse_names(raw: str, text: str) -> list[str]:
    """Validate one turn's output and return the entity names."""
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("entities"), list):
        raise ValueError('Expected {"entities": [...]}')
    names = parsed["entities"]
    if not all(isinstance(name, str) and name for name in names):
        raise ValueError("Expected non-empty entity strings")
    missing = [name for name in names if name not in text]
    if missing:
        raise ValueError(f"Entity mention absent from input text: {missing}")
    return names


def decomposed_ner(text: str, client: Client) -> tuple[dict[str, str], list[dict]]:
    """Ask one label-specific question per turn, retaining conversation history.

    A schema-invalid turn is recorded and contributes no accepted predictions;
    other turns still run. If two turns claim the same mention, the later
    label wins (counts as one prediction).
    """
    messages = [{"role": "system", "content": SYSTEM}]
    predictions: dict[str, str] = {}
    turn_records: list[dict] = []

    for i, label in enumerate(LABELS):
        # Give the sentence once; later turns refer back to it via history.
        question = (
            f"Sentence: {text}\nWhich entities are of type {label}?"
            if i == 0
            else f"Which entities in the same sentence are of type {label}?"
        )
        messages.append({"role": "user", "content": question})

        started = time.perf_counter()
        response = client.chat(
            model=MODEL,
            think=False,
            format=ENTITY_SCHEMA,
            messages=messages,
            options=OPTIONS,
        )
        elapsed = time.perf_counter() - started
        raw = response.message.content or ""

        # Preserve the actual assistant response, even if invalid, as in the
        # multi-turn Decomposed-QA treatment.
        messages.append({"role": "assistant", "content": raw})

        accepted: dict[str, str] = {}
        error = None
        try:
            accepted = {name: label for name in parse_names(raw, text)}
            predictions.update(accepted)
        except (ValueError, TypeError) as exc:  # JSONDecodeError is a ValueError
            error = str(exc)

        turn_records.append({
            "label": label,
            "raw_response": raw,
            "valid": error is None,
            "error": error,
            "accepted": accepted,
            "wall_seconds": elapsed,
            "generated_tokens": response.eval_count,
            "prompt_tokens": response.prompt_eval_count,
            "generation_duration_ns": response.eval_duration,
        })

    return predictions, turn_records


def main() -> None:
    client = Client(host=OLLAMA_HOST)
    totals = {"TP": 0, "FP": 0, "FN": 0}
    records = []

    for sample in DATASET:
        print(f"\nProcessing {sample['id']}")
        prediction, turns = decomposed_ner(sample["text"], client)
        scores = evaluate_ner(sample["gold"], prediction)
        for key in totals:
            totals[key] += scores[key]

        for turn in turns:
            status = "ok" if turn["valid"] else f"INVALID ({turn['error']})"
            print(f"  {turn['label']:<12} {turn['raw_response']}  [{status}]")
        print(f"Prediction: {prediction}")
        print(f"TP={scores['TP']} FP={scores['FP']} FN={scores['FN']}")
        print(f"F1={scores['f1']:.4f}")

        records.append({
            "id": sample["id"],
            "text": sample["text"],
            "gold": sample["gold"],
            "prediction": prediction,
            "valid_turns": sum(t["valid"] for t in turns),
            "turns": turns,
            "scores": scores,
            "latency_seconds": sum(t["wall_seconds"] for t in turns),
            "generated_tokens": sum(t["generated_tokens"] or 0 for t in turns),
        })

    micro = micro_scores(totals)
    total_turns = len(records) * len(LABELS)
    print("\n=== DATASET RESULTS (decomposed QA) ===")
    print(f"TP={totals['TP']}, FP={totals['FP']}, FN={totals['FN']}")
    print(f"Micro-Precision: {micro['precision']:.4f}")
    print(f"Micro-Recall:    {micro['recall']:.4f}")
    print(f"Micro-F1:        {micro['f1']:.4f}")
    print(f"Valid turns:     {sum(r['valid_turns'] for r in records)}/{total_turns}")
    print(f"Total latency:   {sum(r['latency_seconds'] for r in records):.2f}s")
    print(f"Generated tokens: {sum(r['generated_tokens'] for r in records)}")

    output_path = PROJECT_ROOT / "results" / "ner_dev_decomposed.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=2, ensure_ascii=False)
    print(f"\nSaved results to: {output_path}")


if __name__ == "__main__":
    main()
