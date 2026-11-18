
"""Decomposed-QA named-entity recognition using Ollama and Qwen3 4B.

Run: python decompose_qa.py
Install: python -m pip install ollama

Use the Ollama URL reachable from the Python process (local remote-host port
11434, or a Windows SSH tunnel such as 11435).
"""

import json
import os
import time
from ollama import Client

MODEL = "qwen3:4b"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
LABELS = ("Person", "Organization", "Location")
TEXT = "Marie Curie worked in Paris."

SYSTEM = (
    "Extract named entities from the user's sentence. "
    "Reply with a JSON object whose keys are the exact entity names "
    "found in the sentence and whose values are Person, Organization, "
    "or Location. Only return entities of the type requested by the user. "
    "Do not return instructions, input text, or questions as JSON fields. "
    "Return {} if no entities of that type exist."
)


def decomposed_ner(text: str, client: Client) -> tuple[dict[str, str], list[dict]]:
    """Run three label-specific questions, retaining conversation history.

    A schema-invalid turn is recorded and contributes no accepted predictions;
    other turns still run. This is a diagnostic script, not a benchmark scorer.
    """
    messages = [{"role": "system", "content": SYSTEM}]
    predictions: dict[str, str] = {}
    turn_records: list[dict] = []

    for label in LABELS:
        question = (
            f"Text: {text}\n"
            f"What are the named entities labeled as {label}? "
            "Return only the JSON entity-to-type mapping."
        )
        messages.append({"role": "user", "content": question})

        started = time.perf_counter()
        response = client.chat(
            model=MODEL,
            think=False,
            format="json",
            messages=messages,
            options={"temperature": 0, "num_predict": 256},
        )
        elapsed = time.perf_counter() - started
        raw = response.message.content or ""

        # Preserve the actual assistant response, even if invalid, as in the
        # multi-turn Decomposed-QA treatment.
        messages.append({"role": "assistant", "content": raw})

        accepted: dict[str, str] = {}
        error = None
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Expected a JSON object")
            if not all(
                isinstance(name, str)
                and isinstance(entity_type, str)
                and entity_type == label
                for name, entity_type in parsed.items()
            ):
                raise ValueError(f"Expected entity-name-to-{label} mapping")
            if not all(name and name in text for name in parsed):
                raise ValueError("Entity mention is absent from input text")
            accepted = parsed
            predictions.update(accepted)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            error = str(exc)

        turn_records.append(
            {
                "label": label,
                "raw_response": raw,
                "valid": error is None,
                "error": error,
                "accepted": accepted,
                "wall_seconds": elapsed,
                "generated_tokens": response.eval_count,
                "generation_seconds": (
                    response.eval_duration / 1e9
                    if response.eval_duration is not None
                    else None
                ),
            }
        )

    return predictions, turn_records


def main() -> None:
    client = Client(host=OLLAMA_HOST)
    predictions, turns = decomposed_ner(TEXT, client)

    for turn in turns:
        print(f"\nENTITY TYPE: {turn['label']}")
        print("RAW MODEL RESPONSE:")
        print(turn["raw_response"])
        print(f"Schema valid: {turn['valid']}")
        if turn["error"]:
            print(f"Validation error: {turn['error']}")
        print(f"Generated tokens: {turn['generated_tokens']}")
        print(f"Wall-clock latency: {turn['wall_seconds']:.2f} seconds")

    print("\nFINAL COMBINED PREDICTIONS:")
    print(json.dumps(predictions, indent=2, ensure_ascii=False))
    print(f"\nValid turns: {sum(t['valid'] for t in turns)}/{len(turns)}")
    print(f"Total generated tokens: {sum(t['generated_tokens'] or 0 for t in turns)}")
    print(f"Total wall-clock latency: {sum(t['wall_seconds'] for t in turns):.2f} seconds")


if __name__ == "__main__":
    main()
