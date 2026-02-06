import os
import json
import argparse
import time
import subprocess
from scad_driver import ScadDriver
from foam_driver import FoamDriver
from llm_agent import LLMAgent
from data_store import DataStore
from simulation_runner import run_simulation
from constraints import CONSTRAINTS

def main():
    parser = argparse.ArgumentParser(description="Generative AI Optimizer for Corkscrew Filter")
    parser.add_argument("--iterations", type=int, default=5, help="Number of optimization iterations")
    parser.add_argument("--scad-file", type=str, default="corkscrew.scad", help="Path to OpenSCAD file")
    parser.add_argument("--case-dir", type=str, default="corkscrewFilter", help="Path to OpenFOAM case directory")
    parser.add_argument("--output-stl", type=str, default="corkscrew_fluid.stl", help="Output STL filename")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual OpenFOAM execution (mocks everything)")
    parser.add_argument("--skip-cfd", action="store_true", help="Generate geometry but skip CFD simulation")
    parser.add_argument("--reuse-mesh", action="store_true", help="Reuse existing mesh (skips geometry generation and meshing)")
    parser.add_argument("--container-engine", type=str, default="auto", choices=["auto", "podman", "docker"], help="Force specific container engine")
    args = parser.parse_args()

    # Initialize components
    scad = ScadDriver(args.scad_file)
    foam = FoamDriver(args.case_dir, container_engine=args.container_engine)
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
        "helix_profile_radius_mm": 2.5,
        "helix_void_profile_radius_mm": 1.0,
        "helix_profile_scale_ratio": 1.4,
        "tube_od_mm": 32,
        "insert_length_mm": 50,
        "GENERATE_CFD_VOLUME": True
    }

    # Constraints for the LLM
    # Imported from constraints.py

    print("Starting optimization loop...")

    for i in range(args.iterations):
        print(f"\n=== Iteration {i+1}/{args.iterations} ===")
        print(f"Testing parameters: {current_params}")

        # Run Simulation via Runner
        metrics, png_paths = run_simulation(
            scad,
            foam,
            current_params,
            output_stl_name=args.output_stl,
            dry_run=args.dry_run,
            skip_cfd=args.skip_cfd,
            iteration=i,
            reuse_mesh=args.reuse_mesh
        )

        print(f"Result metrics: {metrics}")

        # Check for critical failure
        if "error" in metrics:
            if metrics["error"] == "environment_missing_tools":
                print("\nCRITICAL ERROR: OpenFOAM tools not found.")
                print("Switching to geometry-only mode (--skip-cfd) for remaining iterations.")
                print("Please fix your OpenFOAM/Container environment to resume CFD simulations.")
                args.skip_cfd = True
                continue
            elif metrics["error"] == "geometry_generation_failed":
                print("Skipping this iteration due to geometry failure.")
                continue

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
            new_params = agent.suggest_parameters(current_params, metrics, CONSTRAINTS, image_paths=png_paths, history=full_history)
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
