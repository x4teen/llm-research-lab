from ollama import Client
import json
import time

from evaluation import evaluate_ner

#Ollama endpoint through SSH tunnel to Vast.ai
client = Client(host="http://127.0.0.1:11434")

MODEL = "qwen3:4b"

text = "Microsoft CEO Satya Nadella met Google executives in London."

system = (
    "Extract the named entities from the user's sentence. "
    "Reply with a JSON object whose keys are the entity names found in the sentence "
    "and whose values are Person, Organization, or Location."
)

messages = [
    {"role": "system", "content": system},
    {"role": "user", "content": text},
]

start = time.perf_counter()

response = client.chat(
    model=MODEL,
    think=False,
    format="json",
    messages=messages,
    options={"temperature": 0, "num_predict": 256},
)

elapsed = time.perf_counter() - start

try:
    result = json.loads(response.message.content)

    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")

    allowed_types = {"Person", "Organization", "Location"}

    if not all(
        isinstance(entity, str)
        and isinstance(label, str)
        and label in allowed_types
        for entity, label in result.items()
    ):
        raise ValueError("Invalid entity prediction structure")

    valid_output = True

except (json.JSONDecodeError, ValueError, TypeError) as error:
    print(f"Invalid model output: {error}")
    result = {}
    valid_output = False

gold = {
    "Microsoft": "Organization",
    "Satya Nadella": "Person",
    "Google": "Organization",
    "London": "Location"
}

scores = evaluate_ner(gold, result)


print("\nMODEL RESPONSE:")
print(json.dumps(result, indent=2))

print("\nEVALUATION RESULTS:")
for metric, value in scores.items():
    print(f"{metric}: {value}")

print("\nPERFORMANCE:")
print(f"Wall-clock latency: {elapsed:.2f} seconds")
print(f"Generated tokens: {response.eval_count}")
print(f"Generation duration: {response.eval_duration / 1e9:.2f} seconds")

