
import sys
import json
import time
from pathlib import Path
from ollama import Client
from evaluation import evaluate_ner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# Use the Ollama endpoint that works in your environment
client = Client(host="http://127.0.0.1:11434")
MODEL = "qwen3:4b"

# Small development dataset — not the held-out benchmark
dataset = [
    {
        "id": "dev_001",
        "text": "Microsoft CEO Satya Nadella visited London.",
        "gold": {
            "Microsoft": "Organization",
            "Satya Nadella": "Person",
            "London": "Location"
        }
    },
    {
        "id": "dev_002",
        "text": "Tim Cook met Sundar Pichai at Google.",
        "gold": {
            "Tim Cook": "Person",
            "Sundar Pichai": "Person",
            "Google": "Organization"
        }
    },
    {
        "id": "dev_003",
        "text": "Amazon opened an office in Berlin.",
        "gold": {
            "Amazon": "Organization",
            "Berlin": "Location"
        }
    },
    {
        "id": "dev_004",
        "text": "Marie Curie worked in Paris.",
        "gold": {
            "Marie Curie": "Person",
            "Paris": "Location"
        }
    },
    {
        "id": "dev_005",
        "text": "The engineer reviewed the report yesterday.",
        "gold": {}
    }
]

system = (
    "Extract the named entities from the user's sentence. "
    "Reply with a JSON object whose keys are the exact entity names "
    "found in the sentence and whose values are Person, "
    "Organization, or Location. "
    "Return {} if no named entities are found."
)

totals = {"TP": 0, "FP": 0, "FN": 0}
records = []
allowed_types = {"Person", "Organization", "Location"}

for sample in dataset:
    print(f"\nProcessing {sample['id']}")

    start = time.perf_counter()

    response = client.chat(
        model=MODEL,
        think=False,
        format="json",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": sample["text"]}
        ],
        options={
            "temperature": 0,
            "num_predict": 256
        }
    )

    elapsed = time.perf_counter() - start
    raw_output = response.message.content or ""

    try:
        prediction = json.loads(raw_output)

        if not isinstance(prediction, dict):
            raise ValueError("Expected a JSON object")

        if not all(
            isinstance(name, str)
            and isinstance(label, str)
            and label in allowed_types
            for name, label in prediction.items()
        ):
            raise ValueError("Invalid entity dictionary")

        valid = True

    except (ValueError, TypeError) as error:
        print(f"Invalid output: {error}")
        prediction = {}
        valid = False

    scores = evaluate_ner(sample["gold"], prediction)

    for key in totals:
        totals[key] += scores[key]

    records.append({
        "id": sample["id"],
        "text": sample["text"],
        "gold": sample["gold"],
        "prediction": prediction,
        "valid": valid,
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

# Aggregate entity counts before calculating micro-F1
tp, fp, fn = totals["TP"], totals["FP"], totals["FN"]

precision = tp / (tp + fp) if tp + fp else 0.0
recall = tp / (tp + fn) if tp + fn else 0.0
f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0

print("\n=== DATASET RESULTS ===")
print(f"TP={tp}, FP={fp}, FN={fn}")
print(f"Micro-Precision: {precision:.4f}")
print(f"Micro-Recall:    {recall:.4f}")
print(f"Micro-F1:        {f1:.4f}")
print(f"Valid outputs:   {sum(r['valid'] for r in records)}/{len(records)}")
print(f"Total latency:   {sum(r['latency_seconds'] for r in records):.2f}s")
print(f"Generated tokens: {sum(r['generated_tokens'] or 0 for r in records)}")

# Save all responses, including unsuccessful ones
output_path = PROJECT_ROOT / "results" / "ner_dev_baseline.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w", encoding="utf-8") as file:
    json.dump(records, file, indent=2, ensure_ascii=False)

print(f"\nSaved results to: {output_path}")
