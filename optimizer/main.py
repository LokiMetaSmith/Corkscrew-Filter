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
    current_params = {
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

    i = 0
    while True:
        if not infinite_mode and i >= max_iterations:
            break

        print(f"\n=== Iteration {i+1} ===")

        # Deduplication Check
        # If this is the very first run (i=0) and we haven't mutated, current_params is the default.
        # If the default was already run in history, we should skip it and ask LLM.
        # However, agent.suggest_parameters needs metrics to suggest something.
        # If we have NO history, we run defaults.
        # If we have history, we might want to start by asking the LLM immediately if defaults are visited.

        param_hash = get_params_hash(current_params)
        if param_hash in visited_params:
            print(f"Parameters already visited (Hash: {param_hash}). Requesting new parameters from LLM...")

            # We need dummy metrics or use the last run's metrics to ask for next step?
            # Or just tell LLM "Propose something new".
            # The agent uses 'history' to decide.

            # Fallback: if we are stuck on duplicates, use random search
            if agent.history:
                last_run = agent.history[-1]
                metrics_context = last_run.get("metrics", {})
            else:
                metrics_context = {"error": "duplicate_start"} # Should not happen if history loaded

            # Ask LLM (or Random)
            # We force it to suggest new params
            new_params_or_meta = agent.suggest_parameters(current_params, metrics_context, CONSTRAINTS, history=full_history)

            # Unpack response
            stop_opt = False
            if "stop_optimization" in new_params_or_meta:
                 stop_opt = new_params_or_meta.pop("stop_optimization")

            if stop_opt:
                print("LLM signaled to STOP optimization during deduplication.")
                break

            # Update params
            updated = current_params.copy()
            updated.update(new_params_or_meta)
            current_params = updated

            # Check again (simple 1-level retry loop or continue)
            if get_params_hash(current_params) in visited_params:
                print("LLM suggested duplicate again. Forcing random mutation.")
                current_params = agent._generate_random_parameters(current_params, CONSTRAINTS)

            # Continue to next loop iteration to verify/run
            continue

        print(f"Testing parameters: {current_params}")
        visited_params.add(param_hash)

        # Run Simulation via Runner
        # output_stl is strictly 'corkscrew_fluid.stl' for OpenFOAM compatibility
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
                args.skip_cfd = True
                # Don't skip loop, just continue with next params?
                # Actually, if we skip CFD, metrics will be empty/skipped.
            elif metrics["error"] == "geometry_generation_failed":
                print("Geometry generation failed.")
                # We still record the failure so LLM knows it failed

        # Handle Artifact Archiving (STL)
        # We need to save the STL to a unique path so we can keep it if it's a top run.
        unique_stl_path = None
        source_stl = os.path.join(args.case_dir, "constant", "triSurface", args.output_stl)
        if os.path.exists(source_stl):
            run_id_short = hashlib.md5(f"{i}_{time.time()}".encode()).hexdigest()[:8]
            unique_name = f"corkscrew_{run_id_short}.stl"
            unique_stl_path = os.path.join(artifacts_dir, unique_name)
            try:
                shutil.copy(source_stl, unique_stl_path)
            except Exception as e:
                print(f"Warning: Failed to archive STL: {e}")
                unique_stl_path = None

        # 5. Save Results
        run_data = {
            "id": hashlib.md5(f"{i}_{time.time()}".encode()).hexdigest(), # Unique ID
            "status": "completed",
            "git_commit": git_commit,
            "agent_id": "optimizer-script",
            "iteration": i,
            "timestamp": time.time(),
            "parameters": current_params.copy(),
            "metrics": metrics,
            "images": png_paths,
            "artifact_stl_path": unique_stl_path
        }
        store.append_result(run_data)

        # Reload history to include this run (or just append locally)
        full_history.append(run_data)
        agent.history = full_history

        # 6. Cleanup Artifacts (Keep Top 10)
        top_runs = store.get_top_runs(10)
        store.clean_artifacts(top_runs)

        # 7. Ask LLM for next step or Stop
        # We check stop condition from LLM

        new_params_or_meta = agent.suggest_parameters(current_params, metrics, CONSTRAINTS, image_paths=png_paths, history=full_history)

        stop_opt = False
        if "stop_optimization" in new_params_or_meta:
             stop_opt = new_params_or_meta.pop("stop_optimization")
             # Clean key from dict so it doesn't pollute params

        if stop_opt:
            print("\n>>> OPTIMIZATION COMPLETE: LLM signaled stop (Success criteria met). <<<")
            break

        # Post-process types
        if "num_bins" in new_params_or_meta:
            new_params_or_meta["num_bins"] = int(new_params_or_meta["num_bins"])

        updated_params = current_params.copy()
        updated_params.update(new_params_or_meta)
        current_params = updated_params

        i += 1

    print("\nOptimization loop finished.")

if __name__ == "__main__":
    main()
