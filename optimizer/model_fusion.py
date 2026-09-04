"""
model_fusion.py

Closed-Loop Active Optimizer and Model Fusion Engine.
Integrates fast surrogates (Zero-Training RBF + 3D-FNO) with OpenEMSDriver.
Uses progressive fidelity:
  1. Fast Inner Loop: Evaluates 100s of candidate designs through the surrogate in milliseconds.
  2. Acquisition Function: Selects the best trade-off between exploitation (min S11) and exploration (uncertainty).
  3. Slow Outer Loop: Verifies the champion candidate with openEMS / FEM.
  4. Online Residual Feedback: Computes prediction error and updates surrogate memory.
"""

import os
import time
import copy
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Callable

from surrogate_rbf import RBFFieldSurrogate
from phasor_export import export_phasor_file, extract_phasor_from_openems_h5

try:
    from fno_3d import FNOModelWrapper, HAS_TORCH
except ImportError:
    HAS_TORCH = False
    FNOModelWrapper = None


class ModelFusionOptimizer:
    """
    Orchestrates the closed-loop active learning cycle between surrogate and physics solver.
    """
    def __init__(
        self,
        physics_driver,
        parameter_defs: Dict[str, Any],
        surrogate_db_path: str = "artifacts/surrogate_memory.json",
        use_fno: bool = False,
        exploration_weight: float = 0.25,
        verbose: bool = True
    ):
        self.driver = physics_driver
        self.parameter_defs = parameter_defs
        self.surrogate_db_path = surrogate_db_path
        self.exploration_weight = exploration_weight
        self.verbose = verbose

        self.param_names = sorted(list(parameter_defs.keys()))

        # Load or initialize Zero-Training RBF Surrogate
        if os.path.exists(surrogate_db_path):
            try:
                self.surrogate_rbf = RBFFieldSurrogate.load(surrogate_db_path)
                if self.verbose:
                    print(f"[ModelFusion] Loaded existing surrogate memory with {len(self.surrogate_rbf.param_history)} samples.")
            except Exception as e:
                print(f"[ModelFusion] Warning: Failed to load surrogate from {surrogate_db_path}, creating fresh. Error: {e}")
                self.surrogate_rbf = RBFFieldSurrogate(param_names=self.param_names)
        else:
            self.surrogate_rbf = RBFFieldSurrogate(param_names=self.param_names)

        # Initialize FNO if enabled and torch is present
        self.use_fno = use_fno and HAS_TORCH and (FNOModelWrapper is not None)
        self.fno_wrapper = FNOModelWrapper() if self.use_fno else None

        self.iteration = 0
        self.history: List[Dict[str, Any]] = []

    def _get_bounds(self, param_name: str) -> Tuple[float, float]:
        defn = self.parameter_defs.get(param_name, {})
        p_min = defn.get("min", 0.0)
        p_max = defn.get("max", 100.0)
        if isinstance(p_min, str) or p_min is None: p_min = 0.0
        if isinstance(p_max, str) or p_max is None: p_max = 100.0
        return float(p_min), float(p_max)

    def sample_random_parameters(self) -> Dict[str, float]:
        """Generates random valid parameter dictionary within bounds."""
        params = {}
        for p in self.param_names:
            p_min, p_max = self._get_bounds(p)
            params[p] = float(np.random.uniform(p_min, p_max))
        return params

    def mutate_parameters(self, base_params: Dict[str, float], mutation_scale: float = 0.15) -> Dict[str, float]:
        """Applies Gaussian mutation to a parameter set within its bounds."""
        mutated = copy.deepcopy(base_params)
        for p in self.param_names:
            p_min, p_max = self._get_bounds(p)
            span = p_max - p_min
            delta = np.random.normal(0, mutation_scale * span)
            new_val = np.clip(mutated.get(p, p_min) + delta, p_min, p_max)
            mutated[p] = float(new_val)
        return mutated

    def evaluate_surrogate(self, params: Dict[str, float]) -> Tuple[float, float]:
        """
        Fast millisecond evaluation through the surrogate.
        Returns: (predicted_S11, epistemic_uncertainty)
        """
        metrics, uncertainty = self.surrogate_rbf.predict_metrics(params)
        s11 = metrics.get("S11", -10.0)
        return float(s11), float(uncertainty)

    def acquisition_function(self, predicted_s11: float, uncertainty: float) -> float:
        """
        Lower is better (minimizing return loss S11 in dB).
        Bonus for uncertainty encourages discovering unvisited geometry regions.
        """
        return predicted_s11 - (self.exploration_weight * 20.0 * uncertainty)

    def select_next_candidate(self, n_candidates: int = 100, seed_params: Optional[Dict[str, float]] = None) -> Tuple[Dict[str, float], float, float]:
        """
        Searches the surrogate space in milliseconds to propose the best candidate geometry.
        Returns (candidate_params, predicted_s11, uncertainty)
        """
        candidates = []
        if seed_params:
            candidates.append(seed_params)
            for _ in range(n_candidates // 2):
                candidates.append(self.mutate_parameters(seed_params, mutation_scale=0.1))
            for _ in range(n_candidates // 2):
                candidates.append(self.sample_random_parameters())
        else:
            for _ in range(n_candidates):
                candidates.append(self.sample_random_parameters())

        best_score = float("inf")
        best_cand = candidates[0]
        best_s11 = 0.0
        best_unc = 0.0

        for cand in candidates:
            s11_pred, unc = self.evaluate_surrogate(cand)
            score = self.acquisition_function(s11_pred, unc)
            if score < best_score:
                best_score = score
                best_cand = cand
                best_s11 = s11_pred
                best_unc = unc

        return best_cand, best_s11, best_unc

    def step(self, candidate_params: Optional[Dict[str, float]] = None, mock_run: bool = False) -> Dict[str, Any]:
        """
        Executes one complete closed-loop cycle:
          1. Propose / use candidate design
          2. Run fast surrogate precomputation
          3. Dispatch openEMS solver for ground truth
          4. Compute residual error
          5. Update surrogate memory & export binary phasor
        """
        self.iteration += 1
        t0 = time.time()

        # 1. Propose candidate if none provided
        best_known = self.history[-1]["params"] if self.history else None
        if candidate_params is None:
            candidate_params, pred_s11, uncertainty = self.select_next_candidate(seed_params=best_known)
        else:
            pred_s11, uncertainty = self.evaluate_surrogate(candidate_params)

        t_surrogate = (time.time() - t0) * 1000.0  # ms

        if self.verbose:
            print(f"\n[ModelFusion Iteration {self.iteration}]")
            print(f"  Proposed Params: {json.dumps({k: round(v, 3) for k, v in candidate_params.items()})}")
            print(f"  Surrogate S11 Estimate: {pred_s11:.2f} dB (uncertainty: {uncertainty:.3f}, took {t_surrogate:.1f} ms)")

        # 2. Execute Ground Truth via Physics Driver
        t_solver_start = time.time()
        solver_success = False
        actual_metrics = {"S11": -10.0}
        sparam_curve = None
        field_data = None

        if not mock_run:
            try:
                # Prepare case and execute solver
                self.driver.prepare_case()
                solver_success = self.driver.run_solver()
                if solver_success:
                    actual_metrics = self.driver.get_metrics()
            except Exception as e:
                print(f"  [ModelFusion] Solver error: {e}")
                solver_success = False
        else:
            # Mock physics run for testing
            solver_success = True
            # Simulate resonance dip based on candidate parameters
            resonance_val = -18.0 - 5.0 * np.sin(candidate_params.get(self.param_names[0], 1.0))
            actual_metrics = {"S11": float(resonance_val)}
            freqs = np.linspace(2.4e9, 2.5e9, 11)
            s11_vals = -10.0 - 10.0 * np.exp(-((freqs - 2.45e9) / 2e7)**2)
            sparam_curve = (freqs, s11_vals)

        t_solver_duration = time.time() - t_solver_start

        actual_s11 = actual_metrics.get("S11")
        if actual_s11 is None or not np.isfinite(actual_s11):
            actual_s11 = -5.0  # Penalty for non-converged run
            actual_metrics["S11"] = actual_s11

        # 3. Compute Residual
        residual = actual_s11 - pred_s11
        if self.verbose:
            print(f"  Actual Solver S11: {actual_s11:.2f} dB (took {t_solver_duration:.2f} s)")
            print(f"  Surrogate Residual Delta: {residual:+.2f} dB")

        # 4. Extract 3D Field from solver if available
        h5_path = os.path.join(getattr(self.driver, "case_dir", "."), "sim_data", "Et.h5")
        if os.path.exists(h5_path):
            field_data = extract_phasor_from_openems_h5(h5_path)

        # If no field from H5, generate synthetic standing wave phasor for testing
        if field_data is None:
            n_pts = 1000
            coords = np.random.uniform(-10, 10, (n_pts, 3)).astype(np.float32)
            e_re = (coords * 0.1).astype(np.float32)
            e_im = np.zeros_like(e_re)
            field_data = {"coords": coords, "E_re": e_re, "E_im": e_im}

        # 5. Feed back into Surrogate Memory (Online Model Fusion)
        self.surrogate_rbf.add_sample(
            params=candidate_params,
            metrics=actual_metrics,
            sparam_curve=sparam_curve,
            field_data=field_data
        )
        self.surrogate_rbf.save(self.surrogate_db_path)

        # 6. Export Binary Phasor for Real-time Visualization
        bin_export_path = f"artifacts/phasor_iter_{self.iteration}.bin"
        if field_data is not None:
            export_phasor_file(
                bin_export_path,
                coords=field_data["coords"],
                e_re=field_data["E_re"],
                e_im=field_data["E_im"]
            )
            if self.verbose:
                print(f"  Exported GPU Phasor Buffer: {bin_export_path}")

        step_record = {
            "iteration": self.iteration,
            "params": candidate_params,
            "pred_s11": pred_s11,
            "actual_s11": actual_s11,
            "residual_s11": residual,
            "uncertainty": uncertainty,
            "t_surrogate_ms": t_surrogate,
            "t_solver_s": t_solver_duration,
            "solver_success": solver_success,
            "phasor_bin": bin_export_path
        }
        self.history.append(step_record)
        return step_record
