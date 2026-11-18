
"""Align predicted entity names with occurrences in a sentence."""

import re


def align_mentions(text, predictions):
    """Assign predictions to distinct occurrences, left to right.

    Returns:
        aligned: Predictions with character offsets.
        unaligned: Predictions that could not be placed.
    """
    aligned = []
    unaligned = []
    used_spans = set()

    for prediction in predictions:
        name = prediction["text"]
        label = prediction["type"]

        matches = list(re.finditer(re.escape(name), text))

        chosen = None

        for match in matches:
            span = (match.start(), match.end())

            if span not in used_spans:
                chosen = span
                break

        if chosen is None:
            unaligned.append(prediction)
            continue

        used_spans.add(chosen)

        aligned.append({
            "text": name,
            "type": label,
            "start": chosen[0],
            "end": chosen[1],
        })

    return aligned, unaligned


if __name__ == "__main__":
    text = "New York University opened a campus."

    predictions = [
        {"text": "New York University", "type": "ORG"},
        {"text": "New York", "type": "LOC"},
    ]

    aligned, unaligned = align_mentions(text, predictions)

    print("Aligned:", aligned)
    print("Unaligned:", unaligned)
