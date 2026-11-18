
"""Convert BIO annotations into token-indexed entities."""


def bio_to_spans(tokens, tags):
    if len(tokens) != len(tags):
        raise ValueError("Tokens and tags must have equal lengths")

    entities = []
    start = None
    entity_type = None

    def close_entity(end):
        if start is not None:
            entities.append({
                "text": " ".join(tokens[start:end]),
                "type": entity_type,
                "start_token": start,
                "end_token": end,
            })

    for i, tag in enumerate(list(tags) + ["O"]):
        if tag == "O":
            close_entity(i)
            start, entity_type = None, None
            continue

        prefix, label = tag.split("-", 1)

        if prefix == "B":
            close_entity(i)
            start, entity_type = i, label

        elif prefix == "I":
            if start is None or entity_type != label:
                raise ValueError(
                    f"Invalid BIO transition at token {i}: {tag}"
                )
        else:
            raise ValueError(f"Unexpected BIO tag: {tag}")

    return entities


def tokens_to_text_with_offsets(tokens):
    """Return reconstructed text and character spans for each token."""
    text_parts = []
    token_offsets = []
    position = 0

    for token in tokens:
        if text_parts:
            position += 1  # Space before the next token

        start = position
        text_parts.append(token)
        position += len(token)

        token_offsets.append({
            "start": start,
            "end": position,
        })

    return " ".join(text_parts), token_offsets


def bio_to_char_spans(tokens, tags):
    """Convert BIO tags to entities with exact character offsets."""

    text, token_offsets = tokens_to_text_with_offsets(tokens)
    token_entities = bio_to_spans(tokens, tags)

    char_entities = []

    for entity in token_entities:
        first = entity["start_token"]
        last = entity["end_token"] - 1

        start = token_offsets[first]["start"]
        end = token_offsets[last]["end"]

        char_entities.append({
            "text": text[start:end],
            "type": entity["type"],
            "start": start,
            "end": end,
        })

    return text, char_entities


if __name__ == "__main__":
    tokens = ["Marie", "Curie", "visited", "Paris", "."]
    tags = ["B-PER", "I-PER", "O", "B-LOC", "O"]

    for entity in bio_to_spans(tokens, tags):
        print(entity)

    # Test tokens_to_text_with_offsets
    text, offsets = tokens_to_text_with_offsets(tokens)
    print(f"\nReconstructed text: {text}")
    print("Token offsets:")
    for i, offset in enumerate(offsets):
        print(f"  {tokens[i]}: {offset}")

    # Test bio_to_char_spans
    text, char_entities = bio_to_char_spans(tokens, tags)
    print(f"\nReconstructed text: {text}")
    print("Character offsets:")
    for i, entity in enumerate(char_entities):
        print(f"  {entity['text']}: {entity['start']}-{entity['end']}")