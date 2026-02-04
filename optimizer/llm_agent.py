import os
import json
import mimetypes
from google import genai
from google.genai import types
from typing import Dict, List, Any
try:
    from PIL import Image
except ImportError:
    print("Warning: Pillow not found. Image features will be disabled.")
    Image = None

class LLMAgent:
    def __init__(self, api_key=None, model_name="gemini-1.5-flash-001"):
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            print("Warning: GEMINI_API_KEY not found. LLM features will be disabled.")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

        self.model_name = model_name
        self.fallback_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro", "gemini-1.0-pro"]
        self.history = []

    def _generate_with_retry(self, contents):
        """
        Attempts to generate content, retrying with fallback models if a 404 or other client error occurs.
        """
        models_to_try = [self.model_name] + self.fallback_models

        for model in models_to_try:
            try:
                print(f"Attempting to generate with model: {model}")
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents
                )
                return response
            except Exception as e:
                print(f"Model {model} failed: {e}")
                # If it's a 404 Not Found, try next.
                # For other errors, we might also want to try next or fail.
                # Assuming try next for robustness.
                continue

        raise Exception("All models failed to generate content.")

    def suggest_parameters(self, current_params: Dict[str, Any], metrics: Dict[str, Any], constraints: str = "", image_paths: List[str] = None, history: List[Dict] = None) -> Dict[str, Any]:
        """
        Asks the LLM for the next set of parameters.
        """
        # Add last run to history
        if current_params:
            self.history.append({
                "parameters": current_params,
                "metrics": metrics
            })

        if not self.client:
            # Fallback if no API key
            print("No LLM available. Returning current parameters.")
            return current_params

        # Use provided history if available, otherwise use internal history
        history_to_use = history if history is not None else self.history

        prompt = self._construct_prompt(constraints, history_to_use, has_images=bool(image_paths))

        content = [prompt]

        # Load images if provided
        if image_paths:
            for path in image_paths:
                try:
                    print(f"Loading image for LLM: {path}")
                    # Read file directly as bytes
                    with open(path, "rb") as f:
                        image_data = f.read()

                    # Determine mime type
                    mime_type, _ = mimetypes.guess_type(path)
                    if not mime_type:
                        mime_type = "image/png" # Default fallback

                    content.append(types.Part.from_bytes(data=image_data, mime_type=mime_type))
                except Exception as e:
                    print(f"Failed to load image {path}: {e}")

        try:
            response = self._generate_with_retry(content)
            text = response.text
            # Extract JSON from potential markdown code blocks
            clean_text = self._extract_json(text)
            data = json.loads(clean_text)

            if "parameters" in data:
                return data["parameters"]
            else:
                print("LLM response did not contain 'parameters' field.")
                return current_params
        except Exception as e:
            print(f"LLM generation failed after retries: {e}")
            return current_params

    def suggest_campaign(self, history: List[Dict], constraints: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        Asks the LLM to generate a batch of parameter sets to explore different regions of the design space.
        """
        if not self.client:
            print("No LLM available.")
            return []

        history_str = json.dumps(history, indent=2)

        prompt = f"""
You are an expert engineer optimizing a 3D printed inertial filter (corkscrew shape).
GOAL: Generate {count} DISTINCT sets of parameters to explore the design space effectively.
Focus on varying key parameters (radius, twist, screw pitch) to understand their impact on separation efficiency and pressure drop.

CONSTRAINTS:
{constraints}

HISTORY OF RUNS:
{history_str}

TASK:
Propose {count} parameter sets. They should be diverse (explore different strategies).

RESPONSE FORMAT:
You must respond with valid JSON only.
{{
    "campaign_reasoning": "Explain the overall strategy...",
    "jobs": [
        {{
            "reasoning": "Why this specific set...",
            "parameters": {{ ... }}
        }},
        ...
    ]
}}
"""
        try:
            response = self._generate_with_retry([prompt])
            text = response.text
            clean_text = self._extract_json(text)
            data = json.loads(clean_text)

            if "jobs" in data and isinstance(data["jobs"], list):
                # Extract just the parameters from each job
                return [job["parameters"] for job in data["jobs"] if "parameters" in job]
            else:
                print("LLM response did not contain valid 'jobs' list.")
                return []
        except Exception as e:
            print(f"LLM campaign generation failed: {e}")
            return []

    def _construct_prompt(self, constraints, history, has_images=False):
        history_str = json.dumps(history, indent=2)

        visual_instruction = ""
        if has_images:
            visual_instruction = """
VISUAL INSPECTION:
I have provided images of the solid model generated by the current parameters.
Please visually inspect them for:
1. Structural integrity (no disconnected parts).
2. Proper geometry formation (e.g. helical continuity).
3. "Christmas Tree" barb shape on the inlet/outlet (if visible).
4. General printability (wall thickness, etc).
If you see any visual defects, adjust the parameters to fix them in the next iteration.
"""

        return f"""
You are an expert engineer optimizing a 3D printed inertial filter (corkscrew shape) using OpenSCAD and OpenFOAM.
The application is separating MOON DUST (Lunar Regolith, density ~3000 kg/m^3, particle size ~20 microns) from air.
The mechanism is inertial separation via centrifugal force generated by the helical screw.

GOAL: Optimize the design parameters to MAXIMIZE particle collection efficiency (capture dense particles on the outer wall) and MINIMIZE pressure drop.

CONSTRAINTS:
{constraints}

{visual_instruction}

HISTORY OF RUNS:
{history_str}

TASK:
Analyze the history. Identify trends. Propose the NEXT set of parameters to test to improve performance.
You must modify the parameters intelligently based on the physics of centrifugal separation (F = mv^2/r).

RESPONSE FORMAT:
You must respond with valid JSON only.
{{
    "reasoning": "Explain why you chose these parameters...",
    "parameters": {{
        "param_name": value,
        ...
    }}
}}
"""

    def _extract_json(self, text):
        # Remove ```json ... ``` if present
        if "```" in text:
            start = text.find("```json")
            if start == -1:
                start = text.find("```")

            # find end
            end = text.rfind("```")

            if start != -1 and end != -1 and start != end:
                # Adjust start to skip line
                first_newline = text.find("\n", start)
                if first_newline != -1 and first_newline < end:
                    return text[first_newline:end].strip()
        return text.strip()

if __name__ == "__main__":
    agent = LLMAgent(api_key="TEST_KEY") # Won't work without valid key
    print("LLMAgent initialized.")
