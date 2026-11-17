from ollama import Client
import json
import time

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
    # One worked example, shown as a real exchange
    {"role": "user", "content": "Tim Cook visited Apple offices in Paris."},
    {"role": "assistant", "content": '{"Tim Cook": "Person", "Apple": "Organization", "Paris": "Location"}'},
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

result = json.loads(response.message.content)

print("\nMODEL RESPONSE:")
print(json.dumps(result, indent=2))

print("\nPERFORMANCE:")
print(f"Wall-clock latency: {elapsed:.2f} seconds")
print(f"Generated tokens: {response.eval_count}")
print(f"Generation duration: {response.eval_duration / 1e9:.2f} seconds")

