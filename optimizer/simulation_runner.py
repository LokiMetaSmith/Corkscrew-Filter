import os
import time

def run_simulation(scad_driver, foam_driver, params, output_stl_name="corkscrew_fluid.stl", dry_run=False):
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

    Returns:
        tuple: (metrics, image_paths)
            metrics (dict): Simulation results (delta_p, residuals, etc).
            image_paths (list): List of paths to generated PNG visualizations.
    """

    # 1. Generate Geometry (Fluid Volume for CFD)
    stl_path = os.path.join(foam_driver.case_dir, "constant", "triSurface", output_stl_name)
    os.makedirs(os.path.dirname(stl_path), exist_ok=True)

    if not dry_run:
        success = scad_driver.generate_stl(params, stl_path)
        if not success:
            print("Geometry generation failed.")
            return {"error": "geometry_generation_failed"}, []
    else:
        print(f"[Dry Run] Generated STL at {stl_path}")
        if not os.path.exists(stl_path):
            with open(stl_path, 'w') as f: f.write("solid dryrun\nendsolid dryrun")

    # 2. Update Mesh Config
    if not dry_run:
        bounds = scad_driver.get_bounds(stl_path)
        if bounds[0] is None:
            print("Failed to get bounds. Using default.")
        else:
            foam_driver.update_blockMesh(bounds)
    else:
         print("[Dry Run] Updated blockMeshDict")

    # 3. Run Simulation
    metrics = {}
    if not dry_run:
        foam_driver.prepare_case()
        if foam_driver.run_meshing():
            if foam_driver.run_solver():
                # Attempt particle tracking (optional/experimental)
                foam_driver.run_particle_tracking()

                metrics = foam_driver.get_metrics()
            else:
                print("Solver failed.")
                metrics = {"error": "solver_failed"}
        else:
            print("Meshing failed.")
            metrics = {"error": "meshing_failed"}
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
        print("Generating visualization...")
        # Use lower resolution for vis to speed up
        vis_params = params.copy()
        vis_params["high_res_fn"] = 20 # Low res enough for shape check
        png_paths = scad_driver.generate_visualization(vis_params, vis_base)
    else:
        print(f"[Dry Run] Generated Visualization at {vis_base}.png")
        # Create dummy path for dry run consistency
        # png_paths = [f"{vis_base}_view{v}.png" for v in range(3)]
        png_paths = []

    return metrics, png_paths
