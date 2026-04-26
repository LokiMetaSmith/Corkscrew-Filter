import json
import yaml

with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

print("Wait... is `ordered_params` populated incorrectly?!")
print("Let's look at how `ordered_params` is populated:")
#         for key in dependency_order:
#             if key in parameters_def:
#                 ordered_params.append((key, parameters_def[key]))
#         for key, info in parameters_def.items():
#             if key not in dependency_order:
#                 ordered_params.append((key, info))
