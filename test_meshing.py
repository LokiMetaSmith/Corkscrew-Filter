import os
import sys
import shutil

sys.path.append("optimizer")
from optimizer.scad_driver import ScadDriver
from optimizer.foam_driver import FoamDriver
from optimizer.simulation_runner import run_simulation

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

res = run_simulation(scad_driver, foam_driver, params, output_stl_name="corkscrew_fluid.stl", skip_cfd=False)
print("Simulation result:", res[0])
