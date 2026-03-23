import re

with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

execute_func = """    def _execute_simpleFoam(self, solve_procs=1, solve_method='scotch', log_file=None):
        if solve_procs > 1:
            self._generate_decomposeParDict(num_processors=solve_procs, method=solve_method)
            if not self.run_command(["decomposePar", "-force"], log_file=log_file, description="Decomposing Domain"): return False
            cmd = ["mpirun", "--allow-run-as-root", "--oversubscribe", "-np", str(solve_procs), "simpleFoam", "-parallel"]
            success, output = self.run_command(cmd, log_file=log_file, description=f"Solving CFD (Parallel {solve_procs} CPUs)", timeout=14400, capture_output=True)
        else:
            success, output = self.run_command(["simpleFoam"], log_file=log_file, description="Solving CFD", timeout=14400, capture_output=True)

        failure_signals = [
            "floating point exception",
            "segmentation fault",
            "nan",
            "diverging",
            "foam fatal error",
            "foam aborting"
        ]

        if not success:
            return False

        out = output.lower()
        if any(sig in out for sig in failure_signals):
            return False

        if "end" in out:
            if solve_procs > 1:
                import glob, shutil
                if not self.run_command(["reconstructPar", "-latestTime"], log_file=log_file, description="Reconstructing Domain"): return False
                for proc_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
                    shutil.rmtree(proc_dir, ignore_errors=True)
            return True

        return False

"""

pos = content.find("    def run_solver(self")
if pos != -1:
    content = content[:pos] + execute_func + content[pos:]

with open("optimizer/foam_driver.py", "w") as f:
    f.write(content)
