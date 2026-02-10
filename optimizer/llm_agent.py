import os
import json
import re
import random
import mimetypes
import time
import base64
from typing import Dict, List, Any, Union, Tuple

# Attempt imports for providers
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import openai
except ImportError:
    openai = None

try:
    from PIL import Image
except ImportError:
    # Optional for simple usage, but good to have
    Image = None

class LLMProvider:
    """Abstract base class for LLM providers."""
    def generate(self, prompt: str, image_paths: List[str] = None) -> str:
        raise NotImplementedError

    def list_models(self) -> List[str]:
        return []

    def get_name(self) -> str:
        return "Unknown Provider"


class GoogleGenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        if not genai:
            raise ImportError("google-genai library not installed.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.fallback_models = ["gemini-2.5-flash", "gemini-3.0-flash", "gemini-1.5-flash"]

    def get_name(self) -> str:
        return f"Google GenAI ({self.model_name})"

    def generate(self, prompt: str, image_paths: List[str] = None) -> str:
        # Prepare content
        content = [prompt]
        if image_paths:
            for path in image_paths:
                try:
                    # print(f"Loading image for LLM: {path}")
                    with open(path, "rb") as f:
                        image_data = f.read()
                    mime_type, _ = mimetypes.guess_type(path)
                    if not mime_type:
                        mime_type = "image/png"
                    content.append(types.Part.from_bytes(data=image_data, mime_type=mime_type))
                except Exception as e:
                    print(f"Failed to load image {path}: {e}")

        # Retry logic with fallbacks
        models_to_try = [self.model_name] + self.fallback_models
        # Deduplicate
        unique_models = []
        seen = set()
        for m in models_to_try:
            if m not in seen:
                unique_models.append(m)
                seen.add(m)
        models_to_try = unique_models

        for model in models_to_try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # print(f"Attempting to generate with Google model: {model} (Attempt {attempt+1}/{max_retries})")
                    response = self.client.models.generate_content(
                        model=model,
                        contents=content
                    )
                    return response.text
                except Exception as e:
                    error_str = str(e)
                    # print(f"Model {model} failed: {error_str}")

                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        match = re.search(r"retry in ([0-9.]+)s", error_str)
                        if match:
                            wait_time = float(match.group(1)) + 1.0
                            print(f"Rate limit hit. Waiting for {wait_time:.2f} seconds...")
                            time.sleep(wait_time)
                            continue
                        else:
                            print("Rate limit hit. Waiting 30s...")
                            time.sleep(30)
                            continue
                    break # Not a rate limit, try next model

            # If exhausted retries for this model, continue to next fallback

        raise Exception("All Google models failed.")

    def list_models(self) -> List[str]:
        models = []
        try:
            for m in self.client.models.list():
                actions = getattr(m, "supported_actions", None)
                methods = getattr(m, "supported_generation_methods", None)
                if (actions and "generateContent" in actions) or \
                   (methods and "generateContent" in methods):
                    models.append(m.name)
        except Exception as e:
            print(f"Error listing Google models: {e}")
        return models


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = None, model_name: str = "gpt-4o"):
        if not openai:
            raise ImportError("openai library not installed.")

        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model_name = model_name

    def get_name(self) -> str:
        base = self.client.base_url
        return f"OpenAI Compatible ({base}) - Model: {self.model_name}"

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def generate(self, prompt: str, image_paths: List[str] = None) -> str:
        messages = []

        content_list = [{"type": "text", "text": prompt}]

        if image_paths:
            for path in image_paths:
                try:
                    # print(f"Loading image for LLM: {path}")
                    base64_image = self._encode_image(path)
                    mime_type, _ = mimetypes.guess_type(path)
                    if not mime_type:
                        mime_type = "image/png"

                    content_list.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    })
                except Exception as e:
                    print(f"Failed to load image {path}: {e}")

        messages.append({
            "role": "user",
            "content": content_list
        })

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # print(f"Attempting to generate with OpenAI model: {self.model_name} (Attempt {attempt+1}/{max_retries})")
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages
                )
                return response.choices[0].message.content
            except Exception as e:
                error_str = str(e)
                print(f"OpenAI Provider failed: {error_str}")

                # Handle Rate Limits (429)
                if "429" in error_str or isinstance(e, openai.RateLimitError):
                    print("Rate limit hit. Waiting 20s...")
                    time.sleep(20)
                    continue

                # If not rate limit, generic retry?
                # For network errors maybe. For invalid request, no.
                # Assuming simple retry strategy.
                time.sleep(5)

        raise Exception(f"OpenAI Provider failed after {max_retries} attempts.")

    def list_models(self) -> List[str]:
        models = []
        try:
            resp = self.client.models.list()
            for m in resp.data:
                models.append(m.id)
        except Exception as e:
            print(f"Error listing OpenAI models: {e}")
        return models


