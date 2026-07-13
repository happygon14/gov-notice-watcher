import os
import requests

headers = {
    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"
}

r = requests.get(
    "https://openrouter.ai/api/v1/models",
    headers=headers
)

models = r.json()["data"]

keywords = [
    "qwen",
    "llama",
    "gemini",
    "grok",
    "gpt",
    "claude"
]

for m in models:
    model_id = m["id"].lower()

    for k in keywords:
        if k in model_id:
            print(m["id"])
            break
