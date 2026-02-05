import os
import sys
from llm_agent import LLMAgent

def main():
    print("Verifying LLM Connection...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Please export GEMINI_API_KEY='your_key_here' and try again.")
        sys.exit(1)

    print(f"Initializing LLMAgent with default model...")
    agent = LLMAgent(api_key=api_key)
    print(f"Agent Model: {agent.model_name}")
    print(f"Fallback Models: {agent.fallback_models}")

    prompt = ["Hello! Please confirm you are working by replying with 'System Operational'."]

    print("\nSending request...")
    try:
        response = agent._generate_with_retry(prompt)
        print(f"\nResponse received:\n{response.text}")
        print("\nVerification SUCCESS.")
    except Exception as e:
        print(f"\nVerification FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
