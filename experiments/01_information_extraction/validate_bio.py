"""Validate BIO-to-span conversion on CoNLL-2003 validation data.

Installs the datasets package automatically if missing (see ner_common).
"""

from collections import Counter

from bio_to_spans import bio_to_spans
from ner_common import load_conll, load_conll_label_map
from bio_to_spans import bio_to_char_spans


def main():
    validation = load_conll()["validation"]
    id2label = load_conll_label_map()

    entity_counts = Counter()
    failures = []

    for index, sample in enumerate(validation):
        tokens = sample["tokens"]
        tags = [id2label[tag] for tag in sample["tags"]]

        try:
            entities = bio_to_spans(tokens, tags)
            text, char_entities = bio_to_char_spans(tokens, tags)

            assert len(entities) == len(char_entities)

            for entity in char_entities:
                start = entity["start"]
                end = entity["end"]

                assert 0 <= start < end <= len(text)
                assert text[start:end] == entity["text"]
        except (ValueError, AssertionError) as exc:
            failures.append({"index": index, "error": str(exc)})
            continue

        for entity in entities:
            entity_counts[entity["type"]] += 1

    print(f"Validation records: {len(validation)}")
    print(f"Successful records: {len(validation) - len(failures)}")
    print(f"Failed records:     {len(failures)}")

    print("\nEntity counts:")
    for label, count in sorted(entity_counts.items()):
        print(f"  {label}: {count}")

    if failures:
        print("\nFirst five failures:")
        for failure in failures[:5]:
            print(failure)


if __name__ == "__main__":
    main()
