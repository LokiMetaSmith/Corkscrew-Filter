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

    def validate_assembly(self, fluid_path, inlet_path, outlet_path, wall_path, tolerance=1.0, boundaries_config=None):
        """
        Validates the assembly of CFD components.
        Checks for existence, validity, and basic alignment.
        tolerance: max deviation in mesh units (default 1.0)
        boundaries_config: dictionary with alignment definitions from yaml config.
        """
        results = {"valid": True, "messages": []}

        if boundaries_config is None:
            boundaries_config = {}

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

            def check_alignment(component_name, c_min, c_max, f_min, f_max, config_key):
                boundary_conf = boundaries_config.get(config_key, {})
                alignment = boundary_conf.get("alignment")

                if not alignment:
                    results["messages"].append(f"Warning: Alignment not defined in config for {config_key}. Defaulting to 'vertical'.")
                    alignment = "vertical"

                if alignment == "any":
                    return True, ""

                if alignment == "vertical":
                    if not (c_max[2] >= f_min[2] - tol and c_min[2] <= f_max[2] + tol):
                        return False, f"{component_name} is not vertically aligned with Fluid. {component_name} Z: {c_min[2]:.2f}-{c_max[2]:.2f}, Fluid Z: {f_min[2]:.2f}-{f_max[2]:.2f}"
                elif alignment == "horizontal":
                    # For horizontal alignment, check if it intersects with fluid in X or Y bounds
                    # At least one of X or Y should overlap
                    x_overlap = (c_max[0] >= f_min[0] - tol and c_min[0] <= f_max[0] + tol)
                    y_overlap = (c_max[1] >= f_min[1] - tol and c_min[1] <= f_max[1] + tol)
                    if not (x_overlap or y_overlap):
                        return False, f"{component_name} is not horizontally aligned with Fluid. {component_name} X: {c_min[0]:.2f}-{c_max[0]:.2f}, Y: {c_min[1]:.2f}-{c_max[1]:.2f}"
                else:
                    results["messages"].append(f"Warning: Unknown alignment type '{alignment}' for {config_key}. Defaulting to 'vertical'.")
                    if not (c_max[2] >= f_min[2] - tol and c_min[2] <= f_max[2] + tol):
                        return False, f"{component_name} is not vertically aligned with Fluid."

                return True, ""

            # Check A: Inlet Alignment
            inlet_config_key = "inlet"
            is_aligned, msg = check_alignment("Inlet", i_min, i_max, f_min, f_max, inlet_config_key)
            if not is_aligned:
                results["valid"] = False
                results["messages"].append(msg)

            # Check B: Outlet Alignment
            # Note: The outlet STL might represent the clean outlet or dust outlet depending on the setup.
            # Assuming it is the clean_outlet for now, but in reality we might have multiple.
            # Usually 'outlet.stl' corresponds to 'clean_outlet' in manifold config.
            # Or if it's the corkscrew filter, it corresponds to 'outlet'
            # Let's check 'clean_outlet' first, fallback to 'outlet'
            outlet_config_key = "clean_outlet" if "clean_outlet" in boundaries_config else "outlet"
            is_aligned, msg = check_alignment("Outlet", o_min, o_max, f_min, f_max, outlet_config_key)
            if not is_aligned:
                results["valid"] = False
                results["messages"].append(msg)

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
