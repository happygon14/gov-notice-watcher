import os
import requests

headers = {
    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"
}

r = requests.get(
    "https://openrouter.ai/api/v1/models",
    headers=headers
)

print(r.status_code)

models = r.json()["data"]

for m in models[:30]:
    print(m["id"])
