import json

# Or maybe `p_min is None`?
# In `configs/corkscrew_config.yaml`:
# helix_profile_radius_mm: { type: "float", min: 1.5, max: 5.0, default: 1.7 }
# It has min and max!

# Oh! Wait!
# In `configs/corkscrew_config.yaml`:
#   parameters:
#     part_to_generate: { type: "string", default: "modular_filter_assembly" }
#     num_bins: { type: "int", min: 1, max: 3, default: 1 }

# If `config.get('geometry', {}).get('parameters', {})` is passed to `_generate_random_parameters`,
# YES, `ordered_params` WILL have `helix_profile_radius_mm`!

# Could there be a bug in python `min(current_p_max, float(new_params["helix_path_radius_mm"]) - 0.01)`?
# Let's write the exact loop.
import random
new_params = {"helix_path_radius_mm": 3.93}
current_p_max = 5.0
current_p_min = 1.5
current_p_max = min(current_p_max, float(new_params["helix_path_radius_mm"]) - 0.01)
print(current_p_max) # 3.92
if current_p_min > current_p_max:
    current_p_max = current_p_min
print("After check:", current_p_max)
print("Generated:", round(random.uniform(current_p_min, current_p_max), 2))
