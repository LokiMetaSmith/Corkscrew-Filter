import os
from llm_agent import LLMAgent

def list_models():
    print("Checking available models from configured providers...")

    # Attempt to initialize agent with environment variables
    # This will automatically pick up GEMINI_API_KEY, OPENAI_API_KEY, etc.
    agent = LLMAgent()

    # Check if we have any providers
    if not agent.providers:
        print("\nError: No LLM providers configured.")
        print("Please set one of the following environment variables:")
        print("  - GEMINI_API_KEY")
        print("  - OPENAI_API_KEY (and optionally OPENAI_BASE_URL)")
        return

    # Use the agent to list models
    agent.list_available_models()

if __name__ == "__main__":
    list_models()
