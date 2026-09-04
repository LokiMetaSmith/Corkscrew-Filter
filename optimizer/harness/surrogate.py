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

    # 2. Multi-physics domain updates with EM surrogate fusion
    fluid = next_state.setdefault('fluid', {})
    struct = next_state.setdefault('structural', {})
    em = next_state.setdefault('electromagnetic', {})

    # Use delta path/profile radius, wall thickness, chamfers, and fillets to predict changes
    delta_path = float(action_dict.get('helix_path_radius_mm', 0.0))
    delta_profile = float(action_dict.get('helix_profile_radius_mm', 0.0))
    delta_wall = float(action_dict.get('tube_wall_mm', 0.0))
    delta_chamfer = float(action_dict.get('blade_chamfer_mm', 0.0))
    delta_fillet = float(action_dict.get('inlet_fillet_radius_mm', 0.0))

    if delta_path != 0 or delta_profile != 0 or delta_fillet != 0:
        p_drop = fluid.get('pressure_drop', 120.0)
        eff = fluid.get('separation_efficiency', 95.0)

        # Smooth fillets and larger area reduce flow separation losses & pressure drop
        area_factor = (delta_path * 1.5) + (delta_profile * 2.0) + (delta_fillet * 3.0)
        fluid['pressure_drop'] = max(10.0, p_drop - area_factor * 10.0)
        fluid['separation_efficiency'] = max(1.0, min(100.0, eff + area_factor * 2.0))

    if delta_wall != 0 or delta_chamfer != 0:
        mass = struct.get('total_mass_g', 50.0)
        struct['total_mass_g'] = max(5.0, mass + delta_wall * 15.0)

        # Chamfering blade edges reduces stress concentration factors
        fos = struct.get('factor_of_safety', 2.0)
        stress = struct.get('max_von_mises_stress_MPa', 45.0)
        struct['factor_of_safety'] = max(0.1, fos + delta_wall * 0.5 + delta_chamfer * 0.3)
        struct['max_von_mises_stress_MPa'] = max(1.0, stress - delta_chamfer * 4.0)

    # Electromagnetic domain (S-parameters & Return Loss)
    try:
        from surrogate_rbf import RBFFieldSurrogate
        if os.path.exists("artifacts/surrogate_memory.json"):
            surr = RBFFieldSurrogate.load("artifacts/surrogate_memory.json")
            pred_m, unc = surr.predict_metrics(geom)
            for mk, mv in pred_m.items():
                em[mk] = mv
            em['uncertainty'] = unc
        else:
            prev_s11 = em.get('S11', -12.0)
            em['S11'] = prev_s11 - (delta_path * 0.8) - (delta_profile * 0.5)
    except Exception:
        prev_s11 = em.get('S11', -12.0)
        em['S11'] = prev_s11 - (delta_path * 0.8) - (delta_profile * 0.5)

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
