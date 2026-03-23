import re

with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

# Replace run_solver method entirely
pattern = re.compile(r"    def run_solver\(self, log_file=None, mesh_scaled_for_memory=False, \*\*kwargs\):.*?(?=    def _create_constant_field)", re.DOTALL)

new_run_solver = """    def run_solver(self, log_file=None, mesh_scaled_for_memory=False, **kwargs):
        \"\"\"
        Runs the solver using a strategy ladder with progressive degradation.
        \"\"\"
        cfd_settings = self.config.get('cfd_settings', {})
        solve_procs = cfd_settings.get('solve_processors', self.num_processors)
        solve_method = cfd_settings.get('solve_decompose_method', 'scotch')

        if mesh_scaled_for_memory:
            self._apply_fallback_wall_functions()

        # Clean up any crashed or old time directories to ensure a fresh start from 0 for the new mesh
        import shutil
        import glob
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

        for i, strategy in enumerate(STRATEGIES):
            print(f"\\n🚀 Attempt {i+1}: {strategy['name']}")

            # Clean time dirs again before retrying
            if i > 0:
                for d in os.listdir(self.case_dir):
                    path = os.path.join(self.case_dir, d)
                    try:
                        if d != "0" and os.path.isdir(path):
                            float(d)
                            shutil.rmtree(path, ignore_errors=True)
                    except ValueError:
                        pass
                for p_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
                    for d in os.listdir(p_dir):
                        path = os.path.join(p_dir, d)
                        try:
                            if d != "0" and os.path.isdir(path):
                                float(d)
                                shutil.rmtree(path, ignore_errors=True)
                        except ValueError:
                            pass

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

            # 5. Run solver
            success = self._execute_simpleFoam(solve_procs=solve_procs, solve_method=solve_method, log_file=log_file)

            if success:
                print(f"✅ SUCCESS with {strategy['name']}")
                return True

            print(f"❌ Failed: {strategy['name']}")

        print("💀 All strategies failed")
        return False

"""

content = pattern.sub(new_run_solver, content, count=1)

with open("optimizer/foam_driver.py", "w") as f:
    f.write(content)
