import subprocess
import os
import shutil
import trimesh
import numpy as np

class ScadDriver:
    def __init__(self, scad_file_path):
        self.scad_file_path = scad_file_path
        self.use_native = shutil.which("openscad") is not None
        if not self.use_native:
            print("Native OpenSCAD not found. Using WASM fallback via 'node export.js'.")

    def generate_stl(self, params, output_path):
        """
        Runs OpenSCAD to generate an STL file with the given parameters.

        Args:
            params (dict): Dictionary of parameter names and values.
            output_path (str): Path to save the generated STL.

        Returns:
            bool: True if successful, False otherwise.
        """

        run_params = params.copy()
        # Default flags for CFD generation if not provided
        if "GENERATE_CFD_VOLUME" not in run_params:
             run_params["GENERATE_CFD_VOLUME"] = "true"
        if "GENERATE_SLICE" not in run_params:
             run_params["GENERATE_SLICE"] = "false"

        param_args = []
        for key, value in run_params.items():
            if isinstance(value, bool):
                val_str = "true" if value else "false"
            else:
                val_str = str(value)
            param_args.extend(["-D", f"{key}={val_str}"])

        if self.use_native:
            cmd = ["openscad", "-o", output_path] + param_args + [self.scad_file_path]
        else:
            # Fallback to Node.js script
            # Assumes export.js is in the root directory relative to where this is run
            # The optimizer is likely run from root as 'python optimizer/main.py'
            cmd = ["node", "export.js", "-o", output_path] + param_args + [self.scad_file_path]

        print(f"Running geometry generation: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if os.path.exists(output_path):
                print(f"STL generated successfully at {output_path}")
                return True
            else:
                print("Generation finished but output file missing.")
                print(result.stderr)
                return False
        except subprocess.CalledProcessError as e:
            print(f"Generation failed with return code {e.returncode}")
            print(e.stderr)
            print(e.stdout)
            return False
        except FileNotFoundError:
            print("Error: Execution command failed. Ensure 'openscad' or 'node' is available.")
            return False

    def get_bounds(self, stl_path):
        """
        Calculates the bounding box of the STL file.

        Args:
            stl_path (str): Path to the STL file.

        Returns:
            tuple: (min_point, max_point) where each is a numpy array [x, y, z].
                   Returns (None, None) if file read fails.
        """
        try:
            mesh = trimesh.load(stl_path)
            # trimesh.load might return a Scene or a Trimesh object.
            # If it's a scene, we dump all geometry.
            if isinstance(mesh, trimesh.Scene):
                if len(mesh.geometry) == 0:
                     return None, None
                # Combine all geometries
                mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

            return mesh.bounds[0], mesh.bounds[1]
        except Exception as e:
            print(f"Error reading STL bounds: {e}")
            return None, None

if __name__ == "__main__":
    # Test stub
    driver = ScadDriver("corkscrew filter.scad")
    print(f"Driver initialized. Native mode: {driver.use_native}")