class LLMAgent:
    def __init__(self, api_key=None, model_name="gemini-2.5-flash"):
        self.providers: List[LLMProvider] = []
        self.history = []

        # 1. Google GenAI Setup
        # Use passed api_key if provided, else env var
        gemini_key = api_key if api_key else os.environ.get("GEMINI_API_KEY")

        if gemini_key and genai:
            try:
                # Use passed model_name if appropriate, otherwise default
                p = GoogleGenAIProvider(gemini_key, model_name=model_name)
                self.providers.append(p)
                # print(f"Registered provider: {p.get_name()}")
            except Exception as e:
                print(f"Failed to initialize Google GenAI provider: {e}")
        elif not genai and gemini_key:
             print("Warning: GEMINI_API_KEY present but google-genai lib missing.")

        # 2. OpenAI Compatible Setup
        openai_key = os.environ.get("OPENAI_API_KEY")
        openai_base = os.environ.get("OPENAI_BASE_URL")
        openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o") # Default to generic

        # If using local/other, key might be arbitrary, base_url is key.
        # Or key is real OpenAI key.
        if (openai_key or openai_base) and openai:
            # If no key provided but base_url exists (common for local), use dummy
            if not openai_key and openai_base:
                openai_key = "sk-no-key-required"

            try:
                p = OpenAIProvider(api_key=openai_key, base_url=openai_base, model_name=openai_model)
                self.providers.append(p)
                # print(f"Registered provider: {p.get_name()}")
            except Exception as e:
                print(f"Failed to initialize OpenAI provider: {e}")
        elif not openai and (openai_key or openai_base):
            print("Warning: OPENAI_API_KEY/BASE_URL present but openai lib missing.")

        if not self.providers:
            print("Warning: No LLM providers available (Missing Keys or Libraries). LLM features will be disabled.")
            print("To enable, set GEMINI_API_KEY or OPENAI_API_KEY/OPENAI_BASE_URL.")

    def _generate(self, prompt: str, image_paths: List[str] = None) -> str:
        """Iterates through providers until one succeeds."""
        if not self.providers:
            raise Exception("No LLM providers available.")

        errors = []
        for provider in self.providers:
            try:
                print(f"Using provider: {provider.get_name()}")
                return provider.generate(prompt, image_paths)
            except Exception as e:
                msg = f"Provider {provider.get_name()} failed: {e}"
                print(msg)
                errors.append(msg)

        raise Exception(f"All providers failed. Errors: {errors}")

    def list_available_models(self):
        print("\n--- Available Models (All Providers) ---")
        if not self.providers:
            print("No providers configured.")
            return

        for provider in self.providers:
            print(f"\nProvider: {provider.get_name()}")
            models = provider.list_models()
            for m in models:
                print(f"- {m}")
        print("----------------------------------------\n")

    def _generate_random_parameters(self, current_params: Dict[str, Any], constraints_str: str) -> Dict[str, Any]:
        """
        Generates random parameters within valid ranges when LLM is unavailable.
        This provides a basic random search strategy.
        """
        print("Using random search strategy...")
        new_params = current_params.copy()

        # Define ranges (based on config.scad and constraints.py)

        # insert_length_mm: 40 - 60
        new_params["insert_length_mm"] = round(random.uniform(40.0, 60.0), 2)

        # number_of_complete_revolutions: 1 - 4
        new_params["number_of_complete_revolutions"] = random.randint(1, 4)

        # helix_void_profile_radius_mm: 0.5 - 2.0
        void_radius = round(random.uniform(0.5, 2.0), 2)
        new_params["helix_void_profile_radius_mm"] = void_radius

        # helix_path_radius_mm: > void + 0.5
        # Range 1.5 - 5.0, but must be > void
        path_radius = round(random.uniform(max(1.5, void_radius + 0.5), 5.0), 2)
        new_params["helix_path_radius_mm"] = path_radius

        # helix_profile_radius_mm: > void + 0.5 AND <= path_radius
        min_profile = max(1.5, void_radius + 0.5)
        profile_radius = round(random.uniform(min_profile, path_radius), 2)
        new_params["helix_profile_radius_mm"] = profile_radius

        # helix_profile_scale_ratio: 1.0 - 2.0
        new_params["helix_profile_scale_ratio"] = round(random.uniform(1.0, 2.0), 2)

        # Slit parameters (explicitly adding them as they are optimization targets)
        slit_axial = round(random.uniform(1.0, 3.0), 2)
        new_params["slit_axial_length_mm"] = slit_axial
        # slit_chamfer_height < slit_axial_length_mm
        new_params["slit_chamfer_height"] = round(random.uniform(0.1, min(1.0, slit_axial - 0.1)), 2)

        # num_bins: 1 - 3 (integer)
        new_params["num_bins"] = random.randint(1, 3)

        return new_params

    def suggest_parameters(self, current_params: Dict[str, Any], metrics: Dict[str, Any], constraints: str = "", image_paths: List[str] = None, history: List[Dict] = None) -> Union[Dict[str, Any], Tuple[Dict[str, Any], bool]]:
        """
        Asks the LLM for the next set of parameters.
        Returns just the new parameters dict, or (parameters, stop_flag) if requested by caller logic.
        """
        # Add last run to history
        if current_params:
            self.history.append({
                "parameters": current_params,
                "metrics": metrics
            })

        if not self.providers:
            # Fallback if no providers
            print("No LLM available. Generating random parameters for exploration.")
            return self._generate_random_parameters(current_params, constraints)

        # Use provided history if available, otherwise use internal history
        history_to_use = history if history is not None else self.history

        prompt = self._construct_prompt(constraints, history_to_use, has_images=bool(image_paths))

        try:
            text = self._generate(prompt, image_paths)
            data = self._parse_json_safely(text)

            # Check for stop signal
            if data.get("stop_optimization") is True:
                print("LLM signaled to STOP optimization.")
                return {"stop_optimization": True}

            if "parameters" in data:
                return data["parameters"]
            else:
                print("LLM response did not contain 'parameters' field.")
                if "error" in metrics:
                    print("Previous run failed and LLM returned invalid/no parameters. Falling back to random strategy.")
                    return self._generate_random_parameters(current_params, constraints)
                return current_params
        except Exception as e:
            print(f"LLM generation failed after retries: {e}")
            if "error" in metrics:
                print("Previous run failed and LLM generation failed. Falling back to random strategy to break error loop.")
                return self._generate_random_parameters(current_params, constraints)
            return current_params

    def suggest_campaign(self, history: List[Dict], constraints: str, count: int = 5, image_paths: List[str] = None) -> List[Dict[str, Any]]:
        """
        Asks the LLM to generate a batch of parameter sets.
        """
        if not self.providers:
            print("No LLM available.")
            return []

        history_str = json.dumps(history, indent=2)

        # Check for errors in the last run
        error_instruction = ""
        if history and "metrics" in history[-1] and "error" in history[-1]["metrics"]:
            last_error = history[-1]["metrics"]["error"]
            details = history[-1]["metrics"].get("details", "No details")
            error_instruction = f"""
CRITICAL WARNING:
The previous run FAILED with error: "{last_error}".
Details: {details}
YOU MUST ADJUST PARAMETERS TO FIX THIS ERROR.
If the error was 'invalid_parameters', you violated a geometric constraint.
If 'helix_void_profile_radius_mm' >= 'helix_profile_radius_mm', you MUST decrease void radius or increase profile radius significantly.
"""

        visual_instruction = ""
        if image_paths:
            visual_instruction = """
VISUAL INSPECTION:
I have provided images of the solid model generated by the MOST RECENT run.
Please visually inspect them for:
1. Structural integrity (no disconnected parts).
2. Proper geometry formation (e.g. helical continuity).
3. "Christmas Tree" barb shape on the inlet/outlet (if visible).
4. General printability (wall thickness, etc).
If you see any visual defects, adjust the parameters to fix them in the next batch.
"""

        prompt = f"""
You are an expert engineer optimizing a 3D printed inertial filter (corkscrew shape) using OpenSCAD and OpenFOAM.
The application is separating MOON DUST (Lunar Regolith, density ~3000 kg/m^3, particle size ~20 microns) from air.
The mechanism is inertial separation via centrifugal force generated by the helical screw.

GOAL: Optimize the design parameters to meet the following STRICT SUCCESS CRITERIA:
1. Particle Collection Efficiency > 99.95%
2. Pressure Drop < 0.7 PSI

Maximize efficiency first, then minimize pressure drop.

CONSTRAINTS:
{constraints}
CONSTRAINT: `helix_profile_radius_mm` must be STRICTLY LESS than `helix_path_radius_mm` (e.g. at least 0.5mm less) to avoid center-axis singularities. Do not set them equal.

{error_instruction}

{visual_instruction}

HISTORY OF RUNS:
{history_str}

TASK:
Analyze the history and visual feedback (if any). Identify trends.
Propose a CAMPAIGN of {count} DISTINCT sets of parameters to explore the design space effectively.
These sets should be diverse enough to learn more about the landscape but focused on improving the best results so far.

RESPONSE FORMAT:
You must respond with valid JSON only.
{{
    "campaign_reasoning": "Explain the overall strategy for this batch...",
    "stop_optimization": false,  // Set to true ONLY if success criteria are met and converged
    "jobs": [
        {{
            "reasoning": "Why this specific set...",
            "parameters": {{
                "param_name": value,
                ...
            }}
        }},
        ...
    ]
}}
"""
        try:
            text = self._generate(prompt, image_paths)
            data = self._parse_json_safely(text)

            if data.get("stop_optimization") is True:
                print("LLM signaled to STOP optimization.")
                return [{"stop_optimization": True}]

            if "jobs" in data and isinstance(data["jobs"], list):
                # Extract just the parameters from each job
                params_list = []
                for job in data["jobs"]:
                    if "parameters" in job:
                        params_list.append(job["parameters"])
                return params_list
            else:
                print("LLM response did not contain valid 'jobs' list.")
                return []
        except Exception as e:
            print(f"LLM campaign generation failed: {e}")
            return []

    def _construct_prompt(self, constraints, history, has_images=False):
        history_str = json.dumps(history, indent=2)

        error_instruction = ""
        if history and "metrics" in history[-1] and "error" in history[-1]["metrics"]:
            last_error = history[-1]["metrics"]["error"]
            details = history[-1]["metrics"].get("details", "No details")
            error_instruction = f"""
CRITICAL WARNING:
The previous run FAILED with error: "{last_error}".
Details: {details}
YOU MUST ADJUST PARAMETERS TO FIX THIS ERROR.
If the error was 'invalid_parameters', you violated a geometric constraint.
If 'helix_void_profile_radius_mm' >= 'helix_profile_radius_mm', you MUST decrease void radius or increase profile radius significantly.
"""

        # Strict constraint reminder
        constraints += "\nCONSTRAINT: `helix_profile_radius_mm` must be STRICTLY LESS than `helix_path_radius_mm` (e.g. at least 0.5mm less) to avoid center-axis singularities. Do not set them equal."

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

