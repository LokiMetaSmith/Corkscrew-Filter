import os
from google import genai

def list_models():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not found.")
        print("Please export GEMINI_API_KEY='your_key_here' and try again.")
        return

    try:
        client = genai.Client(api_key=api_key)
        print("Listing available models:")
        # client.models.list() returns an iterator
        for model in client.models.list():
            # Check if it supports content generation
            if "generateContent" in model.supported_generation_methods:
                print(f"- {model.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
