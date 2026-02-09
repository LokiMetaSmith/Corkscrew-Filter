from typing import Dict, Any, Tuple

# Target metrics defined by the user
TARGET_PRESSURE_DROP_PSI = 0.7
TARGET_EFFICIENCY_PERCENT = 99.95

# Constants for conversion
RHO_AIR = 1.225 # kg/m^3 (approximate)
PSI_TO_PA = 6894.76

def calculate_score(metrics: Dict[str, Any]) -> Tuple[float, float, float, float]:
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

    # Extract raw metrics
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

def is_top_performer(run: Dict[str, Any], all_runs: list, top_n: int = 10) -> bool:
    """
    Determines if a specific run is in the top N performers of all provided runs.
    """
    if not all_runs:
        return True

    # Sort all runs by score (descending)
    sorted_runs = sorted(all_runs, key=lambda r: calculate_score(r.get("metrics", {})), reverse=True)

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
