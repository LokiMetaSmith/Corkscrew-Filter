import os
import json
import argparse
import time
import subprocess
from scad_driver import ScadDriver
from foam_driver import FoamDriver
from llm_agent import LLMAgent
from data_store import DataStore

def main():
    parser = argparse.ArgumentParser(description="Generative AI Optimizer for Corkscrew Filter")
    parser.add_argument("--iterations", type=int, default=5, help="Number of optimization iterations")
    parser.add_argument("--scad-file", type=str, default="corkscrew.scad", help="Path to OpenSCAD file")
    parser.add_argument("--case-dir", type=str, default="corkscrewFilter", help="Path to OpenFOAM case directory")
    parser.add_argument("--output-stl", type=str, default="corkscrew_fluid.stl", help="Output STL filename")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual OpenFOAM execution")
    args = parser.parse_args()

    # Initialize components
    scad = ScadDriver(args.scad_file)
    foam = FoamDriver(args.case_dir)
    agent = LLMAgent() # Expects GEMINI_API_KEY env var
    store = DataStore()

    # Get git commit
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
        # Check for uncommitted changes
        status = subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8").strip()
        if status:
            git_commit += " (dirty)"
            print("Warning: Uncommitted changes detected. Git commit marked as dirty.")
    except Exception as e:
        print(f"Warning: Failed to retrieve git commit info: {e}")
        git_commit = "unknown"

    # Initial parameters
    # Note: These match the variable names in config.scad
    current_params = {
        "part_to_generate": "modular_filter_assembly",
        "num_bins": 1,
        "number_of_complete_revolutions": 2,
        "helix_path_radius_mm": 1.8,
        "helix_void_profile_radius_mm": 1.0,
        "helix_profile_scale_ratio": 1.4,
        "tube_od_mm": 32,
        "insert_length_mm": 50,
        "GENERATE_CFD_VOLUME": True
    }

    # Constraints for the LLM
    constraints = """
    - tube_od_mm must be 32 (hard constraint for fit).
    - insert_length_mm should be around 50.
    - helix_path_radius_mm > helix_void_profile_radius_mm (to ensure structural integrity if solid, but for fluid volume this defines the channel).
    - num_bins should be integer >= 1.
    - Optimization Goal: Maximize particle collection efficiency (trap moon dust) while minimizing pressure drop.
    - Consider increasing number_of_complete_revolutions to increase centrifugal force.
    """

    print("Starting optimization loop...")

    for i in range(args.iterations):
        print(f"\n=== Iteration {i+1}/{args.iterations} ===")
        print(f"Testing parameters: {current_params}")

        # 1. Generate Geometry (Fluid Volume for CFD)
        stl_path = os.path.join(args.case_dir, "constant", "triSurface", args.output_stl)
        os.makedirs(os.path.dirname(stl_path), exist_ok=True)

        if not args.dry_run:
            success = scad.generate_stl(current_params, stl_path)
            if not success:
                print("Geometry generation failed. Skipping this iteration.")
                continue
        else:
            print(f"[Dry Run] Generated STL at {stl_path}")
            if not os.path.exists(stl_path):
                with open(stl_path, 'w') as f: f.write("solid dryrun\nendsolid dryrun")

        # 2. Update Mesh Config
        if not args.dry_run:
            bounds = scad.get_bounds(stl_path)
            if bounds[0] is None:
                print("Failed to get bounds. Using default.")
            else:
                foam.update_blockMesh(bounds)
        else:
             print("[Dry Run] Updated blockMeshDict")

        # 3. Run Simulation
        metrics = {}
        if not args.dry_run:
            foam.prepare_case()
            if foam.run_meshing():
                if foam.run_solver():
                    # Attempt particle tracking
                    foam.run_particle_tracking()

                    metrics = foam.get_metrics()
                else:
                    print("Solver failed.")
                    metrics = {"error": "solver_failed"}
            else:
                print("Meshing failed.")
                metrics = {"error": "meshing_failed"}
        else:
            print("[Dry Run] Ran OpenFOAM simulation")
            metrics = {"delta_p": 100 + i*10, "residuals": 1e-5} # Mock data

        print(f"Result metrics: {metrics}")

        # 4. Generate Visualization (Solid Model for LLM)
        png_paths = []
        vis_base = os.path.join("exports", f"iteration_{i}_solid")
        os.makedirs("exports", exist_ok=True)

        if not args.dry_run:
            print("Generating visualization for LLM...")
            # Use lower resolution for vis to speed up
            vis_params = current_params.copy()
            vis_params["high_res_fn"] = 20 # Low res enough for shape check
            png_paths = scad.generate_visualization(vis_params, vis_base)
        else:
            print(f"[Dry Run] Generated Visualization at {vis_base}.png")
            # Create dummy files for dry run
            for v in range(3):
                p = f"{vis_base}_view{v}.png"
                # Create a 1x1 white pixel png or just empty file (Pillow might fail on empty file)
                # Let's not create files if we can't create valid PNGs easily without PIL here.
                # Actually we can skip image loading in dry run or just pass empty list
                pass

        # 5. Save Results
        run_data = {
            "status": "completed",
            "git_commit": git_commit,
            "agent_id": "optimizer-script",
            "iteration": i,
            "parameters": current_params.copy(),
            "metrics": metrics,
            "images": png_paths
        }
        store.append_result(run_data)

        # 6. Ask LLM for next step
        if i < args.iterations - 1:
            full_history = store.load_history()
            new_params = agent.suggest_parameters(current_params, metrics, constraints, image_paths=png_paths, history=full_history)
            # Post-process types
            if "num_bins" in new_params:
                new_params["num_bins"] = int(new_params["num_bins"])
            if "GENERATE_CFD_VOLUME" in new_params:
                 # Ensure boolean stays boolean if LLM returns it
                 pass

            updated_params = current_params.copy()
            updated_params.update(new_params)
            current_params = updated_params

    print("\nOptimization complete.")

if __name__ == "__main__":
    main()
