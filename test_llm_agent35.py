# Is `validate_parameters` imported from different modules that have different logic?
# `llm_agent.py` imports: `from parameter_validator import validate_parameters`
# `simulation_runner.py` imports: `from parameter_validator import validate_parameters`
# They are exactly the same!

# Let's run `validate_parameters` on that EXACT dictionary:
from optimizer.parameter_validator import validate_parameters
params = {'number_of_complete_revolutions': 3.06, 'num_bins': 1, 'helix_path_radius_mm': 3.93, 'helix_profile_radius_mm': 4.85, 'helix_void_profile_radius_mm': 1.93, 'helix_profile_scale_ratio': 1.71, 'insert_length_mm': 45.4, 'slit_axial_length_mm': 2.07, 'slit_chamfer_height': 0.97, 'target_cell_size': 1.95, 'part_to_generate': 'modular_filter_assembly', 'add_layers': True}
print(validate_parameters(params))
