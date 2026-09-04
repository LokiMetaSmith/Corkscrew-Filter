"""
rl_policy_agent.py

Reinforcement Learning Policy Agent for Active Geometric Morphing.
Learns continuous parameter modification policies using contextual policy gradients.
Adapts online from solver residuals and multi-objective performance feedback.
"""

import os
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple


class GeometryRLPolicyAgent:
    """
    Contextual Policy Gradient agent for intelligent geometry morphing.
    Maps current simulation state & constraints to continuous parameter modification actions.
    """

    def __init__(
        self,
        param_defs: Dict[str, Any],
        learning_rate: float = 0.05,
        exploration_noise: float = 0.20,
        baseline_decay: float = 0.90,
        model_path: str = "artifacts/rl_policy_weights.json"
    ):
        self.param_defs = param_defs
        self.param_names = sorted(list(param_defs.keys()))
        self.d_action = len(self.param_names)
        self.learning_rate = learning_rate
        self.exploration_noise = exploration_noise
        self.baseline_decay = baseline_decay
        self.model_path = model_path

        # State representation size:
        # [p_norm (d), metric_norm (4), target_err (4), uncertainty (1)] = d + 9
        self.d_state = self.d_action + 9

        # Policy Network Weights: W (d_action, d_state), b (d_action,)
        # Initialize with small Gaussian weights
        np.random.seed(42)
        self.W = np.random.normal(0, 0.05, (self.d_action, self.d_state)).astype(np.float64)
        self.b = np.zeros(self.d_action, dtype=np.float64)

        # Baseline value for variance reduction
        self.baseline_reward: float = 0.0
        self.experience_history: List[Dict[str, Any]] = []

        # Load existing weights if available
        if os.path.exists(self.model_path):
            self.load(self.model_path)

    def _get_bounds(self, param_name: str) -> Tuple[float, float]:
        defn = self.param_defs.get(param_name, {})
        p_min = float(defn.get("min", 0.0) or 0.0)
        p_max = float(defn.get("max", 100.0) or 100.0)
        return p_min, p_max

    def construct_state_vector(
        self,
        current_params: Dict[str, float],
        current_metrics: Dict[str, float],
        uncertainty: float = 0.5
    ) -> np.ndarray:
        """Builds standardized state vector s."""
        state = []

        # 1. Normalized parameters
        for p in self.param_names:
            p_min, p_max = self._get_bounds(p)
            span = max(p_max - p_min, 1e-6)
            norm_val = (float(current_params.get(p, p_min)) - p_min) / span
            state.append(np.clip(norm_val, 0.0, 1.0))

        # 2. Normalized metrics
        delta_p = float(current_metrics.get("delta_p", 2500.0)) / 5000.0
        eff = float(current_metrics.get("separation_efficiency", 85.0)) / 100.0
        vm = float(current_metrics.get("max_von_mises_stress_MPa", 30.0)) / 60.0
        fos = float(current_metrics.get("factor_of_safety", 2.0)) / 3.0
        state.extend([delta_p, eff, vm, fos])

        # 3. Target errors (Goal: delta_p < 0.7 PSI = ~4826 Pa, eff > 99.95%, FoS >= 1.5, vm < 60)
        err_p = max(0.0, (float(current_metrics.get("delta_p", 2500.0)) - 4826.0) / 4826.0)
        err_eff = max(0.0, (99.95 - float(current_metrics.get("separation_efficiency", 85.0))) / 100.0)
        err_fos = max(0.0, (1.5 - float(current_metrics.get("factor_of_safety", 2.0))) / 1.5)
        err_vm = max(0.0, (float(current_metrics.get("max_von_mises_stress_MPa", 30.0)) - 60.0) / 60.0)
        state.extend([err_p, err_eff, err_fos, err_vm])

        # 4. Epistemic uncertainty
        state.append(np.clip(float(uncertainty), 0.0, 1.0))

        return np.array(state, dtype=np.float64)

    def predict_action(
        self,
        state: np.ndarray,
        deterministic: bool = False
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Samples action a from Gaussian policy pi(a|s).
        Returns: (action, raw_mean)
        """
        # Linear layer with tanh squashing to [-1, 1]
        mean_action = np.tanh(np.dot(self.W, state) + self.b)

        if deterministic:
            return mean_action, mean_action

        noise = np.random.normal(0, self.exploration_noise, size=self.d_action)
        action = np.clip(mean_action + noise, -1.0, 1.0)
        return action, mean_action

    def morph_parameters(
        self,
        base_params: Dict[str, float],
        action: np.ndarray,
        step_scale: float = 0.15
    ) -> Dict[str, float]:
        """Applies action vector as parameter perturbations."""
        morphed = {}
        for i, p in enumerate(self.param_names):
            p_min, p_max = self._get_bounds(p)
            span = p_max - p_min
            delta = float(action[i]) * (step_scale * span)
            new_val = np.clip(float(base_params.get(p, p_min)) + delta, p_min, p_max)
            morphed[p] = float(new_val)
        return morphed

    def compute_reward(
        self,
        metrics: Dict[str, float],
        domain: str = "cfd"
    ) -> float:
        """
        Computes scalar multi-physics reward R.
        """
        reward = 0.0

        if domain == "cfd":
            eff = float(metrics.get("separation_efficiency", 85.0))
            delta_p = float(metrics.get("delta_p", 2500.0))
            # Reward: 0 to 10 for efficiency + penalty for high pressure
            reward += (eff / 10.0)
            if eff >= 99.95:
                reward += 5.0  # Milestone bonus
            # Pressure penalty: 4826 Pa (0.7 PSI) is the limit
            if delta_p > 4826.0:
                reward -= (delta_p - 4826.0) / 1000.0

        elif domain in ("fea", "structural"):
            vm = float(metrics.get("max_von_mises_stress_MPa", 30.0))
            fos = float(metrics.get("factor_of_safety", 2.0))
            reward += (fos * 2.0)
            if vm > 60.0:
                reward -= ((vm - 60.0) / 10.0) * 3.0

        elif domain == "joint":
            eff = float(metrics.get("separation_efficiency", 85.0))
            delta_p = float(metrics.get("delta_p", 2500.0))
            fos = float(metrics.get("factor_of_safety", 2.0))
            reward += (eff / 15.0) + (fos * 1.5) - (delta_p / 3000.0)

        elif domain == "em":
            s11 = float(metrics.get("S11", -10.0))
            reward += (-s11 / 2.0)  # Lower S11 gives higher reward

        return float(reward)

    def update_policy(
        self,
        state: np.ndarray,
        action: np.ndarray,
        mean_action: np.ndarray,
        reward: float
    ) -> float:
        """
        Performs policy gradient update:
        grad_log_pi = (action - mean_action) / (noise^2) * (1 - mean^2) * s^T
        """
        # Compute advantage over running baseline
        if len(self.experience_history) == 0:
            self.baseline_reward = reward
        else:
            self.baseline_reward = (
                self.baseline_decay * self.baseline_reward
                + (1.0 - self.baseline_decay) * reward
            )

        advantage = reward - self.baseline_reward

        # Gradient of log-likelihood for Gaussian policy with tanh mean
        noise_var = max(self.exploration_noise ** 2, 1e-4)
        error = (action - mean_action) / noise_var
        dtanh = (1.0 - mean_action ** 2)
        grad_out = error * dtanh  # (d_action,)

        grad_W = np.outer(grad_out, state)  # (d_action, d_state)
        grad_b = grad_out                   # (d_action,)

        # Policy update step
        self.W += self.learning_rate * advantage * np.clip(grad_W, -2.0, 2.0)
        self.b += self.learning_rate * advantage * np.clip(grad_b, -2.0, 2.0)

        record = {
            "reward": reward,
            "advantage": advantage,
            "action_norm": float(np.linalg.norm(action))
        }
        self.experience_history.append(record)
        return advantage

    def save(self, file_path: Optional[str] = None):
        target = file_path or self.model_path
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        data = {
            "param_names": self.param_names,
            "W": self.W.tolist(),
            "b": self.b.tolist(),
            "baseline_reward": float(self.baseline_reward),
            "experience_count": len(self.experience_history)
        }
        with open(target, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, file_path: str):
        with open(file_path, "r") as f:
            data = json.load(f)
        self.param_names = data.get("param_names", self.param_names)
        self.W = np.array(data["W"], dtype=np.float64)
        self.b = np.array(data["b"], dtype=np.float64)
        self.baseline_reward = float(data.get("baseline_reward", 0.0))
