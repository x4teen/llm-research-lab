
"""Test Qwen's ability to return occurrence-specific NER spans."""

import json
from ollama import Client

from ner_common import MODEL, OLLAMA_HOST, OPTIONS
from validate_predictions import validate_predictions


TEXT = "Paris welcomed researchers. Paris hosted a conference."

SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["PER", "ORG", "LOC", "MISC"],
                    },
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                },
                "required": ["text", "type", "start", "end"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["entities"],
    "additionalProperties": False,
}

SYSTEM = (
    "Extract all named-entity occurrences from the sentence. "
    "Use entity types PER, ORG, LOC, and MISC. "
    "Return the exact entity text and its zero-based character "
    "start and end offsets. End offsets are exclusive. "
    "Count spaces and punctuation as characters. "
    "Each occurrence must be listed separately."
)


def main():
    client = Client(host=OLLAMA_HOST)

    response = client.chat(
        model=MODEL,
        think=False,
        format=SCHEMA,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Sentence: {TEXT}"},
        ],
        options=OPTIONS,
    )

    raw = response.message.content or ""
    print("RAW MODEL RESPONSE:")
    print(raw)

    try:
        parsed = json.loads(raw)
        entities = validate_predictions(TEXT, parsed["entities"])
        print("\nVALIDATION: PASSED")
        print(f"Accepted entities: {len(entities)}")
    except (ValueError, TypeError, KeyError) as exc:
        print(f"\nVALIDATION: FAILED ({exc})")

    print(f"\nGenerated tokens: {response.eval_count}")


if __name__ == "__main__":
    main()
