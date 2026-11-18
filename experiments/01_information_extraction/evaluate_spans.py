
"""Exact character-span NER evaluation."""


def evaluate_spans(gold, predicted):
    """Score matches on (start, end, type)."""

    def as_set(entities):
        return {
            (e["start"], e["end"], e["type"])
            for e in entities
        }

    gold_set = as_set(gold)
    pred_set = as_set(predicted)

    tp = len(gold_set & pred_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2 * tp / (2 * tp + fp + fn)
        if 2 * tp + fp + fn
        else 0.0
    )

    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


if __name__ == "__main__":
    gold = [
        {"start": 0, "end": 11, "type": "PER"},
        {"start": 20, "end": 25, "type": "LOC"},
    ]

    predicted = [
        {"start": 6, "end": 11, "type": "PER"},
        {"start": 20, "end": 25, "type": "LOC"},
    ]

    print(evaluate_spans(gold, predicted))
