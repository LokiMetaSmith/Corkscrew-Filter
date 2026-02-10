import os
import sys
from llm_agent import LLMAgent

def main():
    print("Verifying LLM Connection...")

    # Initialize LLMAgent (will detect GEMINI_API_KEY, OPENAI_API_KEY, etc.)
    # passing no args forces it to look at environment variables
    agent = LLMAgent()

    if not agent.providers:
        print("\nError: No LLM providers configured.")
        print("Please set one of the following:")
        print("  - GEMINI_API_KEY (for Google Gemini)")
        print("  - OPENAI_API_KEY (and optionally OPENAI_BASE_URL for Local LLMs)")
        sys.exit(1)

    print(f"\nConfigured Providers:")
    for p in agent.providers:
        print(f"  - {p.get_name()}")

    prompt = "Hello! Please confirm you are working by replying with 'System Operational'."

    print("\nSending request...")
    try:
        # Using the internal _generate method to test connection
        # We use _generate directly because we want raw text output, not parsed JSON
        response_text = agent._generate(prompt)
        print(f"\nResponse received:\n{response_text}")
        print("\nVerification SUCCESS.")
    except Exception as e:
        print(f"\nVerification FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
