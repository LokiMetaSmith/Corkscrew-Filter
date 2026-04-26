import json

# WHAT IF `current_params` has `helix_profile_radius_mm` = 4.85 AND `ordered_params` loop DOES NOT EXECUTE FOR IT?!
# WHY would it not execute for it?
# Because `config.get('geometry', {}).get('parameters', {})` DOES NOT CONTAIN IT!
# Let's check `configs/corkscrew_config.yaml` AGAIN.
# Is it possible that the user passed a DIFFERENT config file?
# "Using Configuration File: configs/corkscrew_config.yaml"
# So it's the SAME config file.

# THEN IT MUST BE IN `parameters_def`.
# THEN IT MUST BE IN `ordered_params`.

# What if `if param_info.get('constant', False): continue` IS TRIGGERED?
# `param_info` for `helix_profile_radius_mm` is:
# `{ type: "float", min: 1.5, max: 5.0, default: 1.7 }`
# `.get('constant', False)` returns `False`.
# SO IT IS NOT TRIGGERED.

# SO IT MUST GO TO `p_min = ...`, `p_max = ...`.
# `p_min` is 1.5, `p_max` is 5.0.
# BOTH ARE NOT NONE!
# SO it MUST GO to `if p_min is not None and p_max is not None:`!
# SO it MUST CALL `random.uniform`!
# IF IT CALLS `random.uniform`, it GENERATES a new value.

# IF IT GENERATES A NEW VALUE, HOW COULD IT BE 4.85 WHEN `helix_path_radius_mm` WAS GENERATED AS 3.93?!
# Let's say `helix_path_radius_mm` is generated as 3.93.
# Then `current_p_max = min(5.0, 3.93 - 0.01) = 3.92`.
# `random.uniform(1.5, 3.92)` CANNOT return 4.85.

# THE ONLY WAY is if `helix_path_radius_mm` was generated as >= 4.86!
# IF `helix_path_radius_mm` was >= 4.86, then `random.uniform(1.5, 4.85)` COULD return 4.85!
