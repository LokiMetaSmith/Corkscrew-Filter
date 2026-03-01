import trimesh
import numpy as np
import os
import warnings

class Validator:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def _load_mesh(self, stl_path):
        """Safely loads a mesh, handling Scenes."""
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=RuntimeWarning, module='trimesh') # Suppress loading warnings
                mesh = trimesh.load(stl_path)

            if isinstance(mesh, trimesh.Scene):
                if len(mesh.geometry) == 0:
                    return None
                mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
            return mesh
        except Exception as e:
            if self.verbose:
                print(f"Error loading {stl_path}: {e}")
            return None

    def validate_mesh(self, stl_path, check_watertight=True, check_volume=True):
        """
        Validates a single STL file.
        Returns (valid: bool, messages: list)
        """
        if not os.path.exists(stl_path):
            return False, [f"File not found: {stl_path}"]

        mesh = self._load_mesh(stl_path)
        if mesh is None:
             return False, ["Failed to load mesh or empty scene."]

        messages = []
        valid = True

        if mesh.is_empty:
            return False, ["Mesh is empty."]

        if check_watertight and not mesh.is_watertight:
            # Caps and Fluid volume should be watertight in this workflow
            messages.append("Mesh is not watertight (has holes or non-manifold edges).")
            valid = False

        # Check for non-manifold geometry specifically (if it's watertight it might still be non-manifold)
        if not mesh.is_volume and valid:
             messages.append("Mesh does not enclose a valid volume (may have self-intersections or inverted normals).")
             valid = False

        if check_volume and mesh.volume <= 0:
            messages.append(f"Mesh has non-positive volume: {mesh.volume:.6f}")
            valid = False

        if len(mesh.faces) == 0:
             messages.append("Mesh has 0 faces.")
             valid = False

        return valid, messages

    def validate_assembly(self, fluid_path, inlet_path, outlet_path, wall_path, tolerance=1.0):
        """
        Validates the assembly of CFD components.
        Checks for existence, validity, and basic alignment.
        tolerance: max deviation in mesh units (default 1.0)
        """
        results = {"valid": True, "messages": []}

        # 1. Validate individual components
        # Note: Inlet/Outlet caps are small, might have tiny volume, but should be watertight cylinders.
        components = {
            "Fluid": fluid_path,
            "Inlet": inlet_path,
            "Outlet": outlet_path,
            "Wall": wall_path
        }

        meshes = {}

        for name, path in components.items():
            v, msgs = self.validate_mesh(path, check_watertight=True, check_volume=True)
            if not v:
                results["valid"] = False
                results["messages"].append(f"{name} validation failed: {'; '.join(msgs)}")
            else:
                if self.verbose:
                    results["messages"].append(f"{name} passed individual checks.")
                # Load for next step
                if results["valid"]: # Only load if valid so far
                    meshes[name] = self._load_mesh(path)

        if not results["valid"]:
            return results

        # 2. Geometric Relations
        try:
            fluid = meshes["Fluid"]
            inlet = meshes["Inlet"]
            outlet = meshes["Outlet"]
            wall = meshes["Wall"]

            f_min, f_max = fluid.bounds
            i_min, i_max = inlet.bounds
            o_min, o_max = outlet.bounds
            w_min, w_max = wall.bounds

            tol = tolerance

            # Check A: Inlet near Fluid Min Z
            # Inlet cap (center) should be close to Fluid min Z
            i_center_z = (i_min[2] + i_max[2]) / 2
            if abs(i_center_z - f_min[2]) > tol and abs(i_center_z - f_max[2]) > tol:
                # Note: Inlet might be at Max Z if coordinate system is flipped, but usually Min Z.
                # Actually, in ModularFilterAssembly, Z=0 is center. Min Z is bottom.
                if not (i_max[2] >= f_min[2] - tol and i_min[2] <= f_max[2] + tol):
                     results["valid"] = False
                     results["messages"].append(f"Inlet is not vertically aligned with Fluid. Inlet Z: {i_min[2]:.2f}-{i_max[2]:.2f}, Fluid Z: {f_min[2]:.2f}-{f_max[2]:.2f}")

            # Check B: Outlet near Fluid Max Z (or Min Z if swapped)
            o_center_z = (o_min[2] + o_max[2]) / 2
            # Verify outlet is at opposite end of inlet?
            # Or just check if it touches the bounding box.
            if not (o_max[2] >= f_min[2] - tol and o_min[2] <= f_max[2] + tol):
                 results["valid"] = False
                 results["messages"].append(f"Outlet is not vertically aligned with Fluid. Outlet Z: {o_min[2]:.2f}-{o_max[2]:.2f}")

            # Check C: Wall encloses Fluid (XY)
            # Wall bounds should be >= Fluid bounds in XY
            # Allow small tolerance
            if (w_min[0] > f_min[0] + tol) or (w_max[0] < f_max[0] - tol) or \
               (w_min[1] > f_min[1] + tol) or (w_max[1] < f_max[1] - tol):
                results["messages"].append(f"Warning: Wall XY bounds do not fully enclose Fluid XY bounds. Wall might be too small or misaligned.")
                # Don't fail hard on this, purely warning

        except Exception as e:
            results["valid"] = False
            results["messages"].append(f"Assembly validation exception: {e}")

        return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        v = Validator(verbose=True)
        res = v.validate_mesh(sys.argv[1])
        print(res)
