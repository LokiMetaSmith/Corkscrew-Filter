import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

from llm_agent import LLMAgent

def list_models():
    print("Checking available models from configured providers...")

    # Attempt to initialize agent with environment variables
    # This will automatically pick up GEMINI_API_KEY, OPENAI_API_KEY, etc.
    agent = LLMAgent()

    # Check if we have any providers
    if not agent.providers:
        print("\nError: No LLM providers configured.")
        return

    # Use the agent to list models
    agent.list_available_models()

if __name__ == "__main__":
    list_models()
