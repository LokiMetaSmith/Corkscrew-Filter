"""
gmsh_driver.py
Direct CAD STEP-to-Mesh pipeline for OpenFOAM using Gmsh Python API.
Converts exact B-rep STEP models into 3D volume meshes (.msh / OpenFOAM).
"""

import os
import subprocess
import gmsh

class GmshDriver:
    def __init__(self, mesh_size_min=1.0, mesh_size_max=5.0, algorithm=6):
        self.mesh_size_min = mesh_size_min
        self.mesh_size_max = mesh_size_max
        self.algorithm = algorithm # 6 = Frontal-Delaunay for 2D, 1 = Delaunay for 3D

    def generate_mesh_from_step(self, step_path, output_msh_path, log_file=None):
        """
        Imports a STEP CAD file and generates a 3D volumetric mesh using Gmsh.

        Args:
            step_path (str): Path to input .step file.
            output_msh_path (str): Path to output .msh file.
            log_file (str, optional): Path to log file.

        Returns:
            bool: True if mesh generation succeeded, False otherwise.
        """
        if not os.path.exists(step_path):
            print(f"Error: STEP file does not exist at {step_path}")
            return False

        out_dir = os.path.dirname(output_msh_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        try:
            gmsh.initialize()
            gmsh.option.setNumber("General.Terminal", 0 if log_file else 1)
            gmsh.model.add("step_model")

            # Import STEP model via OpenCASCADE
            shapes = gmsh.model.occ.importShapes(step_path)
            gmsh.model.occ.synchronize()

            # Set meshing size options
            gmsh.option.setNumber("Mesh.MeshSizeMin", self.mesh_size_min)
            gmsh.option.setNumber("Mesh.MeshSizeMax", self.mesh_size_max)
            gmsh.option.setNumber("Mesh.Algorithm", self.algorithm)

            # Auto-assign physical volume
            volumes = gmsh.model.getEntities(dim=3)
            if volumes:
                v_tags = [v[1] for v in volumes]
                gmsh.model.addPhysicalGroup(3, v_tags, tag=1, name="internalMesh")

            # Auto-assign physical surfaces for boundaries
            surfaces = gmsh.model.getEntities(dim=2)
            if surfaces:
                s_tags = [s[1] for s in surfaces]
                gmsh.model.addPhysicalGroup(2, s_tags, tag=2, name="walls")

            # Generate 3D volume mesh
            gmsh.model.mesh.generate(3)

            # Save in MSH format (version 2.2 for gmshToFoam compatibility)
            gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
            gmsh.write(output_msh_path)
            gmsh.finalize()

            if os.path.exists(output_msh_path):
                if log_file:
                    with open(log_file, 'a') as f:
                        f.write(f"Gmsh generated 3D mesh at {output_msh_path}\n")
                return True
            return False

        except Exception as e:
            print(f"Gmsh meshing failed for {step_path}: {e}")
            try:
                gmsh.finalize()
            except Exception:
                pass
            return False

    def convert_msh_to_openfoam(self, msh_path, case_dir):
        """
        Converts a Gmsh .msh file into OpenFOAM polyMesh format using gmshToFoam.

        Args:
            msh_path (str): Path to input .msh file.
            case_dir (str): OpenFOAM case directory.

        Returns:
            bool: True if conversion succeeded, False otherwise.
        """
        cmd = ["gmshToFoam", msh_path, "-case", case_dir]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"gmshToFoam conversion skipped or failed: {e}")
            return False

if __name__ == "__main__":
    driver = GmshDriver()
    print("GmshDriver initialized successfully.")
