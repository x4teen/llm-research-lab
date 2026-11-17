import torch
from ollama import Client

print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

client = Client(host="http://127.0.0.1:11434")
response = client.chat(
    model="qwen3:4b",
    messages=[
        {"role": "user", "content": "Explain transformer attention briefly."}
    ],
    think=False,
)
print(response.message.content)