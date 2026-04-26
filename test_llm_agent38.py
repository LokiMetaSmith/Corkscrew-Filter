import yaml
with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Ah! Look at `main.py` line 192:
# random_params = agent._generate_random_parameters(base_params, config.get('geometry', {}).get('parameters', {}))
# So `parameters_def` IS `config.get('geometry', {}).get('parameters', {})`
# Are there ANY properties in `parameters_def`?
print("parameters_def keys:", config.get('geometry', {}).get('parameters', {}).keys())

# Yes! `helix_profile_radius_mm` is there!
# Then `ordered_params` WILL contain `helix_profile_radius_mm` and its `param_info` will have `min: 1.5, max: 5.0`.
# AND `p_min` will be 1.5, `p_max` will be 5.0.
# So `if p_min is not None and p_max is not None:` WILL EXECUTE.
# THEN IT WILL CALL `random.uniform(current_p_min, current_p_max)`.
# Since `current_p_min` is 1.5 and `current_p_max` is 3.92, `new_params["helix_profile_radius_mm"]` CANNOT BE 4.85!
# Unless `random.uniform(1.5, 3.92)` somehow returns 4.85! (Impossible).
# SO HOW DID IT BECOME 4.85?!
# ONLY if `ordered_params` DID NOT contain `helix_profile_radius_mm`?!
# Why would `ordered_params` not contain it?
# Because `main.py` passes SOMETHING ELSE as `parameters_def`?!
# `config.get('geometry', {}).get('parameters', {})` is exactly what is passed.
