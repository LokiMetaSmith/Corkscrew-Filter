import json

# Okay, wait.
# We know that `base_params` is taken from `full_history[-1]["parameters"]`.
# And we saw from `optimization_log.jsonl` that `full_history[-1]["parameters"]` is:
last_params = {"number_of_complete_revolutions": 1.06, "num_bins": 1, "helix_path_radius_mm": 2.76, "helix_profile_radius_mm": 2.7, "helix_void_profile_radius_mm": 0.9, "helix_profile_scale_ratio": 1.33, "insert_length_mm": 50.33, "slit_axial_length_mm": 2.89, "slit_chamfer_height": 0.26, "target_cell_size": 4.54, "part_to_generate": "modular_filter_assembly", "add_layers": True}
# Let's pass THIS EXACT DICTIONARY into `_generate_random_parameters` and see what happens!

import yaml
from optimizer.llm_agent import LLMAgent
from optimizer.parameter_validator import validate_parameters
agent = LLMAgent(None)
with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

print(validate_parameters(last_params))
res = agent._generate_random_parameters(last_params, config['geometry']['parameters'])
print(res)
