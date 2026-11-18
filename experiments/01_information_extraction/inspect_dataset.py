"""Inspect the CoNLL-2003 dataset.

Installs the datasets package automatically if missing (see ner_common).
Run: python experiments/01_information_extraction/inspect_dataset.py
"""

from ner_common import load_conll, load_conll_label_map


def main():
    import datasets  # installed by load_conll() if missing

    print("Loading CoNLL-2003 dataset...")
    dataset = load_conll()
    print(f"datasets version: {datasets.__version__}")

    print("\nAvailable splits:")
    for split, records in dataset.items():
        print(f"  {split}: {len(records)} examples")

    print("\nDataset columns:")
    print(dataset["validation"].column_names)

    print("\nAnnotation schema:")
    print(dataset["validation"].features)

    id2label = load_conll_label_map()
    print("\nTag ids:")
    print(id2label)

    example = dataset["validation"][0]
    print("\nOne validation example:")
    print(example)
    print("\nTokens with tags:")
    for token, tag in zip(example["tokens"], example["tags"]):
        print(f"  {token:<15} {id2label[tag]}")


if __name__ == "__main__":
    main()
