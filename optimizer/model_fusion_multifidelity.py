"""
model_fusion_multifidelity.py

Two-Stage Multi-Fidelity Closed-Loop Active Learning Optimizer.
Prunes unviable geometries with fast Tier-1 coarse simulations (~15s) and only
promotes high-potential candidates to Tier-2 fine simulations (~15m).
Calibrates cross-fidelity transfer functions rho and discrepancy fields delta(x) online.
"""

import os
import time
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

from surrogate_multifidelity import MultiFidelitySurrogate
from multifidelity_driver import MultiFidelityPhysicsDriver
from surrogate_gradients import DifferentiableInverseDesigner
from async_solver_queue import AsyncSolverQueue
from cfd_fea_field_io import export_multiphysics_field_bin


class MultiFidelityModelFusionOptimizer:
    """
    Two-stage multi-fidelity model fusion optimizer.
    Filters candidate space with cheap coarse meshes, calibrating fine-mesh predictions online.
    """

    def __init__(
        self,
        physics_driver=None,
        parameter_defs: Optional[Dict[str, Any]] = None,
        domain: str = "cfd",
        surrogate_db_path: Optional[str] = None,
        screening_eff_threshold: float = 88.0,
        screening_dp_threshold: float = 4500.0,
        verbose: bool = True
    ):
        self.domain = domain.lower()
        self.parameter_defs = parameter_defs or {}
        self.param_names = sorted(list(self.parameter_defs.keys()))
        self.verbose = verbose
        self.screening_eff_threshold = screening_eff_threshold
        self.screening_dp_threshold = screening_dp_threshold

        # Multi-Fidelity Surrogate
        db_path = surrogate_db_path or f"artifacts/{self.domain}_multifidelity.json"
        self.surrogate_db_path = db_path
        self.surrogate = MultiFidelitySurrogate(domain=self.domain, param_names=self.param_names)

        # Multi-Fidelity Driver Wrapper
        self.driver = MultiFidelityPhysicsDriver(base_driver=physics_driver, domain=self.domain, verbose=self.verbose)

        # Differentiable Inverse Designer (operating on fused high-fi surface)
        self.inverse_designer = DifferentiableInverseDesigner(
            surrogate=self.surrogate.high_fi_surrogate,
            parameter_defs=self.parameter_defs,
            domain=self.domain
        )

        # Async Queue for background fine runs
        self.async_queue = AsyncSolverQueue(max_workers=2, verbose=self.verbose)

        self.iteration = 0
        self.history: List[Dict[str, Any]] = []

    def sample_random_parameters(self) -> Dict[str, float]:
        params = {}
        for p in self.param_names:
            defn = self.parameter_defs.get(p, {})
            p_min = float(defn.get("min", 0.0) or 0.0)
            p_max = float(defn.get("max", 100.0) or 100.0)
            params[p] = float(np.random.uniform(p_min, p_max))
        return params

    def select_next_candidate(self) -> Tuple[Dict[str, float], Dict[str, float], float]:
        """Proposes candidate geometry using inverse design on the multi-fidelity surface."""
        if self.surrogate.is_fitted and len(self.surrogate.high_fi_history) >= 2:
            try:
                # Update surrogate reference
                self.inverse_designer.surrogate = self.surrogate.high_fi_surrogate
                opt_p, score = self.inverse_designer.optimize(n_restarts=4)
                pred_m, unc = self.surrogate.predict_metrics(opt_p)
                return opt_p, pred_m, unc
            except Exception:
                pass

        # Fallback to random / exploration
        cand = self.sample_random_parameters()
        pred_m, unc = self.surrogate.predict_metrics(cand)
        return cand, pred_m, unc

    def step(
        self,
        candidate_params: Optional[Dict[str, float]] = None,
        mock_run: bool = True
    ) -> Dict[str, Any]:
        """
        Executes complete Two-Stage Multi-Fidelity Cycle:
          Stage 1: Fast Coarse Simulation (Tier 1)
          Screening: Evaluate performance vs threshold
          Stage 2: Fine Simulation (Tier 2) only if candidate passes screening
        """
        self.iteration += 1
        t0 = time.time()

        # 1. Propose candidate
        if candidate_params is None:
            candidate_params, pred_h, unc = self.select_next_candidate()
        else:
            pred_h, unc = self.surrogate.predict_metrics(candidate_params)

        if self.verbose:
            print(f"\n[MultiFidelity Iteration {self.iteration}]")
            print(f"  Proposed Geometry: {json.dumps({k: round(v, 2) for k, v in candidate_params.items()})}")
            pred_str = ", ".join([f"{k}: {v:.1f}" for k, v in pred_h.items()])
            print(f"  Fused Multi-Fi Estimate: [{pred_str}] (uncertainty={unc:.3f})")

        # 2. Stage 1: Fast Coarse Simulation (Tier 1)
        coarse_res = self.driver.execute(candidate_params, fidelity="coarse", mock_run=mock_run)
        coarse_metrics = coarse_res["metrics"]
        self.surrogate.add_low_fidelity_sample(
            candidate_params,
            coarse_metrics,
            field_data=coarse_res["field_data"]
        )

        # 3. Two-Stage Screening Filter
        passed_screening = False
        if self.domain == "cfd":
            eff = coarse_metrics.get("separation_efficiency", 0.0)
            dp = coarse_metrics.get("delta_p", 9999.0)
            # Pass if coarse metrics meet screening threshold
            if eff >= self.screening_eff_threshold and dp <= self.screening_dp_threshold:
                passed_screening = True
        elif self.domain in ("fea", "structural"):
            fos = coarse_metrics.get("factor_of_safety", 0.0)
            if fos >= 1.4:
                passed_screening = True
        else:
            passed_screening = True

        # 4. Stage 2: Fine Simulation (Tier 2) if passed
        fine_res = None
        status = "PRUNED_COARSE"
        actual_fine_metrics = {}

        if passed_screening:
            status = "PROMOTED_TO_FINE"
            if self.verbose:
                print(f"  >>> Screening Passed! Promoting candidate to Tier-2 Fine Simulation (1.5mm mesh)...")
            fine_res = self.driver.execute(candidate_params, fidelity="fine", mock_run=mock_run)
            actual_fine_metrics = fine_res["metrics"]
            self.surrogate.add_high_fidelity_sample(
                candidate_params,
                actual_fine_metrics,
                field_data=fine_res["field_data"]
            )
            self.surrogate.save(self.surrogate_db_path)
        else:
            if self.verbose:
                print(f"  --- Candidate failed screening threshold. Pruning to save compute!")

        # 5. Export 3D Field
        bin_export_path = f"artifacts/{self.domain}_multifidelity_iter_{self.iteration}.bin"
        field_to_export = fine_res["field_data"] if fine_res else coarse_res["field_data"]
        if field_to_export is not None and "coords" in field_to_export:
            vals = field_to_export.get("values")
            if vals is None:
                if self.domain == "cfd":
                    vals = np.concatenate([field_to_export["U"], field_to_export["p"][:, np.newaxis]], axis=-1)
                elif self.domain in ("fea", "structural"):
                    vals = np.concatenate([field_to_export["disp"], field_to_export["von_mises"][:, np.newaxis]], axis=-1)
                else:
                    vals = np.zeros((len(field_to_export["coords"]), 1), dtype=np.float32)

            export_multiphysics_field_bin(
                bin_export_path,
                coords=field_to_export["coords"],
                values=vals,
                domain=self.domain.upper()
            )

        total_duration = time.time() - t0
        stats = self.surrogate.get_fidelity_stats()

        record = {
            "iteration": self.iteration,
            "params": candidate_params,
            "status": status,
            "coarse_metrics": coarse_metrics,
            "fine_metrics": actual_fine_metrics,
            "pred_metrics": pred_h,
            "uncertainty": unc,
            "duration_s": total_duration,
            "stats": stats,
            "field_bin": bin_export_path
        }
        self.history.append(record)

        if self.verbose:
            print(f"  Multi-Fidelity Stats: {stats['low_fidelity_samples']} Coarse | {stats['high_fidelity_samples']} Fine (Compute Speedup: {stats['speedup_factor']}x)")
            if self.surrogate.rho:
                rho_str = ", ".join([f"{k}: {v:.2f}" for k, v in self.surrogate.rho.items()])
                print(f"  Calibrated Cross-Fidelity Scaling rho: [{rho_str}]")

        return record
