import requests

try:
    response = requests.get("http://localhost:11434/api/tags", timeout=2)
    print(response.json())
except Exception as e:
    print(f"Error: {e}")
