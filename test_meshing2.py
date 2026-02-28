import os
import sys
import shutil

sys.path.append("optimizer")
from optimizer.scad_driver import ScadDriver
from optimizer.foam_driver import FoamDriver

params = {
    'part_to_generate': 'modular_filter_assembly',
    'num_bins': 1,
    'number_of_complete_revolutions': 2,
    'helix_path_radius_mm': 8.0,
    'helix_profile_radius_mm': 4.0,
    'helix_void_profile_radius_mm': 3.0,
    'tube_od_mm': 32,
    'insert_length_mm': 50,
    'GENERATE_CFD_VOLUME': True,
    'add_layers': False
}

scad_driver = ScadDriver("corkscrew.scad")
foam_driver = FoamDriver("corkscrewFilter", num_processors=1)

assets = scad_driver.generate_cfd_assets(params, "corkscrewFilter/constant/triSurface")
if not assets:
    print("Failed to generate assets")
    sys.exit(1)

for key, path in assets.items():
    scad_driver.scale_mesh(path, 0.001)

# we need blockMesh bounds too
bounds = scad_driver.get_bounds(assets['fluid'])
import numpy as np
foam_driver.update_blockMesh(np.array(bounds), margin=np.array([1.2, 1.2, 0.95]), target_cell_size=0.002)

# update internal point
foam_driver.update_snappyHexMesh_location(np.array(bounds), helix_path_radius_mm=8.0)

foam_driver.prepare_case()

# pass dict with filenames
asset_filenames = {k: os.path.basename(v) for k, v in assets.items()}
success = foam_driver.run_meshing(log_file="test_meshing.log", bin_config={"num_bins": 1}, stl_assets=asset_filenames, add_layers=False)
print("Meshing success:", success)
