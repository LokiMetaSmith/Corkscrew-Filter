import yaml
import random
from optimizer.llm_agent import LLMAgent
from optimizer.parameter_validator import validate_parameters

with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

agent = LLMAgent(None)
params_def = config['geometry']['parameters']

# WAIT. `ordered_params` is populated by iterating over `parameters_def`.
# BUT what if `parameters_def` contains properties that are NOT handled in `ordered_params` correctly?
# Look at `test_llm_agent28.py`!
# `res` had:
# 'tube_od_mm': {'type': 'float', 'default': 32.0, 'constant': True}

# WAIT! If `res` HAS DICTIONARIES, and then `main.py` saves it to `optimization_log.jsonl`?! No, it failed validation.
# If it fails validation, it might NOT be saved.
# Wait, `validate_parameters` in `parameter_validator.py`:
# `tube_od = float(params.get("tube_od_mm", 32))`
# If `params["tube_od_mm"]` is a DICTIONARY `{'type': 'float', ...}`, THEN `float(dictionary)` raises `TypeError`!
# "Parameter type error: float() argument must be a string or a real number, not 'dict'"
