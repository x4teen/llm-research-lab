
def evaluate_ner(gold, predicted):
    """
    Evaluate exact-match named entities.

    gold and predicted are dictionaries:
    {"entity text": "entity type"}
    """

    gold_set = set(gold.items())
    predicted_set = set(predicted.items())

    tp = len(gold_set & predicted_set)
    fp = len(predicted_set - gold_set)
    fn = len(gold_set - predicted_set)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }


if __name__ == "__main__":
    # Test case
    gold = {
        "Microsoft": "Organization",
        "Satya Nadella": "Person",
        "Google": "Organization",
        "London": "Location"
    }

    predicted = {
        "Microsoft": "Organization",
        "Satya Nadella": "Person",
        "Google": "Organization"
    }

    print(evaluate_ner(gold, predicted))