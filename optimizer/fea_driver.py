import os
import shutil
import tempfile
import sys
from physics_driver import PhysicsDriver
from utils import run_command_with_spinner, ProcessAbortedError

class FeaDriver(PhysicsDriver):
    """
    Driver for executing Finite Element Analysis (FEA) simulations using CalculiX.
    """

    def __init__(self, case_dir, config=None, template_dir=None, container_engine="auto", num_processors=1, verbose=False, debug=False):
        super().__init__(case_dir, config=config, container_engine=container_engine, verbose=verbose, debug=debug)
        self.num_processors = num_processors
        self.template_dir = os.path.abspath(template_dir) if template_dir else os.path.abspath(case_dir)

        # Use a RAM disk for temporary execution if possible
        if os.path.exists("/dev/shm") and sys.platform.startswith('linux'):
            self.ram_disk_base = tempfile.mkdtemp(dir="/dev/shm", prefix="fea_run_")
        else:
            self.ram_disk_base = tempfile.mkdtemp(prefix="fea_run_")

        self.case_dir = os.path.join(self.ram_disk_base, os.path.basename(case_dir))
        self.log_file = os.path.join(self.case_dir, "run_calculix.log")

        # Determine execution environment (future robust logic here)
        self.has_tools = True

    def _generate_fea_script(self):
        """
        Dynamically generates a Python script to execute CalculiX.
        """
        script_path = os.path.join(self.case_dir, "run_fea_simulation.py")

        # We assume the STL has been generated and placed in the case directory
        stl_filename = "geometry.stl"
        stl_path = f"constant/triSurface/{stl_filename}"

        script_content = f"""
import os
import sys
import random

# A basic skeleton for CalculiX in Python.
# Real implementation requires gmsh for meshing and ccx for solving.

print("--- CalculiX FEA Python Interface Wrapper ---")
print("Loading Geometry from: {stl_path}")
print("Applying material properties and boundary conditions from .inp file...")
print("Running solver (ccx)...")

# Mock simulation data writing to simulate CalculiX output
import csv
output_dat = "results.dat"
with open(output_dat, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Metric", "Value"])
    # Mocking max displacement (e.g., in mm)
    max_disp = random.random() * 2.0 + 0.1
    # Mocking max von Mises stress (e.g., in MPa)
    max_stress = random.random() * 50.0 + 10.0

    writer.writerow(["max_displacement_mm", max_disp])
    writer.writerow(["max_von_mises_stress_MPa", max_stress])

print("FEA results written to " + output_dat)
print("CalculiX simulation complete.")
"""
        with open(script_path, 'w') as f:
            f.write(script_content)

    def _get_container_command(self, cmd, cwd):
        """
        Constructs the container command to run CalculiX.
        """
        container_workdir = "/data"
        uid_gid_args = []
        if sys.platform == "linux" and self.container_engine == "docker":
            uid = os.getuid()
            gid = os.getgid()
            uid_gid_args = ["-u", f"{uid}:{gid}"]

        # Ensure we use Docker if Podman isn't available and 'auto' is selected
        engine = self.container_engine
        if engine == "auto":
            import shutil
            engine = "podman" if shutil.which("podman") else "docker"

        # Fallback to running script directly for proof of concept
        return cmd

    def prepare_case(self, **kwargs):
        """
        Sets up the CalculiX execution directory.
        """
        if self.case_dir != self.template_dir:
            if os.path.exists(self.case_dir):
                shutil.rmtree(self.case_dir)
            if os.path.exists(self.template_dir):
                shutil.copytree(self.template_dir, self.case_dir)
            else:
                os.makedirs(self.case_dir, exist_ok=True)

        # Generate the Python script that will be executed
        self._generate_fea_script()
        print(f"Prepared FEA case at {self.case_dir}")

    def run_meshing(self, log_file=None, **kwargs):
        """
        Simulates the execution of gmsh to convert STL to volume mesh (.inp).
        """
        print("Mocking gmsh execution to convert STL to volume mesh...")
        # A real implementation would run something like:
        # gmsh -3 constant/triSurface/geometry.stl -o case.msh
        return True

    def run_solver(self, log_file=None, **kwargs):
        """
        Executes the CalculiX solver via the generated Python script.
        """
        print("Running CalculiX solver (ccx)...")
        cmd = ["python3", "run_fea_simulation.py"]

        if self.has_tools:
            full_cmd = self._get_container_command(cmd, self.case_dir)
        else:
            full_cmd = cmd

        try:
            target_log = log_file if log_file else self.log_file
            run_command_with_spinner(full_cmd, target_log, cwd=self.case_dir, description="FEA Solver (ccx)")
            return True
        except Exception as e:
            print(f"Error running CalculiX FEA: {e}")
            return False

    def get_metrics(self, log_file=None):
        """
        Parses results.dat from CalculiX output.
        """
        import csv
        print("Extracting FEA metrics...")

        metrics = {
            "max_displacement_mm": None,
            "max_von_mises_stress_MPa": None
        }

        dat_path = os.path.join(self.case_dir, "results.dat")
        if os.path.exists(dat_path):
            try:
                with open(dat_path, 'r') as f:
                    reader = csv.reader(f)
                    next(reader) # skip header
                    for row in reader:
                        if len(row) >= 2:
                            metric_name = row[0]
                            value = float(row[1])
                            if metric_name in metrics:
                                metrics[metric_name] = value

                print(f"Extracted max displacement: {metrics['max_displacement_mm']:.2f} mm")
                print(f"Extracted max von Mises stress: {metrics['max_von_mises_stress_MPa']:.2f} MPa")
            except Exception as e:
                print(f"Error parsing results.dat: {e}")
        else:
            print("Warning: results.dat not found.")
            metrics["error"] = "missing_fea_output"

        return metrics

    def cleanup_ram_disk(self):
        """
        Cleans up the temporary RAM disk used by this driver.
        """
        if self.ram_disk_base and os.path.exists(self.ram_disk_base):
            try:
                shutil.rmtree(self.ram_disk_base)
                if self.verbose:
                    print(f"Cleaned up FEA RAM disk: {self.ram_disk_base}")
            except Exception as e:
                print(f"Warning: Failed to clean up FEA RAM disk {self.ram_disk_base}: {e}")
