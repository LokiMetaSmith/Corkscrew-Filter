import subprocess
import os
import shutil
import trimesh
import numpy as np
import warnings
from utils import run_command_with_spinner

class ScadDriver:
    def __init__(self, scad_file_path, force_native=False):
        self.scad_file_path = scad_file_path

        has_native = shutil.which("openscad") is not None
        has_node = shutil.which("node") is not None

        # Determine preference:
        # Default to WASM (use_native=False) unless forced or Node is missing.
        self.use_native = False

        if force_native and has_native:
            self.use_native = True
        elif not has_node and has_native:
            # Fallback to native if node is missing but native exists
            self.use_native = True

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

        # Check if CFD generation is requested (handle bool or string)
        gen_cfd = run_params.get("GENERATE_CFD_VOLUME", "true")
        if str(gen_cfd).lower() == "true":
             if "CUT_FOR_VISIBILITY" not in run_params:
                 # Disable visibility cut for CFD volume to save processing time
                 run_params["CUT_FOR_VISIBILITY"] = "false"

        # Limit resolution to prevent OOM/Timeouts if not specified
        if "high_res_fn" not in run_params:
             run_params["high_res_fn"] = 100

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

    def _load_clean_mesh(self, stl_path):
        """
        Loads a mesh and cleans degenerate faces.

        Args:
            stl_path (str): Path to the STL file.

        Returns:
            trimesh.Trimesh: The loaded and cleaned mesh, or None if failed.
        """
        try:
            if not os.path.exists(stl_path):
                return None

            # Suppress RuntimeWarning from trimesh during load/process
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=RuntimeWarning, module='trimesh')

                mesh = trimesh.load(stl_path)

                # Handle Scene objects
                if isinstance(mesh, trimesh.Scene):
                    if len(mesh.geometry) == 0:
                        return None
                    # Combine all geometries
                    mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

                # Enhanced cleaning
                # process() removes duplicates, unreferenced vertices, etc.
                mesh.process()

                # Explicitly remove degenerate faces (area check)
                mesh.update_faces(mesh.nondegenerate_faces())

                if len(mesh.faces) == 0:
                    return None

                return mesh
        except Exception as e:
            print(f"Error loading mesh {stl_path}: {e}")
            return None

    def get_bounds(self, stl_path):
        """
        Calculates the bounding box of the STL file.

        Args:
            stl_path (str): Path to the STL file.

        Returns:
            tuple: (min_point, max_point) where each is a numpy array [x, y, z].
                   Returns (None, None) if file read fails.
        """
        mesh = self._load_clean_mesh(stl_path)
        if mesh is None:
            return None, None

        try:
            return mesh.bounds[0], mesh.bounds[1]
        except Exception as e:
            print(f"Error reading STL bounds: {e}")
            return None, None

    def scale_mesh(self, stl_path, scale_factor):
        """
        Scales the mesh in-place by the given factor.

        Args:
            stl_path (str): Path to the STL file.
            scale_factor (float): The scaling factor (e.g., 0.001 for mm -> m).

        Returns:
            bool: True if successful, False otherwise.
        """
        mesh = self._load_clean_mesh(stl_path)
        if mesh is None:
            return False

        try:
            mesh.apply_scale(scale_factor)
            mesh.export(stl_path)
            return True
        except Exception as e:
            print(f"Error scaling mesh: {e}")
            return False

    def get_internal_point(self, stl_path):
        """
        Finds a point strictly inside the mesh using ray tracing.

        Args:
            stl_path (str): Path to the STL file.

        Returns:
            list: [x, y, z] coordinate strictly inside the mesh, or None if failed.
        """
        try:
            mesh = self._load_clean_mesh(stl_path)
            if mesh is None:
                print(f"Could not load valid mesh from: {stl_path}")
                return None

            # robust ray casting
            min_pt, max_pt = mesh.bounds
            center = (min_pt + max_pt) / 2.0

            # Start a ray from outside the bounds
            # Move significantly outside to ensure we are outside
            start_point = min_pt - (max_pt - min_pt) * 0.5

            # Aim at centroid
            direction = center - start_point
            direction = direction / np.linalg.norm(direction)

            # Use ray-mesh intersection
            # Suppress warnings during ray tracing (e.g., if sliver faces remain)
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=RuntimeWarning, module='trimesh')

                intersector = trimesh.ray.ray_triangle.RayMeshIntersector(mesh)
                locations, index_ray, index_tri = intersector.intersects_location(
                    ray_origins=[start_point],
                    ray_directions=[direction]
                )

            if len(locations) >= 2:
                # Sort intersections by distance from start
                dists = np.linalg.norm(locations - start_point, axis=1)
                sorted_indices = np.argsort(dists)

                # The ray enters at index 0, exits at index 1 (ideally)
                p1 = locations[sorted_indices[0]]
                p2 = locations[sorted_indices[1]]

                # Midpoint should be inside
                midpoint = (p1 + p2) / 2.0
                return midpoint.tolist()

            elif len(locations) == 1:
                # Only found one intersection (maybe mesh is open or ray didn't exit)
                # Step slightly past the intersection
                p1 = locations[0]
                # Step 1mm or 5% of bounding box diagonal
                diag = np.linalg.norm(max_pt - min_pt)
                step = max(0.1, diag * 0.01)

                point = p1 + direction * step
                return point.tolist()

            print("Warning: Could not find intersection for internal point.")
            return None

        except Exception as e:
            print(f"Error calculating internal point: {e}")
            return None

if __name__ == "__main__":
    # Test stub
    driver = ScadDriver("corkscrew.scad")
    print(f"Driver initialized. Native mode: {driver.use_native}")
