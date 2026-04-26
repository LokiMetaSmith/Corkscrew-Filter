import yaml
import random
from optimizer.llm_agent import LLMAgent
from optimizer.parameter_validator import validate_parameters

with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

agent = LLMAgent(None)
params_def = config.get('geometry', {}).get('parameters', {})

print("length of params_def:", len(params_def))
# This is NOT empty.
# BUT wait! Look at `main.py` line 192:
# random_params = agent._generate_random_parameters(base_params, config.get('geometry', {}).get('parameters', {}))
# This is NOT empty!

# So `ordered_params` WILL NOT BE EMPTY!
# IF `ordered_params` IS NOT EMPTY, it will overwrite the parameters.
# IF it overwrites the parameters, it will generate a VALID configuration.
# If it generates a VALID configuration, `validate_parameters` will return True, and it will return that VALID configuration.
# But it DID NOT return a valid configuration!

# What if `is_valid, _ = validate_parameters(new_params)` returns `True` for that INVALID configuration?!
# Wait, I just tested it in `test_llm_agent35.py`:
# params = {'number_of_complete_revolutions': 3.06, 'num_bins': 1, 'helix_path_radius_mm': 3.93, 'helix_profile_radius_mm': 4.85, ...}
# print(validate_parameters(params)) -> `(False, 'Invalid Geometry...')`

# IF `validate_parameters` RETURNS FALSE, AND `ordered_params` IS NOT EMPTY.
# THEN IT LOOPS 100 TIMES AND FAILS, AND PRINTS THE WARNING!
# BUT THE WARNING WAS NOT IN THE USER LOG!

# IS IT POSSIBLE THAT THE SCRIPT I AM LOOKING AT IS NOT THE SAME SCRIPT THAT THE USER RAN?!
# Yes, if I look at `git log`, maybe they modified it?
# Let's check `git status`.
