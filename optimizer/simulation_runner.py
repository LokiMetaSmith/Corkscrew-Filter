import os
import time
import math
import numpy as np
from utils import Timer
from parameter_validator import validate_parameters

def run_simulation(scad_driver, foam_driver, params, output_stl_name="corkscrew_fluid.stl", dry_run=False, skip_cfd=False, iteration=0, reuse_mesh=False):
    """
    Executes the full simulation pipeline:
    1. Generate Fluid Geometry (STL)
    2. Update OpenFOAM BlockMesh
    3. Run OpenFOAM Simulation
    4. Extract Metrics
    5. Generate Visualization Images (Solid Model)

    Args:
        scad_driver (ScadDriver): Initialized ScadDriver instance.
        foam_driver (FoamDriver): Initialized FoamDriver instance.
        params (dict): Dictionary of parameters for the run.
        output_stl_name (str): Filename for the fluid STL (inside case/constant/triSurface).
        dry_run (bool): If True, skips actual processing and returns mock data.
        skip_cfd (bool): If True, generates geometry but skips CFD simulation.
        iteration (int): The current iteration number (used for logging).
        reuse_mesh (bool): If True, skips geometry generation and meshing, using existing mesh.

    Returns:
        tuple: (metrics, image_paths)
            metrics (dict): Simulation results (delta_p, residuals, etc).
            image_paths (list): List of paths to generated PNG visualizations.
    """

    # Setup Log Directory
    log_dir = os.path.join("logs", f"iteration_{iteration}")
    os.makedirs(log_dir, exist_ok=True)

    # Log files
    geom_log = os.path.join(log_dir, "geometry.log")
    mesh_log = os.path.join(log_dir, "meshing.log")
    solver_log = os.path.join(log_dir, "solver.log")
    vis_log = os.path.join(log_dir, "visualization.log")

    # 0. Validate Parameters
    is_valid, error_msg = validate_parameters(params)
    if not is_valid:
        print(f"Parameter Validation Failed: {error_msg}")
        return {"error": "invalid_parameters", "details": error_msg}, []

    # 1. Generate Geometry (Fluid Volume for CFD)
    stl_path = os.path.join(foam_driver.case_dir, "constant", "triSurface", output_stl_name)
    os.makedirs(os.path.dirname(stl_path), exist_ok=True)

    if not dry_run:
        if not reuse_mesh:
            with Timer("Geometry Generation"):
                success = scad_driver.generate_stl(params, stl_path, log_file=geom_log)

                # Scale STL to meters immediately after generation
                if success:
                    SCALE_FACTOR = 0.001
                    print(f"Scaling mesh by factor {SCALE_FACTOR} (mm -> m)...")
                    if not scad_driver.scale_mesh(stl_path, SCALE_FACTOR):
                        print("Failed to scale mesh. Aborting.")
                        success = False

            if not success:
                print(f"Geometry generation failed. Check {geom_log} for details.")
                return {"error": "geometry_generation_failed"}, []
        else:
            print("[Reuse Mesh] Skipping geometry generation.")
    else:
        print(f"[Dry Run] Generated STL at {stl_path}")
        if not os.path.exists(stl_path):
            with open(stl_path, 'w') as f: f.write("solid dryrun\nendsolid dryrun")

    # 2. Update Mesh Config
    if not dry_run and not skip_cfd:
        # Early check for environment
        if not foam_driver.has_tools:
            print("OpenFOAM tools not found. Skipping simulation.")
            return {"error": "environment_missing_tools", "details": "Neither OpenFOAM nor Docker found"}, []

        if not reuse_mesh:
            bounds = scad_driver.get_bounds(stl_path)
            if bounds[0] is None:
                print("Failed to get bounds. Using default.")
            else:
                SCALE_FACTOR = 0.001 # mm to meters
                # Calculate dynamic target cell size based on smallest feature
                target_cell_size = 1.5 * SCALE_FACTOR # Default scaled
                void_r = params.get("helix_void_profile_radius_mm")
                if void_r:
                    try:
                        # Ensure resolution is sufficient for small channels (at least ~2.5 cells radius)
                        # We use 0.3 * radius to be safe (diameter / 6), clamped between 0.2mm and 0.8mm
                        # This ensures small inlet patches are captured by snappyHexMesh
                        calculated_size_mm = float(void_r) * 0.3
                        target_cell_size_mm = max(0.2, min(0.8, calculated_size_mm))
                        target_cell_size = target_cell_size_mm * SCALE_FACTOR
                    except (ValueError, TypeError):
                        pass

                # Estimate cell count to prevent OOM
                BLOCK_MARGIN = np.array([1.2, 1.2, 0.95])
                # Ensure bounds are numpy arrays for subtraction
                bounds_arr = [np.array(b) for b in bounds]
                size = bounds_arr[1] - bounds_arr[0]

                block_size = size * BLOCK_MARGIN
                block_volume = np.prod(block_size)

                estimated_cells = block_volume / (target_cell_size ** 3)

                MAX_CELLS = 250_000
                if estimated_cells > MAX_CELLS:
                    new_size = (block_volume / MAX_CELLS) ** (1/3)
                    print(f"Warning: Estimated cell count {estimated_cells:.0f} exceeds {MAX_CELLS} limit. Increasing target_cell_size from {target_cell_size:.5f}m to {new_size:.5f}m to prevent OOM.")
                    target_cell_size = new_size

                print(f"Updating blockMesh with target_cell_size={target_cell_size:.3f}m")
                foam_driver.update_blockMesh(bounds, margin=tuple(BLOCK_MARGIN), target_cell_size=target_cell_size)

                # 1. Try to find an internal point using robust ray tracing (trimesh)
                # The bounds and mesh are already scaled to meters, so this returns meters.
                custom_location = scad_driver.get_internal_point(stl_path)

                if custom_location:
                    print(f"Using ray-traced internal point: {custom_location}")
                else:
                    print("Warning: Could not find internal point using ray tracing. Attempting fallback calculation.")

                    # 2. Fallback to analytic calculation
                    part = params.get("part_to_generate", "modular_filter_assembly")
                    if part == "modular_filter_assembly":
                        try:
                            L = float(params.get("insert_length_mm", 50))
                            revs = float(params.get("number_of_complete_revolutions", 2))
                            path_r = float(params.get("helix_path_radius_mm", 1.8))

                            # Calculate twist angle at Z=0 (center)
                            # The helix rotates by total_twist over height H.
                            # Total height of helix is L + 2 (from MasterHollowHelix logic).
                            # Twist rate = 360 * revs / L.
                            # Total twist = twist_rate * (L + 2).
                            # At center (Z=0), rotation is total_twist / 2 (assuming linear_extrude center=true).

                            twist_rate = 360.0 * revs / L
                            total_twist = twist_rate * (L + 2.0)
                            angle_at_center_deg = total_twist / 2.0

                            theta_rad = math.radians(angle_at_center_deg)

                            # Calculate position
                            x = path_r * math.cos(theta_rad)
                            y = path_r * math.sin(theta_rad)
                            z = 0.0
                            # Scale fallback calculation to meters
                            custom_location = (x * SCALE_FACTOR, y * SCALE_FACTOR, z * SCALE_FACTOR)
                            print(f"Calculated custom seed location for channel: {custom_location}")
                        except Exception as e:
                            print(f"Warning: Failed to calculate custom location: {e}")

                # Update location (if custom_location is None, foam_driver defaults to bounds-based legacy logic)
                foam_driver.update_snappyHexMesh_location(bounds, custom_location=custom_location)
        else:
            print("[Reuse Mesh] Skipping BlockMesh update.")
    elif skip_cfd:
        print("[Skip CFD] Skipping BlockMesh update.")
    else:
         print("[Dry Run] Updated blockMeshDict")

    # 3. Run Simulation
    metrics = {}
    if not dry_run and not skip_cfd:
        foam_driver.prepare_case(keep_mesh=reuse_mesh)

        if not reuse_mesh:
            with Timer("Meshing"):
                success = foam_driver.run_meshing(log_file=mesh_log)
        else:
            print("[Reuse Mesh] Skipping meshing pipeline.")
            success = True

        if success:
            with Timer("Solver"):
                success = foam_driver.run_solver(log_file=solver_log)

            if success:
                # Attempt particle tracking (optional/experimental)
                with Timer("Particle Tracking"):
                    foam_driver.run_particle_tracking(log_file=solver_log)

                metrics = foam_driver.get_metrics(log_file=solver_log)
            else:
                print(f"Solver failed. Check {solver_log}")
                metrics = {"error": "solver_failed"}
        else:
            print(f"Meshing failed. Check {mesh_log}")
            metrics = {"error": "meshing_failed"}
    elif skip_cfd:
        print("[Skip CFD] Skipping CFD simulation.")
        metrics = {"skipped": True, "note": "CFD simulation skipped by user request"}
    else:
        print("[Dry Run] Ran OpenFOAM simulation")
        # Mock metrics for dry run
        import random
        metrics = {
            "delta_p": 100 + random.randint(0, 50),
            "residuals": 1e-5
        }

    # 4. Generate Visualization (Solid Model for LLM/Human Review)
    png_paths = []
    # Create an exports directory relative to current working directory
    # We use a timestamp or iteration-based name?
    # For a worker, we might not know the "iteration number" easily if we just process a job ID.
    # Let's use a temp folder or the job ID if passed?
    # For now, let's just use "exports/latest" or similar, but the caller might want to move it.
    # Actually, main.py uses "iteration_{i}_solid".
    # Let's make the output base a parameter or derive it.

    # We'll default to a timestamped folder in exports/ to avoid overwrites
    timestamp = int(time.time())
    vis_base = os.path.join("exports", f"run_{timestamp}_solid")
    os.makedirs("exports", exist_ok=True)

    if not dry_run:
        # Use lower resolution for vis to speed up
        vis_params = params.copy()
        vis_params["high_res_fn"] = 20 # Low res enough for shape check

        with Timer("Visualization"):
            png_paths = scad_driver.generate_visualization(vis_params, vis_base, log_file=vis_log)

    else:
        print(f"[Dry Run] Generated Visualization at {vis_base}.png")
        # Create dummy path for dry run consistency
        # png_paths = [f"{vis_base}_view{v}.png" for v in range(3)]
        png_paths = []

    return metrics, png_paths
