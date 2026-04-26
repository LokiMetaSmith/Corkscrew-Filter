import json

# Okay. It does not appear twice.
# So `helix_path_radius_mm` is generated ONCE per attempt.
# And `helix_profile_radius_mm` is generated AFTER it.
# So `helix_profile_radius_mm` MUST BE <= `helix_path_radius_mm` - 0.01 in EVERY ATTEMPT.

# IF `helix_profile_radius_mm` MUST BE <= `helix_path_radius_mm` in EVERY ATTEMPT,
# HOW ON EARTH CAN `helix_profile_radius_mm` BE 4.85 AND `helix_path_radius_mm` BE 3.93?!?!?!

# Wait!
# Could it be that `validate_parameters(new_params)` returns TRUE,
# BUT `main.py` MODIFIES THE PARAMETERS AFTER `_generate_random_parameters` RETURNS THEM?!
# Let's check `main.py`!
# 192: random_params = agent._generate_random_parameters(base_params, config.get('geometry', {}).get('parameters', {}))
# 193: if get_params_hash(random_params) not in visited_params:
# 194:     parameter_queue.append(random_params)
#
# 211: while parameter_queue:
# 212:     params = parameter_queue.pop(0)
# 216:     job_id = manager.create_job(params)

# Is `params` modified by `manager.create_job`?
# Is `current_params` in `else:` block modified?
# 277: current_params = parameter_queue.pop(0)
# 286: print(f"Testing parameters: {current_params}")
