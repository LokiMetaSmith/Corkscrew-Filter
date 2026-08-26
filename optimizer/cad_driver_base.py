import os
import trimesh
import numpy as np
import warnings

class CadDriverBase:
    """
    Abstract Base Class for CAD Drivers (OpenSCAD, Build123d, etc.)
    """

    def generate_stl(self, params, output_path, log_file=None, params_file=None):
        raise NotImplementedError

    def generate_step(self, params, output_path, log_file=None, params_file=None):
        raise NotImplementedError

    def generate_visualization(self, params, output_base, log_file=None, params_file=None):
        raise NotImplementedError

    def generate_cfd_assets(self, params, output_dir, log_file=None, params_file=None):
        raise NotImplementedError

    def _load_clean_mesh(self, stl_path):
        """Loads a mesh and cleans degenerate faces using trimesh."""
        try:
            if not os.path.exists(stl_path):
                return None

            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=RuntimeWarning, module='trimesh')
                mesh = trimesh.load(stl_path)

                if isinstance(mesh, trimesh.Scene):
                    if len(mesh.geometry) == 0:
                        return None
                    mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

                mesh.process()
                mesh.update_faces(mesh.nondegenerate_faces(1e-14))

                if len(mesh.faces) == 0:
                    return None

                return mesh
        except Exception as e:
            print(f"Error loading mesh {stl_path}: {e}")
            return None

    def get_bounds(self, stl_path):
        """Calculates the bounding box of the STL file."""
        mesh = self._load_clean_mesh(stl_path)
        if mesh is None:
            return None, None
        try:
            return mesh.bounds[0], mesh.bounds[1]
        except Exception as e:
            print(f"Error reading STL bounds: {e}")
            return None, None

    def scale_mesh(self, stl_path, scale_factor):
        """Scales the mesh in-place by the given factor."""
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

    def get_internal_point(self, stl_path, given_point=None):
        """Finds a point strictly inside the mesh using ray tracing and containment checking."""
        try:
            mesh = self._load_clean_mesh(stl_path)
            if mesh is None:
                print(f"Could not load valid mesh from: {stl_path}")
                return None

            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=RuntimeWarning, module='trimesh')

                if given_point is not None:
                    if mesh.contains([given_point])[0]:
                        return given_point
                    else:
                        print(f"Warning: The given point {given_point} is NOT inside the mesh. Re-ray-tracing...")

                min_pt, max_pt = mesh.bounds
                margin = (max_pt - min_pt) * 0.05
                safe_min = min_pt + margin
                safe_max = max_pt - margin

                x_vals = np.linspace(safe_min[0], safe_max[0], 5)
                y_vals = np.linspace(safe_min[1], safe_max[1], 5)
                z_vals = np.linspace(safe_min[2], safe_max[2], 5)

                xv, yv, zv = np.meshgrid(x_vals, y_vals, z_vals)
                grid_points = np.vstack([xv.ravel(), yv.ravel(), zv.ravel()]).T

                is_inside = mesh.contains(grid_points)
                inside_points = grid_points[is_inside]

                if len(inside_points) > 0:
                    center = (min_pt + max_pt) / 2.0
                    dists = np.linalg.norm(inside_points - center, axis=1)
                    best_point = inside_points[np.argmin(dists)]
                    return best_point.tolist()

                center = (min_pt + max_pt) / 2.0
                start_point = min_pt - (max_pt - min_pt) * 0.5
                direction = center - start_point
                direction = direction / np.linalg.norm(direction)

                intersector = trimesh.ray.ray_triangle.RayMeshIntersector(mesh)
                locations, index_ray, index_tri = intersector.intersects_location(
                    ray_origins=[start_point],
                    ray_directions=[direction]
                )

                if len(locations) >= 2:
                    dists = np.linalg.norm(locations - start_point, axis=1)
                    sorted_indices = np.argsort(dists)
                    p1 = locations[sorted_indices[0]]
                    p2 = locations[sorted_indices[1]]
                    midpoint = (p1 + p2) / 2.0
                    if mesh.contains([midpoint])[0]:
                        return midpoint.tolist()

            print("Warning: Could not find any internal point inside the mesh.")
            return None

        except Exception as e:
            print(f"Error calculating internal point: {e}")
            return None
