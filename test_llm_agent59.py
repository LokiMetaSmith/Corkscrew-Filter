import json
import yaml

with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Ah! If `full_history[-1]["parameters"]` did NOT have `tube_od_mm` or `GENERATE_CFD_VOLUME`, then `base_params` doesn't have them!
# BUT WHY DID `_generate_random_parameters` RETURN AN INVALID COMBINATION?!
# Is there a bug in my manual tracing of `_generate_random_parameters`?
# Let's pass EXACTLY the user log dictionary into `validate_parameters` to see if it's really invalid.
# Yes, it is invalid: 4.85 >= 3.93.

# How could `_generate_random_parameters` generate 4.85 and 3.93?!
# Let's look at `_generate_random_parameters` limit logic:
# if param_name == "helix_profile_radius_mm" and "helix_path_radius_mm" in new_params:
#    current_p_max = min(current_p_max, float(new_params["helix_path_radius_mm"]) - 0.01)

# Is it possible that `ordered_params` does NOT execute for `helix_profile_radius_mm`?
# NO, we checked that.
# Is it possible that `float(new_params["helix_path_radius_mm"])` FAILS?
# NO.
# Is it possible that `current_p_min > current_p_max` triggers, and `current_p_min` IS 4.85?!
# NO, `current_p_min` is from `param_info.get('min')`, which is 1.5.

# WAIT. WHAT IF `_generate_random_parameters` WAS NEVER CALLED?!
# But the log says "Using random search strategy..."!
# SO IT WAS CALLED.

# WHAT IF `_generate_random_parameters` RETURNED SOMETHING ELSE, BUT `main.py` APPENDED `base_params` INSTEAD?!
# Let's look at `main.py`:
# 191: base_params = full_history[-1]["parameters"] if full_history else initial_params
# 192: random_params = agent._generate_random_parameters(base_params, config.get('geometry', {}).get('parameters', {}))
# 193: if get_params_hash(random_params) not in visited_params:
# 194:     parameter_queue.append(random_params)

# No, it appends `random_params`.

# OKAY, WHAT IF `random_params` WAS VALID, AND APPENDED TO `parameter_queue`, BUT `parameter_queue` ALREADY HAD THE INVALID ONE?!
# WHERE COULD THE INVALID ONE COME FROM?!
