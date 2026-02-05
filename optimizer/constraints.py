# Optimization Constraints & Goals
# This file is used by both the single-step optimizer (main.py) and the campaign generator (generate_campaign.py)
# to guide the LLM's parameter suggestions.

CONSTRAINTS = """
    - tube_od_mm must be 32 (hard constraint for fit).
    - insert_length_mm should be around 50.
    - helix_path_radius_mm > helix_void_profile_radius_mm (to ensure structural integrity if solid, but for fluid volume this defines the channel).
    - helix_profile_radius_mm must be > helix_void_profile_radius_mm (e.g., by at least 1mm) to generate valid geometry.
    - num_bins should be integer >= 1.
    - Optimization Goal: Maximize particle collection efficiency (trap moon dust) while minimizing pressure drop.
    - Consider increasing number_of_complete_revolutions to increase centrifugal force.
    - Experiment with `slit_axial_length_mm` (range: 1.0 - 3.0) and `slit_chamfer_height` (range: 0.1 - 1.0) to optimize particle rejection at the slit.
    - Ensure `slit_chamfer_height` < `slit_axial_length_mm`.
"""
