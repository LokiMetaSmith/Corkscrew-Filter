import json
from optimizer.parameter_validator import validate_parameters

# IF IT WAS NEWLY GENERATED, WHY DID IT FAIL VALIDATION?!
# The validation error is:
# Invalid Geometry: Helix profile radius (4.85mm) must be strictly less than helix path radius (3.93mm) to avoid center-axis singularity.

# SO IT GENERATED 4.85 AND 3.93!
# How could it generate 4.85 for profile and 3.93 for path?
# Let's trace `_generate_random_parameters` with 4.85 and 3.93.

# 1. `new_params = current_params.copy()`
# 2. `param_name` = "helix_path_radius_mm".
#    `p_min` = 1.5, `p_max` = 5.0
#    Generates a number, let's say it generates 3.93.
# 3. `param_name` = "helix_profile_radius_mm".
#    `p_min` = 1.5, `p_max` = 5.0
#    `if param_name == "helix_profile_radius_mm" and "helix_path_radius_mm" in new_params:`
#        `current_p_max = min(5.0, 3.93 - 0.01) = 3.92`
#    `new_params["helix_profile_radius_mm"]` = random.uniform(1.5, 3.92).

# IT IS IMPOSSIBLE FOR `random.uniform(1.5, 3.92)` TO GENERATE 4.85!
# UNLESS `ordered_params` DOES NOT CONTAIN `helix_profile_radius_mm`?!
# When would `ordered_params` NOT contain it?
# If `parameters_def` passed to `_generate_random_parameters` DOES NOT contain it!
# Is it possible that `config.get('geometry', {}).get('parameters', {})` does not contain it?
# In my tests it does!

# WAIT! Is it possible that `current_params` ALREADY HAD 4.85 for `helix_profile_radius_mm`?
# And it did NOT get overwritten because it was NOT in `ordered_params`?
# YES!
# If it was in `current_params` (which is `base_params`, which came from `full_history[-1]["parameters"]`), and `ordered_params` did NOT overwrite it, then it would stay 4.85!
# But WHY wouldn't `ordered_params` overwrite it?
# Because it's NOT in `ordered_params`!
# Why is it not in `ordered_params`?
# Look at `llm_agent.py` line 397:
# if param_info.get('constant', False):
#     continue

# AH!!!!!!!!!!
# IF IT'S MARKED AS CONSTANT, IT SKIPS IT!
# IS `helix_profile_radius_mm` MARKED AS CONSTANT?!
