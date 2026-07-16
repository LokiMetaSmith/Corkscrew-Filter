import os
import sys
import importlib.util
from typing import Dict, Any, Tuple
from .state import State, Action

DEFAULT_WORLD_MODEL_TEMPLATE = """
# Auto-generated world model program
# Represents physics-informed transition rule step(state, action)

def step(state_dict, action_dict):
    \"\"\"
    Receives state_dict: {'geometry': {...}, 'fluid': {...}, 'structural': {...}, 'electromagnetic': {...}}
    Receives action_dict: {'param_name': mutation_value, ...}
    Returns predicted_state_dict of the same shape.
    \"\"\"
    import copy
    next_state = copy.deepcopy(state_dict)

    # 1. Update geometry parameters based on action mutations
    geom = next_state.setdefault('geometry', {})
    for param, mutation in action_dict.items():
        geom[param] = float(geom.get(param, 0.0)) + float(mutation)

    # 2. Heuristics for predicting multi-physics domain updates based on standard physics sensitivities
    fluid = next_state.setdefault('fluid', {})
    struct = next_state.setdefault('structural', {})
    em = next_state.setdefault('electromagnetic', {})

    # Simple default linear sensitivity model to prevent static state
    # e.g., wider channels (higher radius) -> lower pressure drop, lower efficiency
    # higher wall thickness -> higher mass, higher factor of safety
    # S11 improves/degrades slightly with geometry changes

    # Use delta path/profile radius to predict changes
    delta_path = float(action_dict.get('helix_path_radius_mm', 0.0))
    delta_profile = float(action_dict.get('helix_profile_radius_mm', 0.0))
    delta_wall = float(action_dict.get('tube_wall_mm', 0.0))

    if delta_path != 0 or delta_profile != 0:
        # Narrower/wider channels affect fluid drag/pressure drop
        p_drop = fluid.get('pressure_drop', 120.0)
        eff = fluid.get('separation_efficiency', 95.0)

        # Increasing path radius or profile radius increases flow area -> reduces pressure drop
        area_factor = (delta_path * 1.5) + (delta_profile * 2.0)
        fluid['pressure_drop'] = max(10.0, p_drop - area_factor * 10.0)
        fluid['separation_efficiency'] = max(1.0, min(100.0, eff + area_factor * 2.0))

    if delta_wall != 0:
        mass = struct.get('total_mass_g', 50.0)
        struct['total_mass_g'] = max(5.0, mass + delta_wall * 15.0)

        fos = struct.get('factor_of_safety', 2.0)
        struct['factor_of_safety'] = max(0.1, fos + delta_wall * 0.5)

    return next_state
"""

class SurrogateManager:
    def __init__(self, filepath: str = "world_model.py"):
        self.filepath = filepath
        self._ensure_world_model_exists()

    def _ensure_world_model_exists(self):
        if not os.path.exists(self.filepath):
            dir_name = os.path.dirname(self.filepath)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(self.filepath, "w") as f:
                f.write(DEFAULT_WORLD_MODEL_TEMPLATE.strip() + "\n")

    def run_step(self, current_state: State, action: Action) -> State:
        """
        Executes the step function in world_model.py dynamically.
        """
        # Load world_model module dynamically
        spec = importlib.util.spec_from_file_location("world_model", self.filepath)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec from file: {self.filepath}")

        world_model_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(world_model_mod)

        if not hasattr(world_model_mod, "step"):
            raise AttributeError("world_model.py must define a 'step' function.")

        # Execute
        state_dict = current_state.to_dict()
        action_dict = action.to_dict()

        predicted_dict = world_model_mod.step(state_dict, action_dict)
        return State.from_dict(predicted_dict)

    def update_model_code(self, new_code: str):
        """
        Overwrites world_model.py with updated synthesized program code.
        """
        dir_name = os.path.dirname(self.filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(self.filepath, "w") as f:
            f.write(new_code.strip() + "\n")
