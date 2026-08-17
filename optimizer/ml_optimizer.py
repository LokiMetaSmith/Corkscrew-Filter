import optuna
import os
from typing import Dict, Any, Callable, Tuple

class OptunaOptimizer:
    def __init__(self, config: Dict[str, Any], study_name: str = "openauto_cfd_optimization", storage: str = "sqlite:///artifacts/optuna_study.db"):
        self.config = config
        self.study_name = study_name
        self.storage = storage

        os.makedirs(os.path.dirname(self.storage.replace("sqlite:///", "")), exist_ok=True)

        # Determine direction based on config
        target = self.config.get('optimization', {}).get('target', 'maximize')
        self.direction = "maximize" if target == "maximize" else "minimize"

        self.study = optuna.create_study(
            study_name=self.study_name,
            storage=self.storage,
            direction=self.direction,
            load_if_exists=True
        )

    def _suggest_parameters(self, trial: optuna.Trial, parameters_def: Dict[str, Any]) -> Dict[str, Any]:
        """Suggests parameters, respecting dependency order similarly to the fallback."""

        dependency_order = [
            "tube_od_mm", "tube_wall_mm", "cyclone_diameter", "vortex_finder_diameter",
            "inlet_width", "helix_path_radius_mm", "helix_profile_radius_mm",
            "helix_void_profile_radius_mm", "slit_axial_length_mm", "slit_chamfer_height"
        ]

        # Get list of all parameters, append any not in dependency_order
        all_params = list(parameters_def.keys())
        ordered_params = [p for p in dependency_order if p in all_params]
        ordered_params.extend([p for p in all_params if p not in ordered_params])

        new_params = {}
        for param_name in ordered_params:
            constraints = parameters_def.get(param_name, {})

            # Use default/constant values
            if "default" in constraints and constraints.get("constant", False):
                 new_params[param_name] = constraints["default"]
                 continue

            p_min = constraints.get("min")
            p_max = constraints.get("max")
            p_type = constraints.get("type", "float")

            # Resolve dependencies (e.g. max is another parameter)
            current_p_min = p_min
            if isinstance(p_min, str) and p_min in new_params:
                current_p_min = new_params[p_min]

            current_p_max = p_max
            if isinstance(p_max, str) and p_max in new_params:
                current_p_max = new_params[p_max]

            # Default bounds if None
            if current_p_min is None: current_p_min = 0.0
            if current_p_max is None: current_p_max = 100.0

            # Dynamic geometry constraint fallbacks (mimicking random strategy)
            if param_name == "helix_profile_radius_mm" and "helix_path_radius_mm" in new_params:
                if current_p_max > new_params["helix_path_radius_mm"]:
                    current_p_max = new_params["helix_path_radius_mm"] * 0.95

            if param_name == "helix_void_profile_radius_mm" and "helix_profile_radius_mm" in new_params:
                if current_p_max > new_params["helix_profile_radius_mm"]:
                    current_p_max = new_params["helix_profile_radius_mm"] * 0.95

            # Sample from Optuna
            if current_p_min > current_p_max:
                current_p_min = current_p_max # Prevent invalid bounds

            if p_type == "int":
                new_params[param_name] = trial.suggest_int(param_name, int(current_p_min), int(current_p_max))
            elif p_type == "float":
                new_params[param_name] = trial.suggest_float(param_name, float(current_p_min), float(current_p_max))
            else:
                new_params[param_name] = trial.suggest_float(param_name, float(current_p_min), float(current_p_max))

        return new_params

    def suggest_next(self, parameters_def: Dict[str, Any]) -> optuna.Trial:
        """Helper for stepping one trial at a time (like in main.py loop)."""
        trial = self.study.ask()
        params = self._suggest_parameters(trial, parameters_def)
        return trial, params

    def report_result(self, trial: optuna.Trial, score: float, metrics: Dict[str, Any]):
        """Reports the scalar score back to the study, pruning if it failed."""
        if "error" in metrics:
            self.study.tell(trial, state=optuna.trial.TrialState.PRUNED)
        else:
            self.study.tell(trial, score)
