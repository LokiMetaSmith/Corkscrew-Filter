import yaml
with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

parameters_def = config['geometry']['parameters']
dependency_order = [
    "tube_od_mm",
    "tube_wall_mm",
    "cyclone_diameter",
    "vortex_finder_diameter",
    "inlet_width",
    "helix_path_radius_mm",
    "helix_profile_radius_mm",
    "helix_void_profile_radius_mm",
    "slit_axial_length_mm",
    "slit_chamfer_height"
]
ordered_params = []
for key in dependency_order:
    if key in parameters_def:
        ordered_params.append((key, parameters_def[key]))
for key, info in parameters_def.items():
    if key not in dependency_order:
        ordered_params.append((key, info))

counts = {}
for k, v in ordered_params:
    counts[k] = counts.get(k, 0) + 1

for k, c in counts.items():
    if c > 1:
        print(f"DUPLICATE KEY: {k}")
print("Done checking duplicates.")
