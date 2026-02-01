import subprocess
import os
import trimesh
import numpy as np

class ScadDriver:
    def __init__(self, scad_file_path):
        self.scad_file_path = scad_file_path

    def generate_stl(self, params, output_path):
        """
        Runs OpenSCAD to generate an STL file with the given parameters.

        Args:
            params (dict): Dictionary of parameter names and values.
            output_path (str): Path to save the generated STL.

        Returns:
            bool: True if successful, False otherwise.
        """
        # Determine which renderer to use
        cmd = []
        try:
            subprocess.run(["openscad", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cmd = ["openscad"]
        except FileNotFoundError:
            print("Native OpenSCAD not found. Using openscad-wasm (Node.js).")
            # Resolve path to export.js (assumed to be in repo root, parent of 'optimizer')
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            export_js = os.path.join(base_dir, "export.js")
            if not os.path.exists(export_js):
                print(f"Error: export.js not found at {export_js}")
                return False
            cmd = ["node", export_js]

        cmd.extend(["-o", output_path])

        # Add parameters
        # Ensure critical flags are set for CFD generation
        # We override params with these specific values if they aren't present,
        # but typically the caller should manage this.
        # For safety, we force GENERATE_CFD_VOLUME=true here?
        # Let's just update the dict.

        run_params = params.copy()
        run_params["GENERATE_CFD_VOLUME"] = "true"
        run_params["GENERATE_SLICE"] = "false"

        for key, value in run_params.items():
            # Handle different types if necessary, but str(value) usually works for numbers and bools
            # For strings in SCAD, they need quotes, but most here seem to be numbers/bools.
            if isinstance(value, bool):
                val_str = "true" if value else "false"
            else:
                val_str = str(value)

            cmd.extend(["-D", f"{key}={val_str}"])

        cmd.append(self.scad_file_path)

        print(f"Running OpenSCAD: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if os.path.exists(output_path):
                print(f"STL generated successfully at {output_path}")
                return True
            else:
                print("OpenSCAD finished but output file missing.")
                print(result.stderr)
                return False
        except subprocess.CalledProcessError as e:
            print(f"OpenSCAD failed with return code {e.returncode}")
            print(e.stderr)
            return False
        except FileNotFoundError:
            # This handles the case where 'node' is not found (since openscad check is handled above)
            print("Error: Executable not found. Ensure OpenSCAD or Node.js is installed.")
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
    # This won't run successfully in the sandbox unless openscad is installed,
    # but checks syntax.
    print("ScadDriver initialized.")
