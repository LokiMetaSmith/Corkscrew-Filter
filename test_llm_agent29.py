import yaml
import json

with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Ah! In main.py `initial_params` IS evaluated correctly:
initial_params = {}
for param_name, param_def in config.get('geometry', {}).get('parameters', {}).items():
    if 'default' in param_def:
        initial_params[param_name] = param_def['default']
print(initial_params)

# If `initial_params` is evaluated correctly, why did `test_llm_agent28.py` fail?
# Because in test_llm_agent28.py, I PASSED `config['geometry']['parameters']` directly!
# But in `main.py`, `base_params = full_history[-1]["parameters"] if full_history else initial_params`
# So `base_params` is EITHER a valid parameter dict from history, OR `initial_params`.
# BOTH are valid parameter dictionaries (e.g., {'tube_od_mm': 32.0, ...}).
# So my theory about `base_params` containing dictionaries was WRONG.

# THEN WHY DID IT FAIL?
# Let's run `_generate_random_parameters` with the ACTUAL `initial_params` 1000 times to see if it fails.
import random
from optimizer.llm_agent import LLMAgent
from optimizer.parameter_validator import validate_parameters
agent = LLMAgent(None)

fails = 0
for i in range(1000):
    res = agent._generate_random_parameters(initial_params, config['geometry']['parameters'])
    if not validate_parameters(res)[0]:
        fails += 1

print(f"Failed {fails} out of 1000 runs")
