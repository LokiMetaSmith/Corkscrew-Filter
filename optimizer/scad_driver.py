import subprocess
import os
import shutil
import trimesh
import numpy as np
from utils import run_command_with_spinner

class ScadDriver:
    def __init__(self, scad_file_path, force_native=False):
        self.scad_file_path = scad_file_path
        # User requested favoring export.js.
        # Only use native if explicitly forced or if node is missing (unlikely in this env).
        self.use_native = force_native and (shutil.which("openscad") is not None)

        if self.use_native:
            print("Using Native OpenSCAD.")
        else:
            print("Using 'node export.js' (WASM/JS driver).")

    def _format_param(self, key, value):
        """Formats a key-value pair for OpenSCAD CLI (-D key=value)."""
        if isinstance(value, bool):
            val_str = "true" if value else "false"
        elif isinstance(value, str):
            # Check if it's a boolean string
            if value.lower() in ["true", "false"]:
                val_str = value.lower()
            # Check if it's a number (rough check)
            elif self._is_number(value):
                val_str = value
            else:
                # It's a string literal, needs quotes
                val_str = f'"{value}"'
        else:
            val_str = str(value)
        return ["-D", f"{key}={val_str}"]

    def _is_number(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def generate_stl(self, params, output_path, log_file=None):
        """
        Runs OpenSCAD to generate an STL file with the given parameters.

        Args:
            params (dict): Dictionary of parameter names and values.
            output_path (str): Path to save the generated STL.
            log_file (str): Path to log file.

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
            param_args.extend(self._format_param(key, value))

        if self.use_native:
            cmd = ["openscad", "-o", output_path] + param_args + [self.scad_file_path]
        else:
            # Fallback to Node.js script
            # Assumes export.js is in the root directory relative to where this is run
            cmd = ["node", "export.js", "-o", output_path] + param_args + [self.scad_file_path]

        if not log_file:
            print(f"Running geometry generation: {' '.join(cmd)}")

        try:
            if log_file:
                run_command_with_spinner(cmd, log_file, description="Generating Geometry")
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if os.path.exists(output_path):
                if not log_file:
                    print(f"STL generated successfully at {output_path}")
                return True
            else:
                print("Generation finished but output file missing.")
                # If using log_file, the error details are there.
                return False
        except subprocess.CalledProcessError as e:
            print(f"Generation failed with return code {e.returncode}")
            # If log_file used, details are in log.
            if not log_file:
                print(e.stderr)
                print(e.stdout)
            return False
        except FileNotFoundError:
            print("Error: Execution command failed. Ensure 'openscad' or 'node' is available.")
            return False

    def generate_visualization(self, params, output_base, log_file=None):
        """
        Generates the solid model and PNG screenshots using export.js.

        Args:
            params (dict): Parameters for the model.
            output_base (str): Base path for output (e.g., 'temp/vis_model').
                              Will generate 'temp/vis_model.stl' and 'temp/vis_model_viewX.png'.
            log_file (str): Path to log file.

        Returns:
            list: List of paths to the generated PNG files, or empty list on failure.
        """
        stl_path = output_base + ".stl"

        # Setup parameters for solid visual
        vis_params = params.copy()
        # Force these to ensure we see the solid part
        vis_params["GENERATE_CFD_VOLUME"] = False
        vis_params["GENERATE_SLICE"] = False
        # Ensure we are generating the main assembly if not specified
        if "part_to_generate" not in vis_params:
            vis_params["part_to_generate"] = "modular_filter_assembly"

        # Build command (Force use of export.js for --png support)
        param_args = []
        for key, value in vis_params.items():
            param_args.extend(self._format_param(key, value))

        # Use node export.js specifically
        cmd = ["node", "export.js", "-o", stl_path, "--png"] + param_args + [self.scad_file_path]

        if not log_file:
            print(f"Running visualization generation: {' '.join(cmd)}")

        try:
            if log_file:
                run_command_with_spinner(cmd, log_file, description="Generating Visualization")
            else:
                subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Collect PNG paths
            png_paths = []
            # export.js generates _view0.png, _view1.png, _view2.png
            for i in range(3):
                png_path = stl_path.replace(".stl", f"_view{i}.png")

                if os.path.exists(png_path):
                    png_paths.append(png_path)

            if not png_paths:
                print("Warning: Visualization ran but no PNGs found.")

            return png_paths

        except Exception as e:
            print(f"Visualization generation failed: {e}")
            if hasattr(e, 'stderr'): print(e.stderr)
            return []

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
    driver = ScadDriver("corkscrew.scad")
    print(f"Driver initialized. Native mode: {driver.use_native}")
