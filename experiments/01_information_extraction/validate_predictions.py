
"""Validate occurrence-specific NER predictions."""

LABELS = {"PER", "ORG", "LOC", "MISC"}
import re


def find_all_occurrences(text, name):
    """Return all exact substring occurrences as character spans."""
    return [
        {"start": match.start(), "end": match.end()}
        for match in re.finditer(re.escape(name), text)
    ]



def validate_predictions(text, entities):
    """Check predicted entity types and character boundaries."""
    if not isinstance(entities, list):
        raise ValueError("Expected a list of entities")

    validated = []
    seen = set()

    for entity in entities:
        if not isinstance(entity, dict):
            raise ValueError("Each entity must be an object")

        name = entity.get("text")
        label = entity.get("type")
        start = entity.get("start")
        end = entity.get("end")

        if label not in LABELS:
            raise ValueError(f"Invalid entity type: {label}")

        if not isinstance(name, str) or not name:
            raise ValueError("Invalid entity text")

        if type(start) is not int or type(end) is not int:
            raise ValueError("Character offsets must be integers")

        if not (0 <= start < end <= len(text)):
            raise ValueError("Character offsets are out of bounds")

        if text[start:end] != name:
            raise ValueError(
                f"Span mismatch: expected {name!r}, "
                f"found {text[start:end]!r}"
            )

        identity = (start, end, label)

        if identity in seen:
            raise ValueError(f"Duplicate prediction: {identity}")

        seen.add(identity)
        validated.append(entity)

    return validated


if __name__ == "__main__":
    text = "Paris welcomed researchers. Paris hosted a conference."

    predictions = [
        {"text": "Paris", "type": "LOC", "start": 0, "end": 5},
        {"text": "Paris", "type": "LOC", "start": 28, "end": 33},
    ]

    validated = validate_predictions(text, predictions)

    print(f"Validated entities: {len(validated)}")
    for entity in validated:
        print(entity)

    print(find_all_occurrences(text, "Paris"))
