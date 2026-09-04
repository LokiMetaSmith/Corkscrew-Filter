"""
surrogate_multiphysics.py

Universal Multi-Physics Surrogate for OpenFOAM (CFD), CalculiX (FEA), and OpenEMS.
Provides instant (<2ms) zero-training RBF interpolation of scalar metrics and 3D vector/scalar fields
with epistemic uncertainty quantification across geometric design space.
"""

import os
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
from scipy.interpolate import RBFInterpolator


class MultiPhysicsSurrogate:
    """
    Universal multi-physics surrogate supporting CFD, FEA, EM, and Joint physics.
    Predicts:
      - Scalar metrics:
          CFD: 'delta_p', 'separation_efficiency', 'residuals'
          FEA: 'max_von_mises_stress_MPa', 'max_displacement_mm', 'factor_of_safety'
          EM:  'S11', 'bandwidth_mhz'
      - 3D Continuous Fields:
          CFD: [x, y, z, ux, uy, uz, p]
          FEA: [x, y, z, dx, dy, dz, sigma_vm]
          EM:  [x, y, z, Ex_re, Ey_re, Ez_re, Ex_im, Ey_im, Ez_im]
    """

    def __init__(
        self,
        domain: str = "cfd",
        param_names: Optional[List[str]] = None,
        kernel: str = "thin_plate_spline",
        smoothing: float = 1e-4,
        epsilon: Optional[float] = None,
    ):
        self.domain = domain.lower()
        self.param_names = param_names or []
        self.kernel = kernel
        self.smoothing = smoothing
        self.epsilon = epsilon

        # Observations
        self.param_history: List[np.ndarray] = []
        self.metrics_history: List[Dict[str, float]] = []

        # 3D Field data
        self.field_coords: Optional[np.ndarray] = None  # (N_points, 3)
        self.field_history: List[np.ndarray] = []       # List of (N_points, C)
        self.field_channels: List[str] = []

        # Interpolators
        self._metric_interpolators: Dict[str, RBFInterpolator] = {}
        self._field_interpolator: Optional[RBFInterpolator] = None

        # Parameter normalization
        self._param_min: Optional[np.ndarray] = None
        self._param_max: Optional[np.ndarray] = None
        self.is_fitted: bool = False

    def _extract_param_vector(self, params: Dict[str, float]) -> np.ndarray:
        if not self.param_names:
            self.param_names = sorted(list(params.keys()))
        return np.array([float(params.get(k, 0.0)) for k in self.param_names], dtype=np.float64)

    def add_sample(
        self,
        params: Dict[str, float],
        metrics: Dict[str, Any],
        field_data: Optional[Dict[str, np.ndarray]] = None,
    ):
        """
        Records a ground-truth simulation sample into surrogate memory.
        field_data:
          - 'coords': (N, 3)
          - 'channels': list of channel names (e.g. ['ux', 'uy', 'uz', 'p'])
          - 'values': (N, C) or individual arrays matching channel names
        """
        p_vec = self._extract_param_vector(params)
        self.param_history.append(p_vec)

        # Record scalar metrics
        scalar_m = {}
        for k, v in metrics.items():
            if isinstance(v, (int, float, np.number)) and np.isfinite(v):
                scalar_m[k] = float(v)
        self.metrics_history.append(scalar_m)

        # Record 3D Field Data
        if field_data is not None:
            coords = field_data.get("coords")
            if coords is not None:
                if self.field_coords is None:
                    self.field_coords = np.asarray(coords, dtype=np.float32)

                # Collect channel values
                if "values" in field_data:
                    vals = np.asarray(field_data["values"], dtype=np.float32)
                    if "channels" in field_data:
                        self.field_channels = list(field_data["channels"])
                else:
                    # Domain-specific packing
                    if self.domain == "cfd":
                        u = field_data.get("U", np.zeros((len(coords), 3), dtype=np.float32))
                        p = field_data.get("p", np.zeros((len(coords), 1), dtype=np.float32))
                        if p.ndim == 1:
                            p = p[:, np.newaxis]
                        vals = np.concatenate([u, p], axis=-1).astype(np.float32)
                        self.field_channels = ["ux", "uy", "uz", "p"]
                    elif self.domain in ("fea", "structural"):
                        d = field_data.get("disp", np.zeros((len(coords), 3), dtype=np.float32))
                        s = field_data.get("von_mises", np.zeros((len(coords), 1), dtype=np.float32))
                        if s.ndim == 1:
                            s = s[:, np.newaxis]
                        vals = np.concatenate([d, s], axis=-1).astype(np.float32)
                        self.field_channels = ["dx", "dy", "dz", "sigma_vm"]
                    elif self.domain == "em":
                        e_re = field_data.get("E_re", np.zeros((len(coords), 3), dtype=np.float32))
                        e_im = field_data.get("E_im", np.zeros((len(coords), 3), dtype=np.float32))
                        vals = np.concatenate([e_re, e_im], axis=-1).astype(np.float32)
                        self.field_channels = ["Ex_re", "Ey_re", "Ez_re", "Ex_im", "Ey_im", "Ez_im"]
                    else:
                        vals = np.zeros((len(coords), 1), dtype=np.float32)
                        self.field_channels = ["field_val"]

                self.field_history.append(vals)

        # Refit interpolators online
        self.fit()

    def _make_rbf(self, X: np.ndarray, y: np.ndarray) -> Optional[RBFInterpolator]:
        d = X.shape[1] if X.ndim > 1 else 1
        kwargs = {"kernel": self.kernel, "smoothing": self.smoothing}
        if self.epsilon is not None:
            kwargs["epsilon"] = self.epsilon

        rank = np.linalg.matrix_rank(X) if X.ndim > 1 else 1
        initial_degree = 1 if (len(X) >= 2 * (d + 1) and rank >= d) else -1
        try:
            return RBFInterpolator(X, y, degree=initial_degree, **kwargs)
        except np.linalg.LinAlgError:
            try:
                return RBFInterpolator(X, y, degree=-1, **kwargs)
            except Exception:
                return None
        except Exception:
            return None

    def fit(self):
        """Fits multi-dimensional RBF interpolators on normalized parameter vectors."""
        n_samples = len(self.param_history)
        if n_samples == 0:
            return

        X_raw = np.array(self.param_history)
        self._param_min = np.min(X_raw, axis=0)
        self._param_max = np.max(X_raw, axis=0)
        span = np.where(self._param_max - self._param_min == 0, 1.0, self._param_max - self._param_min)
        X_norm = (X_raw - self._param_min) / span

        # 1. Fit metric interpolators
        metric_keys = set()
        for m in self.metrics_history:
            metric_keys.update(m.keys())

        for m_key in metric_keys:
            y = []
            x_valid = []
            for i, m in enumerate(self.metrics_history):
                if m_key in m:
                    y.append(m[m_key])
                    x_valid.append(X_norm[i])
            if len(y) >= 1:
                interp = self._make_rbf(np.array(x_valid), np.array(y))
                if interp is not None:
                    self._metric_interpolators[m_key] = interp

        # 2. Fit 3D Field interpolator
        if len(self.field_history) >= 1:
            Y_field = np.array([f.flatten() for f in self.field_history])
            interp_f = self._make_rbf(X_norm[:len(self.field_history)], Y_field)
            if interp_f is not None:
                self._field_interpolator = interp_f

        self.is_fitted = True

    def _normalize_params(self, p_vec: np.ndarray) -> np.ndarray:
        if self._param_min is None or self._param_max is None:
            return p_vec
        span = np.where(self._param_max - self._param_min == 0, 1.0, self._param_max - self._param_min)
        return (p_vec - self._param_min) / span

    def predict_metrics(self, params: Dict[str, float]) -> Tuple[Dict[str, float], float]:
        """
        Fast millisecond evaluation of all scalar metrics.
        Returns:
            (predicted_metrics_dict, epistemic_uncertainty)
        """
        p_vec = self._extract_param_vector(params)
        if not self.is_fitted or len(self.param_history) == 0:
            default_metrics = self._get_cold_start_metrics()
            return default_metrics, 1.0

        p_norm = self._normalize_params(p_vec).reshape(1, -1)
        p_norm = np.clip(p_norm, -0.05, 1.05)

        # Calculate distance-based epistemic uncertainty
        X_raw = np.array(self.param_history)
        span = np.where(self._param_max - self._param_min == 0, 1.0, self._param_max - self._param_min)
        X_norm = (X_raw - self._param_min) / span
        dists = np.linalg.norm(X_norm - p_norm, axis=1)
        min_dist = float(np.min(dists))
        uncertainty = float(1.0 - np.exp(-min_dist * 2.0))

        # Predict metrics
        predictions = {}
        for m_key, interp in self._metric_interpolators.items():
            val = float(interp(p_norm)[0])
            predictions[m_key] = val

        return predictions, uncertainty

    def predict(self, params: Dict[str, float]) -> Tuple[Dict[str, float], float]:
        """Convenience alias for predict_metrics."""
        return self.predict_metrics(params)

    def predict_field(self, params: Dict[str, float], enforce_conservation: bool = False) -> Optional[Dict[str, np.ndarray]]:
        """
        Evaluates the full 3D spatial field (N_points, C) for given parameters in milliseconds.
        enforce_conservation: If True, applies Helmholtz-Hodge solenoidal projection to enforce div(u) = 0.
        Returns:
            {'coords': (N, 3), 'values': (N, C), 'channels': [...], ...}
        """
        if not self.is_fitted or self._field_interpolator is None or self.field_coords is None:
            return None

        p_vec = self._extract_param_vector(params)
        p_norm = self._normalize_params(p_vec).reshape(1, -1)
        p_norm = np.clip(p_norm, -0.05, 1.05)
        flat_pred = self._field_interpolator(p_norm)[0]

        n_pts = len(self.field_coords)
        c_channels = len(self.field_channels) if self.field_channels else (len(flat_pred) // n_pts)
        val_grid = flat_pred.reshape((n_pts, c_channels)).astype(np.float32)

        out = {
            "coords": self.field_coords,
            "values": val_grid,
            "channels": self.field_channels
        }

        # Convenient unpacking based on domain
        if self.domain == "cfd" and c_channels >= 4:
            out["U"] = val_grid[:, :3]
            out["p"] = val_grid[:, 3]

            if enforce_conservation:
                try:
                    from pinn_conservation import PhysicsConservationEnforcer
                    enforcer = PhysicsConservationEnforcer()
                    u_proj, div_loss = enforcer.project_divergence_free(self.field_coords, out["U"])
                    out["U"] = u_proj
                    out["divergence_loss"] = div_loss
                    out["vorticity"] = enforcer.compute_vorticity(self.field_coords, u_proj)
                except Exception as e:
                    print(f"[MultiPhysicsSurrogate] Conservation enforcement warning: {e}")

        elif self.domain in ("fea", "structural") and c_channels >= 4:
            out["disp"] = val_grid[:, :3]
            out["von_mises"] = val_grid[:, 3]

            if enforce_conservation:
                try:
                    from pinn_conservation import PhysicsConservationEnforcer
                    enforcer = PhysicsConservationEnforcer()
                    equil_loss = enforcer.compute_structural_equilibrium_loss(self.field_coords, out["disp"])
                    out["equilibrium_loss"] = equil_loss
                except Exception as e:
                    print(f"[MultiPhysicsSurrogate] Conservation enforcement warning: {e}")

        elif self.domain == "em" and c_channels >= 6:
            out["E_re"] = val_grid[:, :3]
            out["E_im"] = val_grid[:, 3:6]

        return out

    def _get_cold_start_metrics(self) -> Dict[str, float]:
        if self.domain == "cfd":
            return {"delta_p": 2500.0, "separation_efficiency": 85.0, "residuals": 1e-3}
        elif self.domain in ("fea", "structural"):
            return {"max_von_mises_stress_MPa": 35.0, "max_displacement_mm": 0.1, "factor_of_safety": 2.0}
        elif self.domain == "em":
            return {"S11": -10.0}
        else:
            return {"objective": 0.0}

    def save(self, file_path: str):
        """Saves surrogate memory to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        data = {
            "domain": self.domain,
            "param_names": self.param_names,
            "kernel": self.kernel,
            "smoothing": self.smoothing,
            "param_history": [p.tolist() for p in self.param_history],
            "metrics_history": self.metrics_history,
            "field_channels": self.field_channels,
            "has_coords": self.field_coords is not None,
            "has_fields": len(self.field_history) > 0,
        }
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        # If 3D fields exist, save companion npz
        if self.field_coords is not None and len(self.field_history) > 0:
            npz_path = file_path.replace(".json", "_fields.npz")
            np.savez_compressed(
                npz_path,
                coords=self.field_coords,
                fields=np.array(self.field_history)
            )

    @classmethod
    def load(cls, file_path: str) -> "MultiPhysicsSurrogate":
        """Loads surrogate memory from disk and refits."""
        with open(file_path, "r") as f:
            data = json.load(f)

        surrogate = cls(
            domain=data.get("domain", "cfd"),
            param_names=data.get("param_names", []),
            kernel=data.get("kernel", "thin_plate_spline"),
            smoothing=data.get("smoothing", 1e-4)
        )
        surrogate.param_history = [np.array(p, dtype=np.float64) for p in data.get("param_history", [])]
        surrogate.metrics_history = data.get("metrics_history", [])
        surrogate.field_channels = data.get("field_channels", [])

        npz_path = file_path.replace(".json", "_fields.npz")
        if os.path.exists(npz_path):
            try:
                loaded_npz = np.load(npz_path)
                surrogate.field_coords = loaded_npz["coords"]
                surrogate.field_history = list(loaded_npz["fields"])
            except Exception as e:
                print(f"[MultiPhysicsSurrogate] Warning: Could not load fields from {npz_path}: {e}")

        surrogate.fit()
        return surrogate
