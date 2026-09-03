"""
build123d_examples.py
Demonstrates 3D model generation, STL & STEP export, and metric calculations
for all build123d parametric CAD models in OpenAuto-CFD.
"""

import os
import sys

# Add optimizer directory to python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
optimizer_dir = os.path.join(repo_root, "optimizer")
if optimizer_dir not in sys.path:
    sys.path.insert(0, optimizer_dir)

from build123d_driver import Build123dDriver

def main():
    out_dir = os.path.join(repo_root, "exports", "examples")
    os.makedirs(out_dir, exist_ok=True)
    print(f"=== OpenAuto-CFD build123d Geometry Generation Examples ===")
    print(f"Output directory: {out_dir}\n")

    # 1. Modular Filter Assembly (Corkscrew)
    print("1. Generating Modular Filter Assembly (Corkscrew)...")
    drv_corkscrew = Build123dDriver("corkscrew.scad")
    params_corkscrew = {
        "tube_od_mm": 30.0,
        "tube_wall_mm": 2.0,
        "insert_length_mm": 60.0,
        "helix_path_radius_mm": 10.0,
        "helix_profile_radius_mm": 4.0,
        "helix_void_profile_radius_mm": 5.0,
        "number_of_complete_revolutions": 2.0,
        "num_bins": 2,
        "spacer_height_mm": 5.0
    }
    stl_cork = os.path.join(out_dir, "corkscrew_assembly.stl")
    step_cork = os.path.join(out_dir, "corkscrew_assembly.step")
    drv_corkscrew.generate_stl(params_corkscrew, stl_cork)
    drv_corkscrew.generate_step(params_corkscrew, step_cork)
    bounds = drv_corkscrew.get_bounds(stl_cork)
    print(f"   -> Saved: {stl_cork}")
    print(f"   -> Saved: {step_cork}")
    print(f"   -> Bounds (min, max): {bounds}\n")

    # 2. Dipole Antenna
    print("2. Generating Dipole Antenna...")
    drv_dipole = Build123dDriver("dipole_antenna.scad")
    params_dipole = {
        "length": 50.0,
        "thickness": 2.0,
        "gap": 2.0
    }
    stl_dipole = os.path.join(out_dir, "dipole_antenna.stl")
    step_dipole = os.path.join(out_dir, "dipole_antenna.step")
    drv_dipole.generate_stl(params_dipole, stl_dipole)
    drv_dipole.generate_step(params_dipole, step_dipole)
    bounds_dipole = drv_dipole.get_bounds(stl_dipole)
    print(f"   -> Saved: {stl_dipole}")
    print(f"   -> Saved: {step_dipole}")
    print(f"   -> Bounds (min, max): {bounds_dipole}\n")

    # 3. Puck Antenna Array
    print("3. Generating Ground-Level Puck Antenna...")
    drv_puck = Build123dDriver("puck_antenna.scad")
    params_puck = {
        "puck_radius": 40.0,
        "puck_height": 15.0,
        "panel_radius": 35.0,
        "panel_thickness": 2.0,
        "panel_height_above_puck": 8.0,
        "num_antennas": 4,
        "antenna_length": 25.0,
        "antenna_width": 3.0,
        "antenna_thickness": 1.0
    }
    stl_puck = os.path.join(out_dir, "puck_antenna.stl")
    step_puck = os.path.join(out_dir, "puck_antenna.step")
    drv_puck.generate_stl(params_puck, stl_puck)
    drv_puck.generate_step(params_puck, step_puck)
    bounds_puck = drv_puck.get_bounds(stl_puck)
    print(f"   -> Saved: {stl_puck}")
    print(f"   -> Saved: {step_puck}")
    print(f"   -> Bounds (min, max): {bounds_puck}\n")

    # 4. Cyclone Filter Manifold
    print("4. Generating Tangential Cyclone Filter Manifold...")
    drv_cyclone = Build123dDriver("cyclone_filter_manifold.scad")
    params_cyclone = {
        "cyclone_diameter": 100.0,
        "cylinder_height": 100.0,
        "cone_height": 150.0,
        "inlet_width": 25.0,
        "inlet_height": 50.0,
        "vortex_finder_diameter": 50.0,
        "vortex_finder_length": 75.0,
        "dust_outlet_diameter": 25.0,
        "wall_thickness": 2.0
    }
    stl_cyclone = os.path.join(out_dir, "cyclone_manifold.stl")
    step_cyclone = os.path.join(out_dir, "cyclone_manifold.step")
    drv_cyclone.generate_stl(params_cyclone, stl_cyclone)
    drv_cyclone.generate_step(params_cyclone, step_cyclone)
    bounds_cyclone = drv_cyclone.get_bounds(stl_cyclone)
    print(f"   -> Saved: {stl_cyclone}")
    print(f"   -> Saved: {step_cyclone}")
    print(f"   -> Bounds (min, max): {bounds_cyclone}\n")

    # 5. Microstrip Trace Optimizer
    print("5. Generating Microstrip Trace PCB Model...")
    drv_trace = Build123dDriver("trace_optimizer.scad")
    params_trace = {
        "substrate_thickness": 1.6,
        "substrate_width": 20.0,
        "substrate_length": 100.0,
        "copper_thickness": 0.035,
        "part": "all"
    }
    stl_trace = os.path.join(out_dir, "trace_optimizer.stl")
    step_trace = os.path.join(out_dir, "trace_optimizer.step")
    drv_trace.generate_stl(params_trace, stl_trace)
    drv_trace.generate_step(params_trace, step_trace)
    bounds_trace = drv_trace.get_bounds(stl_trace)
    print(f"   -> Saved: {stl_trace}")
    print(f"   -> Saved: {step_trace}")
    print(f"   -> Bounds (min, max): {bounds_trace}\n")

    print("=== All build123d model examples generated successfully! ===")

if __name__ == "__main__":
    main()
