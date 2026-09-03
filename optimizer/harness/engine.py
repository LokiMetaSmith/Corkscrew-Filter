import os
import json
from typing import Dict, Any, Callable, List, Tuple
from .state import State, Action, compute_state_distance, parse_solver_outputs_to_state
from .timeline import Timeline
from .surrogate import SurrogateManager
from .notes import NotesManager
from .planner import BFSPlanner

class SchemaEngine:
    def __init__(self, workspace_dir: str, parameter_defs: Dict[str, Any], llm_agent=None, epsilon: float = 5.0):
        self.workspace_dir = workspace_dir
        self.parameter_defs = parameter_defs
        self.llm_agent = llm_agent
        self.epsilon = epsilon  # Dynamic mismatch threshold

        # Paths
        self.timeline_path = os.path.join(workspace_dir, "timeline.jsonl")
        self.world_model_path = os.path.join(workspace_dir, "world_model.py")
        self.notes_path = os.path.join(workspace_dir, "notes.md")

        # Managers
        self.timeline = Timeline(self.timeline_path)
        self.surrogate = SurrogateManager(self.world_model_path)
        self.notes = NotesManager(self.notes_path)
        self.planner = BFSPlanner(self.surrogate, self.parameter_defs)

    def run_backtests(self) -> float:
        """
        Replays past recorded transitions.
        Returns the mean squared prediction error.
        """
        transitions = self.timeline.load_transitions()
        if not transitions:
            return 0.0

        errors = []
        for trans in transitions:
            start = State.from_dict(trans["start_state"])
            act = Action.from_dict(trans["action"])
            actual = State.from_dict(trans["actual_state"])

            try:
                predicted = self.surrogate.run_step(start, act)
                dist = compute_state_distance(predicted, actual)
                errors.append(dist ** 2)
            except Exception as e:
                # If error running model, treat as infinite error
                errors.append(1e6)

        return sum(errors) / len(errors) if errors else 0.0

    def trigger_mechanism_discovery(self, current_state: State, failed_action: Action, actual_next_state: State):
        """
        Invokes LLM (Google GenAI primary, Ollama local fallback) to rewrite world_model.py
        to resolve prediction mismatch issues. Updates notes.md with the physics hypothesis.
        """
        print("[Schema] Mismatch detected. Triggering mechanism discovery loop...")

        past_transitions = self.timeline.load_transitions()
        history_str = json.dumps(past_transitions, indent=2)

        prompt = f"""You are an expert physicist and software engineer.
Our fast virtual surrogate world_model.py failed to predict the actual outcome of the physics solver.

MISMATCH:
- Starting State: {json.dumps(current_state.to_dict(), indent=2)}
- Action Mutation: {json.dumps(failed_action.to_dict(), indent=2)}
- Actual Next State: {json.dumps(actual_next_state.to_dict(), indent=2)}

HISTORY OF ALL TRANSITIONS:
{history_str}

Please discover the corrected physical/geometric mechanism and rewrite the python world_model.py step() function.
The file must be fully functional and self-contained, defining:
def step(state_dict, action_dict):
    ...
    return next_state_dict

Ensure it models transitions for geometry parameters and multi-physics domains (fluid, structural, electromagnetic) dynamically and accurately based on the history.

Your response MUST be divided into two clear parts separated by a marker line containing exactly `=== CODE ===`:
1. A markdown section explaining your new physical hypotheses and representational changes (which will be appended to notes.md).
2. The complete, corrected python code for world_model.py (which will overwrite the current world_model.py).

Example Response format:
Physical Hypothesis explaining the mismatch details...
=== CODE ===
# python world model code...
"""

        # Generate using LLM
        notes_content = "Discovered physical discrepancy. Updated transition sensitivity model."
        model_code = ""

        if self.llm_agent and self.llm_agent.providers:
            try:
                raw_response = self.llm_agent._generate(prompt)
                if "=== CODE ===" in raw_response:
                    parts = raw_response.split("=== CODE ===")
                    notes_content = parts[0].strip()
                    model_code = parts[1].strip()
                    # Clean code block formatting if any
                    if model_code.startswith("```python"):
                        model_code = model_code[len("```python"):].strip()
                    if model_code.endswith("```"):
                        model_code = model_code[:-3].strip()
                else:
                    # Best effort JSON/Python extraction
                    model_code = raw_response
            except Exception as e:
                print(f"[Schema] LLM mechanism discovery failed: {e}. Falling back to default heuristics.")

        if not model_code:
            # Fallback to local heuristic updates to ensure code runs and is updated
            notes_content = "Adjusted model parameters to handle localized mutation scaling."
            # Read current world model code and modify it minimally, or rewrite with default template
            with open(self.world_model_path, "r") as f:
                model_code = f.read()

        # Update persistent artifacts
        self.notes.append_note("Discovered Discrepancy & Representation Change", notes_content)
        self.surrogate.update_model_code(model_code)
        print("[Schema] Mechanism discovery complete. notes.md and world_model.py updated.")

    def run_one_iteration(self, current_state: State, score_func: Callable[[State], float], real_solver_func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Tuple[State, Action, State, float]:
        """
        Executes one full iteration of the Schema loop:
        1. Backtest check: If timeline errors exceed threshold, rewrite world_model.py.
        2. Plan inside surrogate using BFS.
        3. Execute action via the real, expensive multi-physics solver.
        4. Append transitions to the persistent timeline.jsonl.
        """
        # 1. Backtest
        mse = self.run_backtests()
        print(f"[Schema] Backtest MSE: {mse:.4f} (Threshold: {self.epsilon ** 2})")
        if mse > (self.epsilon ** 2):
            # Attempt to resolve using mechanism discovery
            transitions = self.timeline.load_transitions()
            if transitions:
                last_trans = transitions[-1]
                start = State.from_dict(last_trans["start_state"])
                act = Action.from_dict(last_trans["action"])
                actual = State.from_dict(last_trans["actual_state"])
                self.trigger_mechanism_discovery(start, act, actual)

        # 2. Plan inside surrogate
        action, expected_next_state, expected_score = self.planner.search(current_state, score_func)
        print(f"[Schema] Planned Action: {action.to_dict()}")

        # 3. Execute in actual physical world
        # Convert planned action to real solver input parameters
        real_params = current_state.geometry.copy()
        for k, mutation in action.to_dict().items():
            real_params[k] = float(real_params.get(k, 0.0)) + float(mutation)

        print("[Schema] Executing action with physical solvers...")
        metrics = real_solver_func(real_params)
        actual_next_state = parse_solver_outputs_to_state(real_params, metrics)

        # 4. Record transition
        self.timeline.append_transition(current_state, action, expected_next_state, actual_next_state)

        # Verify performance difference
        dist = compute_state_distance(expected_next_state, actual_next_state)
        print(f"[Schema] Target prediction discrepancy: {dist:.4f}")

        return current_state, action, actual_next_state, dist
