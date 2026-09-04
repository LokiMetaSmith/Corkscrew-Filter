"""
surrogate_rbf.py

Zero-Training RBF Field and S-Parameter Surrogate.
Uses Radial Basis Functions (scipy.interpolate.RBFInterpolator) to provide
instant (< 2ms) continuous field and metric interpolation from sparse simulation
checkpoints without requiring neural network training.
"""

import os
import json
import pickle
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from scipy.interpolate import RBFInterpolator


class RBFFieldSurrogate:
    """
    Progressive memory-based surrogate using Radial Basis Functions.
    Interpolates scalar metrics (e.g. min S11), S-parameter frequency curves,
    and 3D complex phasor fields (E_re, E_im) across geometric parameter space.
    """

    def __init__(
        self,
        param_names: Optional[List[str]] = None,
        kernel: str = "thin_plate_spline",
        smoothing: float = 1e-4,
        epsilon: Optional[float] = None,
    ):
        self.param_names = param_names or []
        self.kernel = kernel
        self.smoothing = smoothing
        self.epsilon = epsilon

        # Raw observations
        self.param_history: List[np.ndarray] = []  # Normalized or raw vectors
        self.metrics_history: List[Dict[str, float]] = []
        self.sparam_freqs: Optional[np.ndarray] = None
        self.sparam_history: List[np.ndarray] = []  # Array of S11 values across freqs

        # 3D Field observations: stored as flat (N_points, 6) vectors: [Ex_re, Ey_re, Ez_re, Ex_im, Ey_im, Ez_im]
        self.field_coords: Optional[np.ndarray] = None  # (N_points, 3)
        self.field_history: List[np.ndarray] = []  # List of (N_points, 6)

        # Fitted interpolators
        self._metric_interpolators: Dict[str, RBFInterpolator] = {}
        self._sparam_interpolator: Optional[RBFInterpolator] = None
        self._field_interpolator: Optional[RBFInterpolator] = None

        # Normalization bounds
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
        sparam_curve: Optional[Tuple[np.ndarray, np.ndarray]] = None,
        field_data: Optional[Dict[str, np.ndarray]] = None,
    ):
        """
        Record a ground-truth simulation sample.
        sparam_curve: (freqs_hz, s11_db)
        field_data: {'coords': (N, 3), 'E_re': (N, 3), 'E_im': (N, 3)}
        """
        p_vec = self._extract_param_vector(params)
        self.param_history.append(p_vec)

        # Record scalar metrics
        scalar_m = {}
        for k, v in metrics.items():
            if isinstance(v, (int, float)) and np.isfinite(v):
                scalar_m[k] = float(v)
        self.metrics_history.append(scalar_m)

        # Record S-parameters
        if sparam_curve is not None:
            freqs, s11 = sparam_curve
            if self.sparam_freqs is None:
                self.sparam_freqs = np.asarray(freqs, dtype=np.float64)
            self.sparam_history.append(np.asarray(s11, dtype=np.float64))

        # Record Field Data
        if field_data is not None:
            coords = field_data.get("coords")
            e_re = field_data.get("E_re")
            e_im = field_data.get("E_im")
            if coords is not None and e_re is not None and e_im is not None:
                if self.field_coords is None:
                    self.field_coords = np.asarray(coords, dtype=np.float32)
                # Pack 6 components
                packed = np.concatenate([e_re, e_im], axis=-1).astype(np.float32)
                self.field_history.append(packed)

        self.fit()

    def _make_rbf(self, X: np.ndarray, y: np.ndarray) -> RBFInterpolator:
        d = X.shape[1] if X.ndim > 1 else 1
        kwargs = {"kernel": self.kernel, "smoothing": self.smoothing}
        if len(X) <= d + 1:
            kwargs["degree"] = -1  # Disable polynomial drift for very sparse points
        if self.epsilon is not None:
            kwargs["epsilon"] = self.epsilon
        elif self.kernel not in {"linear", "cubic", "quintic", "thin_plate_spline"}:
            kwargs["epsilon"] = 1.0
        return RBFInterpolator(X, y, **kwargs)

    def fit(self):
        """Fits RBF interpolators on all accumulated data."""
        n_samples = len(self.param_history)
        if n_samples == 0:
            return

        X = np.array(self.param_history, dtype=np.float64)
        self._param_min = np.min(X, axis=0)
        self._param_max = np.max(X, axis=0)
        span = self._param_max - self._param_min
        span[span < 1e-9] = 1.0
        X_norm = (X - self._param_min) / span

        if n_samples < 2:
            self.is_fitted = False
            return

        # 1. Fit metric interpolators
        metric_keys = set()
        for m in self.metrics_history:
            metric_keys.update(m.keys())

        self._metric_interpolators = {}
        for k in metric_keys:
            vals = []
            valid_indices = []
            for i, m in enumerate(self.metrics_history):
                if k in m and np.isfinite(m[k]):
                    vals.append(m[k])
                    valid_indices.append(i)
            if len(vals) >= 2:
                self._metric_interpolators[k] = self._make_rbf(X_norm[valid_indices], np.array(vals))

        # 2. Fit S-parameter curve interpolator
        if len(self.sparam_history) == n_samples and n_samples >= 2:
            Y_sparam = np.array(self.sparam_history)
            self._sparam_interpolator = self._make_rbf(X_norm, Y_sparam)

        # 3. Fit 3D Field interpolator
        if len(self.field_history) == n_samples and n_samples >= 2:
            # Flatten each field snapshot to 1D: shape (n_samples, N_points * 6)
            Y_field = np.array([f.flatten() for f in self.field_history])
            self._field_interpolator = self._make_rbf(X_norm, Y_field)

        self.is_fitted = True

    def _normalize_query(self, p_vec: np.ndarray) -> np.ndarray:
        if self._param_min is None or self._param_max is None:
            return p_vec.reshape(1, -1)
        span = self._param_max - self._param_min
        span[span < 1e-9] = 1.0
        norm = (p_vec - self._param_min) / span
        return norm.reshape(1, -1)

    def get_uncertainty(self, params: Dict[str, float]) -> float:
        """
        Returns normalized Euclidean distance to the closest observed parameter set.
        0.0 means an exact hit, > 0.5 indicates extrapolation/high uncertainty.
        """
        if not self.param_history:
            return 1.0
        p_vec = self._extract_param_vector(params)
        q_norm = self._normalize_query(p_vec)[0]
        X = np.array(self.param_history)
        span = (self._param_max - self._param_min) if self._param_max is not None else np.ones_like(p_vec)
        span[span < 1e-9] = 1.0
        X_norm = (X - (self._param_min if self._param_min is not None else 0.0)) / span
        dists = np.linalg.norm(X_norm - q_norm, axis=1)
        return float(np.min(dists))

    def predict_metrics(self, params: Dict[str, float]) -> Tuple[Dict[str, float], float]:
        """
        Predicts scalar metrics and returns (predictions, uncertainty).
        If fewer than 2 samples exist, returns nearest neighbor or defaults.
        """
        uncertainty = self.get_uncertainty(params)
        if not self.param_history:
            return ({"S11": -10.0}, 1.0)

        p_vec = self._extract_param_vector(params)
        if not self.is_fitted or not self._metric_interpolators:
            # Fallback to nearest neighbor
            X = np.array(self.param_history)
            idx = np.argmin(np.linalg.norm(X - p_vec, axis=1))
            return (dict(self.metrics_history[idx]), uncertainty)

        q_norm = self._normalize_query(p_vec)
        out = {}
        for k, interp in self._metric_interpolators.items():
            val = interp(q_norm)[0]
            out[k] = float(val)
        return (out, uncertainty)

    def predict_s_parameters(self, params: Dict[str, float]) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Predicts the continuous S11(f) frequency response curve."""
        if not self.param_history or self.sparam_freqs is None:
            return None
        p_vec = self._extract_param_vector(params)
        if not self.is_fitted or self._sparam_interpolator is None:
            # Nearest neighbor
            X = np.array(self.param_history)
            idx = np.argmin(np.linalg.norm(X - p_vec, axis=1))
            if self.sparam_history:
                return (self.sparam_freqs, self.sparam_history[idx])
            return None

        q_norm = self._normalize_query(p_vec)
        s11_pred = self._sparam_interpolator(q_norm)[0]
        return (self.sparam_freqs, s11_pred)

    def predict_field(self, params: Dict[str, float]) -> Optional[Dict[str, np.ndarray]]:
        """
        Predicts 3D complex phasor electric field vectors.
        Returns {'coords': (N, 3), 'E_re': (N, 3), 'E_im': (N, 3), 'mag': (N,)}
        """
        if not self.field_history or self.field_coords is None:
            return None

        p_vec = self._extract_param_vector(params)
        n_points = len(self.field_coords)

        if not self.is_fitted or self._field_interpolator is None:
            X = np.array(self.param_history)
            idx = np.argmin(np.linalg.norm(X - p_vec, axis=1))
            packed = self.field_history[idx]
        else:
            q_norm = self._normalize_query(p_vec)
            flat_pred = self._field_interpolator(q_norm)[0]
            packed = flat_pred.reshape((n_points, 6))

        e_re = packed[:, :3]
        e_im = packed[:, 3:6]
        mag = np.sqrt(np.sum(e_re**2 + e_im**2, axis=1))
        return {
            "coords": self.field_coords,
            "E_re": e_re,
            "E_im": e_im,
            "mag": mag,
        }

    def save(self, filepath: str):
        """Serializes the surrogate to disk."""
        data = {
            "param_names": self.param_names,
            "kernel": self.kernel,
            "smoothing": self.smoothing,
            "epsilon": self.epsilon,
            "param_history": [p.tolist() for p in self.param_history],
            "metrics_history": self.metrics_history,
            "sparam_freqs": self.sparam_freqs.tolist() if self.sparam_freqs is not None else None,
            "sparam_history": [s.tolist() for s in self.sparam_history],
            "field_coords": self.field_coords.tolist() if self.field_coords is not None else None,
            "field_history": [f.tolist() for f in self.field_history],
        }
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, filepath: str) -> "RBFFieldSurrogate":
        """Loads a saved surrogate from disk."""
        with open(filepath, "r") as f:
            data = json.load(f)
        surrogate = cls(
            param_names=data.get("param_names"),
            kernel=data.get("kernel", "thin_plate_spline"),
            smoothing=data.get("smoothing", 1e-4),
            epsilon=data.get("epsilon"),
        )
        surrogate.param_history = [np.array(p, dtype=np.float64) for p in data.get("param_history", [])]
        surrogate.metrics_history = data.get("metrics_history", [])
        if data.get("sparam_freqs"):
            surrogate.sparam_freqs = np.array(data["sparam_freqs"], dtype=np.float64)
            surrogate.sparam_history = [np.array(s, dtype=np.float64) for s in data.get("sparam_history", [])]
        if data.get("field_coords"):
            surrogate.field_coords = np.array(data["field_coords"], dtype=np.float32)
            surrogate.field_history = [np.array(f, dtype=np.float32) for f in data.get("field_history", [])]
        surrogate.fit()
        return surrogate
