import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# I will replace the current run_solver and _execute_simpleFoam with the main branch's versions,
# then modify them to incorporate the `adapted_turbulence` and `_sanitize_fields` from my adaptive numerics work.
# This gives the best of both worlds: robust execution + scoring from main AND mesh-aware schemes from this PR.

pattern_exec = re.compile(r"    def _execute_simpleFoam\(self, solve_procs=1, solve_method='scotch', log_file=None\):.*?        return False\n\n", re.DOTALL)
pattern_run = re.compile(r"    def run_solver\(self, log_file=None, mesh_scaled_for_memory=False, \*\*kwargs\):.*?        return False\n\n", re.DOTALL)

# Main branch versions of these functions
main_exec_funcs = """
    def _execute_simpleFoam(self, return_output=False, log_file=None, solve_procs=1, solve_method="scotch"):
        \"\"\"Executes simpleFoam and optionally returns standard output.\"\"\"
        output = ""
        success = False
        target_log = log_file if log_file else self.log_file

        import glob
        import shutil

        if solve_procs > 1:
            self._generate_decomposeParDict(num_processors=solve_procs, method=solve_method)
            if not self.run_command(["decomposePar", "-force"], log_file=target_log, description="Decomposing Domain"):
                return (False, "") if return_output else False

            cmd = ["mpirun", "--allow-run-as-root", "--oversubscribe", "-np", str(solve_procs), "simpleFoam", "-parallel"]
            success, cmd_out = self.run_command(cmd, log_file=target_log, description=f"Solving CFD (Parallel {solve_procs} CPUs)", timeout=14400, capture_output=True)
            output = cmd_out

            if success:
                if not self.run_command(["reconstructPar", "-latestTime"], log_file=target_log, description="Reconstructing Domain"):
                    return (False, "") if return_output else False

            for proc_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
                shutil.rmtree(proc_dir, ignore_errors=True)
        else:
            success, cmd_out = self.run_command(["simpleFoam"], log_file=target_log, description="Solving CFD", timeout=14400, capture_output=True)
            output = cmd_out

        failure_signals = [
            "floating point exception",
            "segmentation fault",
            "nan",
            "diverging",
            "foam fatal error",
            "foam aborting"
        ]

        if not success:
            pass

        out = output.lower()
        if any(sig in out for sig in failure_signals):
            success = False

        if "end" in out:
            success = True

        if return_output:
            if not output and os.path.exists(target_log):
                with open(target_log, 'r', encoding='utf-8', errors='replace') as f:
                    output = f.read()

        return (success, output) if return_output else success

    def _parse_solver_metrics(self, log):
        import re

        metrics = {
            "final_residuals": {},
            "continuity_error": None,
            "has_nan": False,
            "iterations": 0,
        }

        if not log:
            return metrics

        log_lower = log.lower()

        # Detect NaNs / divergence
        if "nan" in log_lower or "floating point exception" in log_lower or "sigfpe" in log_lower:
            metrics["has_nan"] = True

        # Extract residuals (last occurrence)
        residual_pattern = re.findall(
            r"Solving for (\\w+), Initial residual = ([\\deE\\+\\-\\.]+), Final residual = ([\\deE\\+\\-\\.]+)",
            log
        )

        for field, _, final in residual_pattern:
            metrics["final_residuals"][field] = float(final)

        # Continuity error
        cont_match = re.findall(
            r"time step continuity errors : sum local = ([\\deE\\+\\-\\.]+)",
            log
        )
        if cont_match:
            metrics["continuity_error"] = float(cont_match[-1])

        # Iteration count
        metrics["iterations"] = log.count("Time =")

        return metrics

    def _score_run(self, metrics):
        score = 100.0

        # Hard failure penalties
        if metrics["has_nan"]:
            return 0

        # --- Residual scoring ---
        for field, res in metrics["final_residuals"].items():
            if res > 1e-2:
                score -= 30
            elif res > 1e-3:
                score -= 15
            elif res > 1e-4:
                score -= 5

        # --- Continuity error ---
        ce = metrics["continuity_error"]
        if ce is not None:
            if ce > 1e-2:
                score -= 25
            elif ce > 1e-3:
                score -= 10

        # --- Iteration sanity ---
        if metrics["iterations"] < 10:
            score -= 20  # likely premature failure

        return max(score, 0)
"""

