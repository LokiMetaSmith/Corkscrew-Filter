from typing import Dict, Any, Tuple

# Target metrics defined by the user
TARGET_PRESSURE_DROP_PSI = 0.7
TARGET_EFFICIENCY_PERCENT = 99.95

# Constants for conversion
RHO_AIR = 1.225 # kg/m^3 (approximate)
PSI_TO_PA = 6894.76

def calculate_score(metrics: Dict[str, Any], config: Dict[str, Any] = None) -> Tuple[float, float, float, float]:
    """
    Calculates a score for a given run based on its metrics.
    Returns a tuple used for sorting (higher is better).

    Sorting Logic:
    1. Validity: Non-error runs are prioritized.
    2. Target Met: If efficiency >= 99.95%, prioritized.
    3. Pressure Drop: Lower is better (so we use negative).
    4. Efficiency: Higher is better.
    """
    if not metrics or "error" in metrics:
        return (-1.0, 0.0, 0.0, 0.0)

    # Check if a custom objective function is defined in config
    objective = None
    target = 'maximize'
    if config and 'optimization' in config:
        objective = config['optimization'].get('objective_function')
        target = config['optimization'].get('target', 'maximize')

    if objective and objective in metrics:
        # Simple generic sorting based on objective value
        val = metrics[objective]
        if val is None:
            val = 0.0 if target == 'maximize' else float('inf')

        validity_score = 1.0
        # If minimize, flip sign so larger tuple is better
        score_val = val if target == 'maximize' else -val
        return (validity_score, score_val, 0.0, 0.0)

    # Legacy/Default "Thirsty Corkscrew" logic
    efficiency_pct = metrics.get("separation_efficiency", 0.0)
    delta_p_kinematic = metrics.get("delta_p", float('inf'))

    if efficiency_pct is None: efficiency_pct = 0.0
    if delta_p_kinematic is None: delta_p_kinematic = float('inf')

    # Convert Pressure
    # Assuming delta_p is kinematic pressure (m^2/s^2) -> Pa -> PSI
    # Pressure (Pa) = p_kinematic * rho
    pressure_pa = delta_p_kinematic * RHO_AIR
    pressure_psi = pressure_pa / PSI_TO_PA

    # Primary Score: 1.0 if valid, -1.0 if invalid
    validity_score = 1.0

    # Secondary Score: Efficiency Target
    is_target_met = 1.0 if efficiency_pct >= TARGET_EFFICIENCY_PERCENT else 0.0

    # Sort criteria
    if is_target_met:
        # If target met, minimize pressure drop.
        # We return (validity, met_target, -pressure_psi, efficiency)
        return (validity_score, is_target_met, -pressure_psi, efficiency_pct)
    else:
        # If target NOT met, maximize efficiency.
        # We return (validity, met_target, efficiency, -pressure_psi)
        return (validity_score, is_target_met, efficiency_pct, -pressure_psi)

def compute_pareto_front(history: list, objectives: list = None) -> list:
    """
    Computes non-dominated Pareto front runs from history across multi-objective metrics.
    objectives: list of tuples (metric_key, 'maximize'|'minimize')
    """
    if not history:
        return []

    if objectives is None:
        objectives = [("separation_efficiency", "maximize"), ("delta_p", "minimize")]

    valid_runs = [r for r in history if r.get("metrics") and "error" not in r.get("metrics")]
    if not valid_runs:
        return []

    pareto_runs = []
    for i, run_a in enumerate(valid_runs):
        m_a = run_a["metrics"]
        is_dominated = False

        for j, run_b in enumerate(valid_runs):
            if i == j:
                continue
            m_b = run_b["metrics"]

            # Check if B dominates A
            better_or_equal = True
            strictly_better = False

            for key, direction in objectives:
                val_a = m_a.get(key, 0.0 if direction == "maximize" else float('inf'))
                val_b = m_b.get(key, 0.0 if direction == "maximize" else float('inf'))

                if direction == "maximize":
                    if val_b < val_a:
                        better_or_equal = False
                    if val_b > val_a:
                        strictly_better = True
                else: # minimize
                    if val_b > val_a:
                        better_or_equal = False
                    if val_b < val_a:
                        strictly_better = True

            if better_or_equal and strictly_better:
                is_dominated = True
                break

        if not is_dominated:
            pareto_runs.append(run_a)

    return pareto_runs

def export_pareto_plot(history: list, output_path: str = "exports/pareto_front.png", objectives: list = None):
    """
    Generates a 2D/3D scatter plot highlighting the non-dominated Pareto front.
    """
    import os
    import matplotlib.pyplot as plt

    if objectives is None:
        objectives = [("separation_efficiency", "maximize"), ("delta_p", "minimize")]

    pareto_front = compute_pareto_front(history, objectives)

    obj1_key, obj1_dir = objectives[0]
    obj2_key, obj2_dir = objectives[1]

    all_x = [r["metrics"].get(obj1_key, 0.0) for r in history if r.get("metrics") and "error" not in r["metrics"]]
    all_y = [r["metrics"].get(obj2_key, 0.0) for r in history if r.get("metrics") and "error" not in r["metrics"]]

    pf_x = [r["metrics"].get(obj1_key, 0.0) for r in pareto_front]
    pf_y = [r["metrics"].get(obj2_key, 0.0) for r in pareto_front]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(all_x, all_y, color="#89b4fa", alpha=0.6, label="All Runs", s=30)
    ax.scatter(pf_x, pf_y, color="#f38ba8", alpha=0.9, label="Pareto Front", s=80, edgecolors="black")

    ax.set_xlabel(f"{obj1_key} ({obj1_dir})")
    ax.set_ylabel(f"{obj2_key} ({obj2_dir})")
    ax.set_title("Multi-Objective Optimization Pareto Frontier")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path

def is_top_performer(run: Dict[str, Any], all_runs: list, config: Dict[str, Any] = None, top_n: int = 10) -> bool:
    """
    Determines if a specific run is in the top N performers of all provided runs.
    """
    if not all_runs:
        return True

    # Sort all runs by score (descending)
    sorted_runs = sorted(all_runs, key=lambda r: calculate_score(r.get("metrics", {}), config), reverse=True)

    # Get the top N
    top_runs = sorted_runs[:top_n]

    # Check if run is in top_runs (by ID or reference)
    run_id = run.get("id")
    for top_run in top_runs:
        if run_id and top_run.get("id") == run_id:
            return True
        if run is top_run:
            return True

    return False
