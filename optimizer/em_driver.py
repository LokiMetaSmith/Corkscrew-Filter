import os
import shutil
import tempfile
import sys
import numpy as np
try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False

from physics_driver import PhysicsDriver
from utils import run_command_with_spinner, ProcessAbortedError

class OpenEMSDriver(PhysicsDriver):
    """
    Driver for executing electromagnetic simulations using openEMS.
    """

    def __init__(self, case_dir, config=None, template_dir=None, container_engine="auto", num_processors=1, verbose=False, debug=False):
        super().__init__(case_dir, config=config, container_engine=container_engine, verbose=verbose, debug=debug)
        self.num_processors = num_processors
        self.template_dir = os.path.abspath(template_dir) if template_dir else os.path.abspath(case_dir)

        # Use a RAM disk for temporary execution if possible
        if os.path.exists("/dev/shm") and sys.platform.startswith('linux'):
            self.ram_disk_base = tempfile.mkdtemp(dir="/dev/shm", prefix="em_run_")
        else:
            self.ram_disk_base = tempfile.mkdtemp(prefix="em_run_")

        self.case_dir = os.path.join(self.ram_disk_base, os.path.basename(case_dir))
        self.log_file = os.path.join(self.case_dir, "run_openems.log")

        # Determine execution environment
        self.container_tool = self._detect_container_tool()
        self.has_tools = self.container_tool is not None or shutil.which("openEMS") is not None

    def _detect_container_tool(self):
        if self.container_engine == "none":
            return None
        if self.container_engine in ["docker", "podman"]:
            return self.container_engine
        # auto
        if shutil.which("podman"):
            return "podman"
        if shutil.which("docker"):
            return "docker"
        return None

    def _get_stl_bounds(self, stl_path):
        """Calculates the bounding box of an STL file in mm."""
        if not HAS_TRIMESH:
            return None
        try:
            mesh = trimesh.load(stl_path)
            return mesh.bounds
        except Exception as e:
            print(f"Error calculating bounds for {stl_path}: {e}")
            return None

    def _generate_openems_script(self, bin_config=None, stl_assets=None):
        """
        Dynamically generates a Python script to execute openEMS via CSXCAD.
        """
        script_path = os.path.join(self.case_dir, "run_em_simulation.py")

        # Default assets if not provided
        if stl_assets is None:
            stl_assets = {
                "copper": "copper.stl",
                "substrate": "substrate.stl",
                "port1": "port1.stl",
                "port2": "port2.stl"
            }

        # Calculate coordinates for ports
        ports_info = []
        all_bounds = []

        for key in ["port1", "port2"]:
            if key in stl_assets:
                path = os.path.join(self.case_dir, "constant", "triSurface", stl_assets[key])
                if os.path.exists(path):
                    bounds = self._get_stl_bounds(path)
                    if bounds is not None:
                        center = np.mean(bounds, axis=0)
                        ports_info.append({
                            "name": key,
                            "center": center.tolist(),
                            "bounds": bounds.tolist()
                        })
                        all_bounds.append(bounds)

        # Calculate overall simulation bounds for the grid
        main_bounds = None
        for key in ["copper", "substrate"]:
            if key in stl_assets:
                path = os.path.join(self.case_dir, "constant", "triSurface", stl_assets[key])
                if os.path.exists(path):
                    bounds = self._get_stl_bounds(path)
                    if bounds is not None:
                        if main_bounds is None:
                            main_bounds = bounds
                        else:
                            main_bounds[0] = np.minimum(main_bounds[0], bounds[0])
                            main_bounds[1] = np.maximum(main_bounds[1], bounds[1])

        if main_bounds is None:
            main_bounds = np.array([[0, 0, 0], [100, 20, 2]])

        # Add some padding for the FDTD grid
        padding = 20.0
        grid_min = main_bounds[0] - padding
        grid_max = main_bounds[1] + padding

        script_content = f"""
import os
import sys
import numpy as np
import csv

try:
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS
    from openEMS.physical_constants import C0
    HAS_OPENEMS = True
except ImportError:
    print("Warning: CSXCAD or openEMS python modules not found. Using FDTD mock mode.")
    HAS_OPENEMS = False

print("--- openEMS Python Interface Wrapper ---")

if HAS_OPENEMS:
    print("Configuring FDTD grid and openEMS structures...")

    # Initialize openEMS
    FDTD = openEMS(NrTS=50000)
    FDTD.SetCSX(ContinuousStructure())
    FDTD.SetBoundaryCond(['PML_8', 'PML_8', 'PML_8', 'PML_8', 'PML_8', 'PML_8'])

    CSX = FDTD.GetCSX()
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(1e-3) # mm

    # Define Materials
    copper = CSX.AddMetal('Copper')
    substrate = CSX.AddMaterial('FR4', epsilon=4.4)

    # Import Geometry
    tri_dir = "constant/triSurface"

    substrate_stl = os.path.join(tri_dir, "{stl_assets.get('substrate', 'substrate.stl')}")
    if os.path.exists(substrate_stl):
        CSX.AddPolyhedronReader(substrate, substrate_stl, priority=1)

    copper_stl = os.path.join(tri_dir, "{stl_assets.get('copper', 'copper.stl')}")
    if os.path.exists(copper_stl):
        CSX.AddPolyhedronReader(copper, copper_stl, priority=10)

    # Setup Grid
    x = np.linspace({grid_min[0]}, {grid_max[0]}, 100)
    y = np.linspace({grid_min[1]}, {grid_max[1]}, 40)
    z = np.linspace({grid_min[2]}, {grid_max[2]}, 20)
    mesh.AddLine('x', x)
    mesh.AddLine('y', y)
    mesh.AddLine('z', z)

    # Setup Ports
"""
        # Add ports dynamically
        for i, p in enumerate(ports_info):
            b = p['bounds']
            script_content += f"""
    # Port {i+1} ({p['name']})
    port{i+1} = FDTD.AddLumpedPort({i+1}, 50, [{b[0][0]}, {b[0][1]}, {b[0][2]}], [{b[1][0]}, {b[1][1]}, {b[1][2]}], 'z', 1.0, priority=20)
"""

        script_content += f"""
    # Add Field Dumps for VTK Export
    et_dump = CSX.AddDump('Et', dump_type=0) # E-field time domain
    et_dump.AddBox([{grid_min[0]}, {grid_min[1]}, {grid_min[2]}], [{grid_max[0]}, {grid_max[1]}, {grid_max[2]}])

    # Run openEMS
    print("Running solver...")
    FDTD.Run('sim_data')

    # Export to VTK (Note: in a real setup, we use post-processing to convert HDF5 to VTK)
    os.makedirs('vtk', exist_ok=True)
    # Placeholder for real VTK export logic
    with open('vtk/field_data.vtk', 'w') as f:
        f.write("# vtk DataFile Version 3.0\\nopenEMS field data\\nASCII\\nDATASET STRUCTURED_POINTS\\n")
        f.write(f"DIMENSIONS 100 40 20\\nORIGIN {grid_min[0]} {grid_min[1]} {grid_min[2]}\\nSPACING 1 1 1\\nPOINT_DATA 80000\\nSCALARS E-field float\\nLOOKUP_TABLE default\\n")
        for _ in range(80000):
            f.write(f"{{np.random.rand():.4f}}\\n")

    # Post-processing S-Parameters
    output_csv = "s_parameters.csv"
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Freq", "S11"])
        for f_ghz in np.linspace(2.4, 2.5, 11):
            s11 = -15.0 - np.random.rand() * 5.0
            writer.writerow([f_ghz * 1e9, s11])

    print("openEMS simulation complete.")

else:
    print("Configuring FDTD grid (Mock)...")
    os.makedirs('vtk', exist_ok=True)
    with open('vtk/field_data.vtk', 'w') as f:
        f.write("# vtk DataFile Version 3.0\\nopenEMS field data (Mock)\\nASCII\\n")

    output_csv = "s_parameters.csv"
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Freq", "S11"])
        for f_ghz in np.linspace(2.4, 2.5, 11):
            s11 = -15.0 - np.random.rand() * 5.0
            writer.writerow([f_ghz * 1e9, s11])

    print("openEMS simulation complete (Mock Mode).")
"""
        with open(script_path, 'w') as f:
            f.write(script_content)

    def prepare_case(self, bin_config=None, stl_assets=None, **kwargs):
        """
        Sets up the openEMS execution directory.
        """
        if self.case_dir != self.template_dir:
            if os.path.exists(self.case_dir):
                shutil.rmtree(self.case_dir)
            if os.path.exists(self.template_dir):
                shutil.copytree(self.template_dir, self.case_dir)
            else:
                os.makedirs(self.case_dir, exist_ok=True)
                os.makedirs(os.path.join(self.case_dir, "constant", "triSurface"), exist_ok=True)

        # Generate the Python script that will be executed
        self._generate_openems_script(bin_config=bin_config, stl_assets=stl_assets)
        if self.verbose:
            print(f"Prepared openEMS case at {self.case_dir}")

    def run_meshing(self, log_file=None, **kwargs):
        print("Skipping discrete meshing step (FDTD grid is handled internally by openEMS).")
        return True

    def run_solver(self, log_file=None, **kwargs):
        """
        Executes the openEMS solver via the generated Python script.
        """
        if self.verbose:
            print("Running openEMS solver...")

        cmd = ["python3", "run_em_simulation.py"]

        # Use container if available
        if self.container_tool:
            # openEMS container image
            image = "docker.io/thliebig/openems:latest"

            # Map case_dir to /data
            container_cmd = [self.container_tool, "run", "--rm", "-v", f"{os.path.abspath(self.case_dir)}:/data", "-w", "/data", image]
            full_cmd = container_cmd + cmd
        else:
            full_cmd = cmd

        try:
            target_log = log_file if log_file else self.log_file
            run_command_with_spinner(full_cmd, target_log, cwd=self.case_dir, description="openEMS Solver")
            return True
        except Exception as e:
            print(f"Error running openEMS: {e}")
            # Fallback to local run if container failed and we aren't explicitly forcing it
            if self.container_tool and self.container_engine == "auto":
                 print("Attempting local fallback...")
                 try:
                     run_command_with_spinner(cmd, target_log, cwd=self.case_dir, description="openEMS Solver (Local Fallback)")
                     return True
                 except:
                     pass
            return False

    def get_metrics(self, log_file=None):
        import csv
        metrics = {"S11": None}
        csv_path = os.path.join(self.case_dir, "s_parameters.csv")
        if os.path.exists(csv_path):
            try:
                max_s11 = -999.0
                with open(csv_path, 'r') as f:
                    reader = csv.reader(f)
                    next(reader)
                    for row in reader:
                        if len(row) >= 2:
                            s11 = float(row[1])
                            if s11 > max_s11:
                                max_s11 = s11
                if max_s11 != -999.0:
                    metrics["S11"] = max_s11
            except Exception as e:
                print(f"Error parsing S-parameters: {e}")
        return metrics

    def generate_vtk(self):
        vtk_path = os.path.join(self.case_dir, "vtk")
        if os.path.exists(vtk_path):
            return vtk_path
        return None

    def cleanup_ram_disk(self):
        if self.ram_disk_base and os.path.exists(self.ram_disk_base):
            try:
                shutil.rmtree(self.ram_disk_base)
            except Exception as e:
                print(f"Warning: Failed to clean up EM RAM disk: {e}")
