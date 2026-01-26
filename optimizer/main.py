import os
import json
import argparse
import time
from scad_driver import ScadDriver
from foam_driver import FoamDriver
from llm_agent import LLMAgent

def main():
    parser = argparse.ArgumentParser(description="Generative AI Optimizer for Corkscrew Filter")
    parser.add_argument("--iterations", type=int, default=5, help="Number of optimization iterations")
    parser.add_argument("--scad-file", type=str, default="corkscrew filter.scad", help="Path to OpenSCAD file")
    parser.add_argument("--case-dir", type=str, default="corkscrewFilter", help="Path to OpenFOAM case directory")
    parser.add_argument("--output-stl", type=str, default="corkscrew_fluid.stl", help="Output STL filename")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual OpenFOAM execution")
    args = parser.parse_args()

    # Initialize components
    scad = ScadDriver(args.scad_file)
    foam = FoamDriver(args.case_dir)
    agent = LLMAgent() # Expects GEMINI_API_KEY env var

    # Initial parameters
    current_params = {
        "num_bins": 1,
        "number_of_complete_revolutions": 2,
        "screw_OD_mm": 1.8,
        "screw_ID_mm": 1.0,
        "scale_ratio": 1.4,
        "tube_od_mm": 32,
        "insert_length_mm": 50,
        "pitch_mm": 10
    }

    constraints = """
    - tube_od_mm must be 32 (hard constraint for fit).
    - insert_length_mm should be around 50.
    - screw_OD_mm > screw_ID_mm.
    - num_bins should be integer >= 1.
    """

    results_history = []

    print("Starting optimization loop...")

    for i in range(args.iterations):
        print(f"\n=== Iteration {i+1}/{args.iterations} ===")
        print(f"Testing parameters: {current_params}")

        # 1. Generate Geometry
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

        # 4. Save Results
        run_data = {
            "iteration": i,
            "parameters": current_params.copy(),
            "metrics": metrics
        }
        results_history.append(run_data)

        with open("optimization_history.json", "w") as f:
            json.dump(results_history, f, indent=2)

        # 5. Ask LLM for next step
        if i < args.iterations - 1:
            new_params = agent.suggest_parameters(current_params, metrics, constraints)
            if "num_bins" in new_params:
                new_params["num_bins"] = int(new_params["num_bins"])

            updated_params = current_params.copy()
            updated_params.update(new_params)
            current_params = updated_params

    print("\nOptimization complete.")

if __name__ == "__main__":
    main()