GOAL: Optimize the design parameters to meet the following STRICT SUCCESS CRITERIA:
1. Particle Collection Efficiency > 99.95%
2. Pressure Drop < 0.7 PSI

Maximize efficiency first, then minimize pressure drop.

CONSTRAINTS:
{constraints}

{error_instruction}

{visual_instruction}

HISTORY OF RUNS:
{history_str}

TASK:
Analyze the history. Identify trends. Propose the NEXT set of parameters to test.
If you believe the current best result meets the success criteria and no further meaningful improvement is possible, you may choose to STOP the optimization.

RESPONSE FORMAT:
You must respond with valid JSON only.
{{
    "reasoning": "Explain why you chose these parameters...",
    "stop_optimization": false,  // Set to true ONLY if success criteria are met and converged
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
                    text = text[first_newline:end].strip()

        # Try to find the JSON object using regex (outermost curly braces) if it looks like there's extra text
        # This handles cases where the LLM adds commentary outside the code block or forgets the code block
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        # Cleaning: Escape backslashes that are not part of a valid escape sequence
        # This fixes "Invalid \escape" errors common in LLM output (e.g. file paths or LaTeX)
        text = re.sub(r'\\(?![/u"\\bfnrt])', r'\\\\', text)
        return text.strip()

    def _repair_json(self, text):
        """
        Attempts to repair common JSON syntax errors.
        """
        # 1. Remove comments
        text = re.sub(r'//.*', '', text)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

        # 2. Add missing commas after string values
        # Matches "key": "value" followed by "next_key"
        pattern_string = r'("[^"]*"\s*:\s*"(?:[^"\\]|\\.)*")\s*(?=")'
        text = re.sub(pattern_string, r'\1,', text)

        # 3. Add missing commas after primitive values (number, bool, null)
        pattern_primitive = r'("[^"]*"\s*:\s*(?:true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?))\s*(?=")'
        text = re.sub(pattern_primitive, r'\1,', text)

        # 4. Add missing commas after closing braces/brackets
        pattern_structure = r'([}\]])\s*(?=")'
        text = re.sub(pattern_structure, r'\1,', text)

        # 5. Remove trailing commas before closing braces/brackets
        text = re.sub(r',\s*([}\]])', r'\1', text)

        return text

    def _parse_json_safely(self, text):
        """
        Extracts JSON, tries to parse, and falls back to repair if needed.
        """
        clean_text = self._extract_json(text)
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {e}. Attempting repair...")
            repaired_text = self._repair_json(clean_text)
            try:
                return json.loads(repaired_text)
            except json.JSONDecodeError as e2:
                print(f"Repair failed: {e2}")
                # Print snippet for debugging
                print(f"Failed JSON snippet: {clean_text[:500]}...")
                raise e

if __name__ == "__main__":
    # Test initialization
    agent = LLMAgent(api_key="TEST_KEY")
    print("LLMAgent initialized.")
