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

    def generate_interactive_html(self, stl_path, html_output_path, title="Interactive 3D CAD Model"):
        """
        Generates a self-contained interactive 3D WebGL (Three.js) HTML page for an STL file.
        """
        import base64
        if not os.path.exists(stl_path):
            return False

        with open(stl_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ margin: 0; overflow: hidden; background: #181825; color: #cdd6f4; font-family: monospace; }}
        #info {{ position: absolute; top: 10px; left: 10px; z-index: 100; background: rgba(0,0,0,0.6); padding: 8px 14px; border-radius: 6px; border: 1px solid #45475a; }}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>
</head>
<body>
    <div id="info"><strong>OpenAuto-CFD</strong> | {title}</div>
    <script>
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x181825);

        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(50, 50, 50);

        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight1.position.set(1, 1, 1).normalize();
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0x89b4fa, 0.5);
        dirLight2.position.set(-1, -1, -1).normalize();
        scene.add(dirLight2);

        const grid = new THREE.GridHelper(200, 50, 0x45475a, 0x313244);
        scene.add(grid);

        const stlData = "data:application/octet-stream;base64,{b64_data}";
        const loader = new THREE.STLLoader();

        fetch(stlData)
            .then(res => res.arrayBuffer())
            .then(buffer => {{
                const geometry = loader.parse(buffer);
                geometry.center();
                const material = new THREE.MeshStandardMaterial({{ color: 0x89b4fa, metalness: 0.2, roughness: 0.4 }});
                const mesh = new THREE.Mesh(geometry, material);
                scene.add(mesh);

                const boundingBox = new THREE.Box3().setFromObject(mesh);
                const size = boundingBox.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);
                camera.position.set(maxDim * 1.5, maxDim * 1.5, maxDim * 1.5);
                camera.lookAt(0, 0, 0);
            }});

        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});

        function animate() {{
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }}
        animate();
    </script>
</body>
</html>"""

        os.makedirs(os.path.dirname(html_output_path), exist_ok=True)
        with open(html_output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return True

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
