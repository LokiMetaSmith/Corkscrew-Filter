
import os
import inspect
from google import genai
from google.genai import types

def debug_models():
    print("Inspecting google.genai.types...")
    if hasattr(types, "Model"):
        print("Found types.Model")
        # inspect annotations
        try:
            print(types.Model.__annotations__)
        except:
            print("No annotations found")

        # inspect dir
        print("Dir of types.Model:")
        print(dir(types.Model))
    else:
        print("types.Model not found")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found. Cannot perform live list.")
        print("Please export GEMINI_API_KEY='your_key_here' and try again.")
        return

    client = genai.Client(api_key=api_key)
    try:
        print("Listing models...")
        for m in client.models.list():
            # Check supported_actions (newer API) or supported_generation_methods (older API)
            actions = getattr(m, "supported_actions", None)
            methods = getattr(m, "supported_generation_methods", None)

            print(f"Model: {m.name}")
            print(f"Actions: {actions}")
            print(f"Methods: {methods}")

            if actions and "generateContent" in actions:
                print("Status: OK (via actions)")
            elif methods and "generateContent" in methods:
                print("Status: OK (via methods)")
            else:
                print("Status: NO GENERATE CONTENT")
            print("-" * 20)

    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    debug_models()
