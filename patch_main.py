import re

with open('optimizer/main.py', 'r') as f:
    content = f.read()

patch = """<<<<<<< SEARCH
    else:
        # Extract default parameters from YAML config
        initial_params = {}
        for param_name, param_def in config.get('geometry', {}).get('parameters', {}).items():
            if 'default' in param_def:
                initial_params[param_name] = param_def['default']
=======
    else:
        # Extract default parameters from YAML config
        initial_params = {}
        for param_name, param_def in config.get('geometry', {}).get('parameters', {}).items():
            if 'default' in param_def:
                initial_params[param_name] = param_def['default']
            elif param_def.get('constant', False) and 'value' in param_def:
                initial_params[param_name] = param_def['value']
>>>>>>> REPLACE"""

with open('patch_main.diff', 'w') as f:
    f.write(patch)
