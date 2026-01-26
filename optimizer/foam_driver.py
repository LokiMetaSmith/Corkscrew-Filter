import os
import shutil
import subprocess
import glob
import re
import math

class FoamDriver:
    def __init__(self, case_dir, template_dir=None):
        self.case_dir = os.path.abspath(case_dir)
        self.template_dir = os.path.abspath(template_dir) if template_dir else self.case_dir
        self.log_file = os.path.join(self.case_dir, "run_foam.log")

    def prepare_case(self):
        """
        Prepares the case directory.
        """
        if self.case_dir != self.template_dir:
            if os.path.exists(self.case_dir):
                shutil.rmtree(self.case_dir)
            shutil.copytree(self.template_dir, self.case_dir)

        tri_surface = os.path.join(self.case_dir, "constant", "triSurface")
        os.makedirs(tri_surface, exist_ok=True)

        # Clean previous results
        self.run_command(["foamListTimes", "-rm"], ignore_error=True)

        # Ensure 0 folder
        zero_orig = os.path.join(self.case_dir, "0.orig")
        zero = os.path.join(self.case_dir, "0")
        if os.path.exists(zero_orig):
            if os.path.exists(zero):
                shutil.rmtree(zero)
            shutil.copytree(zero_orig, zero)

        # Add function objects to controlDict if not present
        self._inject_function_objects()

    def _inject_function_objects(self):
        """
        Injects surfaceFieldValue function objects to measure pressure drop.
        Assumes 'inlet' and 'outlet' patches exist.
        """
        control_dict = os.path.join(self.case_dir, "system", "controlDict")
        if not os.path.exists(control_dict):
            return

        with open(control_dict, 'r') as f:
            content = f.read()

        if "inletPressure" in content:
            return

        func_obj = """
functions
{
    inletPressure
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   1;
        log             true;
        writeFields     false;
        regionType      patch;
        name            inlet;
        operation       areaAverage;
        fields          (p);
    }
    outletPressure
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   1;
        log             true;
        writeFields     false;
        regionType      patch;
        name            outlet;
        operation       areaAverage;
        fields          (p);
    }
}
"""
        # Insert before the last closing brace or append
        # Naive append might fail if file structure is strict, but usually works if inside main dict.
        # Better: replace "// *****************" with func_obj + end marker
        if "// *" in content:
            content = content.replace("// *********", func_obj + "\n// *********", 1)
        else:
            content += func_obj

        with open(control_dict, 'w') as f:
            f.write(content)

    def update_blockMesh(self, bounds, margin=1.2):
        """
        Updates system/blockMeshDict with new bounds.
        """
        if not bounds or bounds[0] is None:
            print("Invalid bounds, skipping blockMesh update.")
            return

        min_pt, max_pt = bounds
        center = (min_pt + max_pt) / 2
        size = (max_pt - min_pt) * margin

        new_min = center - size / 2
        new_max = center + size / 2

        vertices = [
            f"({new_min[0]} {new_min[1]} {new_min[2]})",
            f"({new_max[0]} {new_min[1]} {new_min[2]})",
            f"({new_max[0]} {new_max[1]} {new_min[2]})",
            f"({new_min[0]} {new_max[1]} {new_min[2]})",
            f"({new_min[0]} {new_min[1]} {new_max[2]})",
            f"({new_max[0]} {new_min[1]} {new_max[2]})",
            f"({new_max[0]} {new_max[1]} {new_max[2]})",
            f"({new_min[0]} {new_max[1]} {new_max[2]})"
        ]

        bm_path = os.path.join(self.case_dir, "system", "blockMeshDict")
        with open(bm_path, 'r') as f:
            content = f.read()

        new_vertices_str = "\n    ".join(vertices)
        pattern = re.compile(r"vertices\s*\((.*?)\);", re.DOTALL)

        if pattern.search(content):
            content = pattern.sub(f"vertices\n(\n    {new_vertices_str}\n);", content)

        with open(bm_path, 'w') as f:
            f.write(content)

    def run_meshing(self):
        """
        Runs the meshing pipeline.
        """
        # Ensure we capture output
        cmds = [
            ["blockMesh"],
            ["surfaceFeatureExtract"],
            ["snappyHexMesh", "-overwrite"],
            # Attempt to identify patches if standard naming didn't work.
            # "autoPatch" splits the boundary based on angle.
            # We use 80 degrees to catch the flat caps.
            ["autoPatch", "80", "-overwrite"],
            ["checkMesh"]
        ]

        for cmd in cmds:
            if not self.run_command(cmd):
                return False
        return True

    def run_solver(self):
        """
        Runs the solver.
        """
        return self.run_command(["simpleFoam"])

    def run_particle_tracking(self):
        """
        Runs particle tracking (Lagrangian).
        Assuming we use icoUncoupledKinematicParcelFoam for one-way coupling test,
        or a custom solver.

        This requires constant/kinematicCloudProperties to be present.
        """
        # Check if properties exist
        cloud_props = os.path.join(self.case_dir, "constant", "kinematicCloudProperties")
        if not os.path.exists(cloud_props):
            print("Warning: kinematicCloudProperties not found. Skipping particle tracking.")
            return False

        # We might need to map fields if using a different solver.
        # But for now, we try running the solver directly.
        return self.run_command(["icoUncoupledKinematicParcelFoam"])

    def run_command(self, cmd, ignore_error=False):
        print(f"Running {' '.join(cmd)} in {self.case_dir}...")
        try:
            with open(self.log_file, "a") as log:
                subprocess.run(
                    cmd,
                    cwd=self.case_dir,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True
                )
            return True
        except subprocess.CalledProcessError:
            print(f"Command {' '.join(cmd)} failed.")
            if not ignore_error:
                return False
            return True
        except FileNotFoundError:
            print(f"Executable {cmd[0]} not found.")
            return False

    def get_metrics(self):
        """
        Parses logs to get metrics.
        Returns dict: {'delta_p': float, 'residuals': float, 'particle_data': ...}
        """
        metrics = {'delta_p': None, 'residuals': None}

        # 1. Parse Residuals from log
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                # Find last "Solving for Ux, ... Initial residual = X, Final residual = Y"
                for line in reversed(lines):
                    if "Solving for Ux" in line:
                        m = re.search(r"Final residual = ([\d\.e\-\+]+)", line)
                        if m:
                            metrics['residuals'] = float(m.group(1))
                        break

        # 2. Parse Pressure Drop
        # Look for postProcessing/inletPressure/0/surfaceFieldValue.dat
        # and postProcessing/outletPressure/0/surfaceFieldValue.dat
        p_in = self._read_latest_postProcessing("inletPressure")
        p_out = self._read_latest_postProcessing("outletPressure")

        if p_in is not None and p_out is not None:
            metrics['delta_p'] = abs(p_in - p_out)

        return metrics

    def _read_latest_postProcessing(self, func_name):
        """
        Reads the last value from a function object output.
        """
        # Path: case/postProcessing/func_name/*/surfaceFieldValue.dat
        base_path = os.path.join(self.case_dir, "postProcessing", func_name)
        if not os.path.exists(base_path):
            return None

        # Find latest time directory
        time_dirs = glob.glob(os.path.join(base_path, "*"))
        if not time_dirs:
            return None
        latest_dir = max(time_dirs, key=os.path.getmtime)

        dat_file = os.path.join(latest_dir, "surfaceFieldValue.dat")
        if not os.path.exists(dat_file):
            return None

        try:
            with open(dat_file, 'r') as f:
                lines = f.readlines()
                # Last line should contain data. Skip comments #
                for line in reversed(lines):
                    if line.strip() and not line.startswith("#"):
                        # Format: time value
                        parts = line.split()
                        if len(parts) >= 2:
                            return float(parts[1])
        except Exception as e:
            print(f"Error reading {dat_file}: {e}")

        return None

if __name__ == "__main__":
    driver = FoamDriver("corkscrewFilter")
    print("FoamDriver initialized.")
