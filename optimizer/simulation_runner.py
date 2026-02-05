import os
import time
from utils import Timer

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

    # 1. Generate Geometry (Fluid Volume for CFD)
    stl_path = os.path.join(foam_driver.case_dir, "constant", "triSurface", output_stl_name)
    os.makedirs(os.path.dirname(stl_path), exist_ok=True)

    if not dry_run:
        if not reuse_mesh:
            with Timer("Geometry Generation"):
                success = scad_driver.generate_stl(params, stl_path, log_file=geom_log)

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
                foam_driver.update_blockMesh(bounds)

                # Try to find an internal point
                internal_point = scad_driver.get_internal_point(stl_path)
                if internal_point:
                    foam_driver.update_snappyHexMesh_location(internal_point)
                else:
                    print("Warning: Could not find internal point. Falling back to bounds-based location.")
                    foam_driver.update_snappyHexMesh_location(bounds)
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