main_run_solver = """
    def run_solver(self, log_file=None, mesh_scaled_for_memory=False, **kwargs):
        \"\"\"
        Runs the solver using a strategy ladder with progressive degradation and scoring.
        \"\"\"
        cfd_settings = self.config.get('cfd_settings', {})
        solve_procs = cfd_settings.get('solve_processors', self.num_processors)
        solve_method = cfd_settings.get('solve_decompose_method', 'scotch')

        if mesh_scaled_for_memory:
            self._apply_fallback_wall_functions()

        import os
        import glob
        import shutil
        import re

        # Clean up any crashed or old time directories to ensure a fresh start from 0 for the new mesh
        for d in os.listdir(self.case_dir):
            path = os.path.join(self.case_dir, d)
            try:
                if d != "0" and os.path.isdir(path):
                    float(d)  # Check if it's a numeric time directory
                    shutil.rmtree(path, ignore_errors=True)
            except ValueError:
                pass

        # Also clean up processor time directories if running in parallel
        for p_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
            shutil.rmtree(p_dir, ignore_errors=True)

        results = []

        STRATEGIES = [
            {
                "name": "RNGkEpsilon",
                "turbulence": "RNGkEpsilon",
                "relaxation": {"p": 0.2, "U": 0.5, "k": 0.5, "epsilon": 0.5},
            },
            {
                "name": "kOmegaSST",
                "turbulence": "kOmegaSST",
                "relaxation": {"p": 0.15, "U": 0.4, "k": 0.4, "omega": 0.4},
            },
            {
                "name": "laminar",
                "turbulence": "laminar",
                "relaxation": {"p": 0.1, "U": 0.3},
            },
        ]

        # Use the requested turbulence model first if provided
        configured_model = cfd_settings.get('turbulence_model', "RNGkEpsilon")

        # Reorder strategies so the configured one is tried first
        configured_idx = next((i for i, s in enumerate(STRATEGIES) if s["turbulence"] == configured_model), 0)
        if configured_idx != 0:
             STRATEGIES.insert(0, STRATEGIES.pop(configured_idx))

        best = None
        for strategy in STRATEGIES:
            print(f"\\n🚀 Trying solver strategy: {strategy['name']}")

            # 1. Configure turbulence model
            self._update_turbulence_properties(strategy["turbulence"])

            # 2. Adaptive fvSchemes (mesh-aware)
            adapted_turbulence = self._update_fvSchemes(strategy["turbulence"])

            # 3. fvSolution (relaxation tuning)
            self._update_fvSolution(
                adapted_turbulence,
                cfd_settings,
                relaxation_override=strategy["relaxation"]
            )

            # 4. Ensure fields are sane
            self._sanitize_fields(adapted_turbulence)

            # Clean up any crashed time directories to ensure a fresh start from 0
            for d in os.listdir(self.case_dir):
                path = os.path.join(self.case_dir, d)
                try:
                    if d != "0" and os.path.isdir(path):
                        float(d)  # Check if it's a numeric time directory
                        shutil.rmtree(path, ignore_errors=True)
                except ValueError:
                    pass

            # Also clean up processor time directories if running in parallel
            for p_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
                for d in os.listdir(p_dir):
                    path = os.path.join(p_dir, d)
                    try:
                        if d != "0" and os.path.isdir(path):
                            float(d)
                            shutil.rmtree(path, ignore_errors=True)
                    except ValueError:
                        pass

            success, output = self._execute_simpleFoam(return_output=True, log_file=log_file, solve_procs=solve_procs, solve_method=solve_method)

            metrics = self._parse_solver_metrics(output)
            score = self._score_run(metrics)

            if strategy["turbulence"] == "laminar":
                score *= 0.85 # Penalize laminar

            # Extract run time from log if possible for time-to-solution weighting
            if output:
                runtime_match = re.search(r"ExecutionTime = ([\\deE\\+\\-\\.]+) s", output)
                if runtime_match:
                    runtime_seconds = float(runtime_match.group(1))
                    score -= runtime_seconds * 0.01

            results.append({
                "strategy": strategy["name"],
                "score": score,
                "metrics": metrics,
                "success": success
            })

            print(f"Strategy {strategy['name']} completed with score={score:.1f} (success={success})")

            if success and score > 80:
                print("✅ High quality run found, exiting early.")
                break

        if results:
            best = max(results, key=lambda r: r["score"])
            print(f"🏆 Best run: {best['strategy']} (score={best['score']:.1f})")

            import json
            with open(os.path.join(self.case_dir, "run_results.json"), "w") as f:
                json.dump(results, f, indent=2)

            return best["success"]
        return False
"""

# Apply the patches
content = pattern_exec.sub("", content, count=1)
content = pattern_run.sub("", content, count=1)

content += main_exec_funcs + main_run_solver

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
