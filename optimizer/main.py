import os
import json
import argparse
import time
import subprocess
import shutil
import hashlib
import sys
from scad_driver import ScadDriver
from foam_driver import FoamDriver
from llm_agent import LLMAgent
from data_store import DataStore
from simulation_runner import run_simulation
from constraints import CONSTRAINTS
try:
    from scoring import calculate_score
except ImportError:
    from optimizer.scoring import calculate_score

def get_params_hash(params):
    """Generates a stable hash for a parameter set to detect duplicates."""
    normalized = {}
    for k, v in params.items():
        if isinstance(v, float):
            normalized[k] = round(v, 4)
        else:
            normalized[k] = v
    s = json.dumps(normalized, sort_keys=True)
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Generative AI Optimizer for Corkscrew Filter")
    parser.add_argument("--iterations", type=str, default="5", help="Number of iterations (int), or 'inf'/'infinite'/-1 for infinite loop")
    parser.add_argument("--scad-file", type=str, default="corkscrew.scad", help="Path to OpenSCAD file")
    parser.add_argument("--case-dir", type=str, default="corkscrewFilter", help="Path to OpenFOAM case directory")
    parser.add_argument("--output-stl", type=str, default="corkscrew_fluid.stl", help="Output STL filename (for OpenFOAM usage)")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual OpenFOAM execution (mocks everything)")
    parser.add_argument("--skip-cfd", action="store_true", help="Generate geometry but skip CFD simulation")
    parser.add_argument("--reuse-mesh", action="store_true", help="Reuse existing mesh (skips geometry generation and meshing)")
    parser.add_argument("--container-engine", type=str, default="auto", choices=["auto", "podman", "docker"], help="Force specific container engine")
    parser.add_argument("--cpus", type=int, default=1, help="Number of CPUs to use for parallel execution (default: 1)")
    parser.add_argument("--no-llm", action="store_true", help="Explicitly disable LLM and use random/fallback strategy (also suppresses prompts in startup script)")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of parameter sets to generate per LLM call")
    parser.add_argument("--no-cleanup", action="store_true", help="Disable cleanup of artifacts (STLs, images) for non-top runs")
    args = parser.parse_args()

    # Parse iterations argument
    infinite_mode = False
    try:
        if args.iterations.lower() in ["inf", "infinite", "-1"]:
            infinite_mode = True
            max_iterations = float("inf")
        else:
            max_iterations = int(args.iterations)
            if max_iterations < 0:
                infinite_mode = True
                max_iterations = float("inf")
    except ValueError:
        print(f"Error: Invalid iterations value '{args.iterations}'. Using default 5.")
        max_iterations = 5

    # Initialize components
    scad = ScadDriver(args.scad_file)
    foam = FoamDriver(args.case_dir, container_engine=args.container_engine, num_processors=args.cpus)

    # Handle --no-llm logic: explicitly disable by unsetting env var
    if args.no_llm and "GEMINI_API_KEY" in os.environ:
        print("Explicitly disabling LLM due to --no-llm flag.")
        del os.environ["GEMINI_API_KEY"]

    agent = LLMAgent() # Expects GEMINI_API_KEY env var
    store = DataStore()

    # Create artifacts directory
    artifacts_dir = "artifacts"
    os.makedirs(artifacts_dir, exist_ok=True)
    # Ensure exports directory exists
    os.makedirs("exports", exist_ok=True)

    # Get git commit
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
        status = subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8").strip()
        if status:
            git_commit += " (dirty)"
    except Exception as e:
        print(f"Warning: Failed to retrieve git commit info: {e}")
        git_commit = "unknown"

    # Initial parameters
    initial_params = {
        "part_to_generate": "modular_filter_assembly",
        "num_bins": 1,
        "number_of_complete_revolutions": 2,
        "helix_path_radius_mm": 1.8,
        "helix_profile_radius_mm": 1.7,
        "helix_void_profile_radius_mm": 1.0,
        "helix_profile_scale_ratio": 1.4,
        "tube_od_mm": 32,
        "insert_length_mm": 50,
        "GENERATE_CFD_VOLUME": True
    }

    # Load History & Populate Visited Set
    print("Loading history from data store...")
    full_history = store.load_history()
    agent.history = full_history # Pre-load agent history

    visited_params = set()
    for run in full_history:
        if "parameters" in run:
            visited_params.add(get_params_hash(run["parameters"]))

    print(f"Loaded {len(full_history)} past runs. Found {len(visited_params)} unique parameter sets.")

    print(f"Starting optimization loop... (Target: {max_iterations} iterations, Infinite: {infinite_mode})")

    # Queue logic
    parameter_queue = []

    # If we have no history, start with default params
    # If we have history, we can start by asking LLM (queue empty) OR verifying default hasn't been run.
    # To keep it simple: Start with default params if they haven't been run.
    if get_params_hash(initial_params) not in visited_params:
        parameter_queue.append(initial_params)

    # Keep track of the last valid run's images to feed to LLM
    last_run_images = []

    i = 0
    while True:
        if not infinite_mode and i >= max_iterations:
            break

        print(f"\n=== Iteration {i+1} ===")

        # Refill Queue if empty
        if not parameter_queue:
            print(f"Parameter queue empty. Requesting {args.batch_size} new sets from LLM...")

            # Determine images to send (from last successful run in history if available)
            # 'last_run_images' tracks the current session, but if we just started, we might want from history?
            # For now, rely on session variable or empty.

            campaign_params = agent.suggest_campaign(
                history=full_history,
                constraints=CONSTRAINTS,
                count=args.batch_size,
                image_paths=last_run_images
            )

            # Check for stop signal (wrapped in list or dict?)
            # suggest_campaign returns a list of dicts. If one has stop_opt, handle it.
            if campaign_params and campaign_params[0].get("stop_optimization") is True:
                print("\n>>> OPTIMIZATION COMPLETE: LLM signaled stop (Success criteria met). <<<")
                break

            if campaign_params:
                print(f"LLM returned {len(campaign_params)} parameter sets.")
                parameter_queue.extend(campaign_params)
            else:
                print("LLM failed to return valid parameters. Falling back to random generation.")
                # Generate 1 random set to keep going
                base_params = full_history[-1]["parameters"] if full_history else initial_params
                random_params = agent._generate_random_parameters(base_params, CONSTRAINTS)
                parameter_queue.append(random_params)

        # Pop next parameters
        if not parameter_queue:
            print("Error: Parameter queue is empty after refill attempt. Aborting loop to prevent infinite error spin.")
            break

        current_params = parameter_queue.pop(0)

        # Deduplication Check
        param_hash = get_params_hash(current_params)
        if param_hash in visited_params:
            print(f"Skipping duplicate parameters (Hash: {param_hash}).")
            # If queue is empty, we'll hit refill next loop. If not, we just take next.
            continue

        print(f"Testing parameters: {current_params}")
        visited_params.add(param_hash)

        # Generate Run ID and Output Prefix
        # Use timestamp to ensure uniqueness
        run_timestamp = time.time()
        run_id_hash = hashlib.md5(f"{i}_{run_timestamp}".encode()).hexdigest()
        run_id_short = run_id_hash[:8]
        output_prefix = os.path.join("exports", f"run_{run_id_short}")

        # Run Simulation via Runner
        # output_stl is strictly 'corkscrew_fluid.stl' for OpenFOAM compatibility
        metrics, png_paths, solid_stl_path, fluid_stl_path = run_simulation(
            scad,
            foam,
            current_params,
            output_stl_name=args.output_stl,
            dry_run=args.dry_run,
            skip_cfd=args.skip_cfd,
            iteration=i,
            reuse_mesh=args.reuse_mesh,
            output_prefix=output_prefix
        )

        print(f"Result metrics: {metrics}")

        # Update images for next LLM call
        if png_paths:
            last_run_images = png_paths

        # Check for critical failure
        if "error" in metrics:
            if metrics["error"] == "environment_missing_tools":
                print("\nCRITICAL ERROR: OpenFOAM tools not found.")
                print("Switching to geometry-only mode (--skip-cfd) for remaining iterations.")
                args.skip_cfd = True
            elif metrics["error"] == "geometry_generation_failed":
                print("Geometry generation failed.")

        # Save Results
        run_data = {
            "id": run_id_hash, # Unique ID
            "status": "completed",
            "git_commit": git_commit,
            "agent_id": "optimizer-script",
            "iteration": i,
            "timestamp": run_timestamp,
            "parameters": current_params.copy(),
            "metrics": metrics,
            "images": png_paths,
            "solid_stl_path": solid_stl_path,
            "fluid_stl_path": fluid_stl_path,
            "artifact_stl_path": fluid_stl_path # Backward compatibility / Alias
        }
        store.append_result(run_data)

        # Reload history to include this run
        full_history.append(run_data)
        agent.history = full_history

        # Cleanup Artifacts (Keep Top 10)
        # We do this every run to save space
        if not args.no_cleanup:
            top_runs = store.get_top_runs(10)
            store.clean_artifacts(top_runs)
        else:
            print("Cleanup disabled (--no-cleanup). Keeping all artifacts.")

        i += 1

    print("\nOptimization loop finished.")

if __name__ == "__main__":
    main()
