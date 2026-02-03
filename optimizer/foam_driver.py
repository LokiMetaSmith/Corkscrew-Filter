import os
import shutil
import subprocess
import glob
import re
import math
import sys
from utils import run_command_with_spinner

class FoamDriver:
    def __init__(self, case_dir, template_dir=None):
        self.case_dir = os.path.abspath(case_dir)
        self.template_dir = os.path.abspath(template_dir) if template_dir else self.case_dir
        self.log_file = os.path.join(self.case_dir, "run_foam.log")
        self.docker_image = os.environ.get("OPENFOAM_IMAGE", "opencfd/openfoam-default:2406")
        self.use_docker = self._should_use_docker()

    def _should_use_docker(self):
        """
        Determines if Docker should be used.
        Returns True if 'simpleFoam' is NOT found in the system PATH.
        """
        if shutil.which("simpleFoam"):
            print("Native OpenFOAM found.")
            return False
        else:
            if shutil.which("docker"):
                print("Native OpenFOAM not found. Using Docker wrapper.")
                return True
            else:
                print("Warning: Neither native OpenFOAM nor Docker found.")
                return False

    def _get_docker_command(self, cmd, cwd):
        """
        Constructs the Docker command to run the given shell command inside the container.
        """
        # We assume the cwd is within the project root or the case directory.
        # To simplify, we mount the case directory to /data in the container
        # and set the working directory to /data.

        # However, OpenFOAM often needs access to parent directories if using shared libs or includes.
        # A safer bet for this specific project structure is to mount the 'case_dir' to '/home/openfoam/run'
        # or similar.

        # User ID mapping to avoid permission issues on Linux
        # On Mac/Windows Docker Desktop handles this automagically usually, but explicit is good.
        uid_gid_args = []
        if sys.platform == "linux":
            uid = os.getuid()
            gid = os.getgid()
            uid_gid_args = ["-u", f"{uid}:{gid}"]

        # Mount point: Target path inside container
        container_workdir = "/home/openfoam/run"

        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{cwd}:{container_workdir}",
            "-w", container_workdir,
        ] + uid_gid_args + [
            self.docker_image,
            "/bin/bash", "-c", " ".join(cmd)
        ]

        return docker_cmd

    def prepare_case(self):
        """
        Prepares the case directory.
        """
        if self.case_dir != self.template_dir:
            if os.path.exists(self.case_dir):
                shutil.rmtree(self.case_dir)
            shutil.copytree(self.template_dir, self.case_dir)

        tri_surface = os.path.join(self.case_dir, "constant", "triSurface")
        os.makedirs(tri_surface, exist_ok=True)

        # Clean previous results
        self.run_command(["foamListTimes", "-rm"], ignore_error=True)

        # Ensure 0 folder
        zero_orig = os.path.join(self.case_dir, "0.orig")
        zero = os.path.join(self.case_dir, "0")
        if os.path.exists(zero_orig):
            if os.path.exists(zero):
                shutil.rmtree(zero)
            shutil.copytree(zero_orig, zero)

        # Add function objects to controlDict if not present
        self._inject_function_objects()

    def _inject_function_objects(self):
        """
        Injects surfaceFieldValue function objects to measure pressure drop.
        Assumes 'inlet' and 'outlet' patches exist.
        """
        control_dict = os.path.join(self.case_dir, "system", "controlDict")
        if not os.path.exists(control_dict):
            return

        with open(control_dict, 'r') as f:
            content = f.read()

        if "inletPressure" in content:
            return

        func_obj = """
functions
{
    inletPressure
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   1;
        log             true;
        writeFields     false;
        regionType      patch;
        name            inlet;
        operation       areaAverage;
        fields          (p);
    }
    outletPressure
    {
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        writeControl    timeStep;
        writeInterval   1;
        log             true;
        writeFields     false;
        regionType      patch;
        name            outlet;
        operation       areaAverage;
        fields          (p);
    }
}
"""
        # Insert before the last closing brace or append
        # Naive append might fail if file structure is strict, but usually works if inside main dict.
        # Better: replace "// *****************" with func_obj + end marker
        if "// *" in content:
            content = content.replace("// *********", func_obj + "\n// *********", 1)
        else:
            content += func_obj

        with open(control_dict, 'w') as f:
            f.write(content)

    def update_blockMesh(self, bounds, margin=1.2):
        """
        Updates system/blockMeshDict with new bounds.
        """
        if not bounds or bounds[0] is None:
            print("Invalid bounds, skipping blockMesh update.")
            return

        self.bounds = bounds
        min_pt, max_pt = bounds
        center = (min_pt + max_pt) / 2
        size = (max_pt - min_pt) * margin

        new_min = center - size / 2
        new_max = center + size / 2

        vertices = [
            f"({new_min[0]} {new_min[1]} {new_min[2]})",
            f"({new_max[0]} {new_min[1]} {new_min[2]})",
            f"({new_max[0]} {new_max[1]} {new_min[2]})",
            f"({new_min[0]} {new_max[1]} {new_min[2]})",
            f"({new_min[0]} {new_min[1]} {new_max[2]})",
            f"({new_max[0]} {new_min[1]} {new_max[2]})",
            f"({new_max[0]} {new_max[1]} {new_max[2]})",
            f"({new_min[0]} {new_max[1]} {new_max[2]})"
        ]

        bm_path = os.path.join(self.case_dir, "system", "blockMeshDict")
        with open(bm_path, 'r') as f:
            content = f.read()

        new_vertices_str = "\n    ".join(vertices)
        pattern = re.compile(r"vertices\s*\((.*?)\);", re.DOTALL)

        if pattern.search(content):
            content = pattern.sub(f"vertices\n(\n    {new_vertices_str}\n);", content)

        with open(bm_path, 'w') as f:
            f.write(content)

    def _write_topoSetDict(self):
        """
        Writes system/topoSetDict to define inlet and outlet faces based on bounds.
        """
        if not hasattr(self, 'bounds') or self.bounds[0] is None:
            print("No bounds available for topoSet.")
            return

        min_pt, max_pt = self.bounds
        # Define a thin slice at the bottom (Z-min) and top (Z-max)
        # Assuming Z is the vertical axis.
        z_min = min_pt[2]
        z_max = max_pt[2]

        # Tolerance for box selection
        tol = 0.5 # mm

        topo_content = f"""
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2406                                 |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      topoSetDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

actions
(
    // Inlet (Bottom)
    {{
        name    inlet_faces;
        type    faceSet;
        action  new;
        source  boxToFace;
        sourceInfo
        {{
            box ({min_pt[0]-100} {min_pt[1]-100} {z_min - tol}) ({max_pt[0]+100} {max_pt[1]+100} {z_min + tol});
        }}
    }}

    // Outlet (Top)
    {{
        name    outlet_faces;
        type    faceSet;
        action  new;
        source  boxToFace;
        sourceInfo
        {{
            box ({min_pt[0]-100} {min_pt[1]-100} {z_max - tol}) ({max_pt[0]+100} {max_pt[1]+100} {z_max + tol});
        }}
    }}
);

// ************************************************************************* //
"""
        with open(os.path.join(self.case_dir, "system", "topoSetDict"), 'w') as f:
            f.write(topo_content)

    def _write_createPatchDict(self):
        """
        Writes system/createPatchDict to create patches from face sets.
        """
        content = """
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2406                                 |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      createPatchDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

pointSync false;

patches
(
    {
        name inlet;
        patchInfo
        {
            type patch;
        }
        constructFrom set;
        set inlet_faces;
    }
    {
        name outlet;
        patchInfo
        {
            type patch;
        }
        constructFrom set;
        set outlet_faces;
    }
);

// ************************************************************************* //
"""
        with open(os.path.join(self.case_dir, "system", "createPatchDict"), 'w') as f:
            f.write(content)

    def run_meshing(self, log_file=None):
        """
        Runs the meshing pipeline.
        """
        # Generate dictionaries for patch creation
        self._write_topoSetDict()
        self._write_createPatchDict()

        # Ensure we capture output
        cmds = [
            ["blockMesh"],
            ["surfaceFeatureExtract"],
            ["snappyHexMesh", "-overwrite"],
            ["topoSet"],
            ["createPatch", "-overwrite"],
            ["checkMesh"]
        ]

        for cmd in cmds:
            # Pass command name as description
            if not self.run_command(cmd, log_file=log_file, description=f"Meshing ({cmd[0]})"):
                return False
        return True

    def run_solver(self, log_file=None):
        """
        Runs the solver.
        """
        return self.run_command(["simpleFoam"], log_file=log_file, description="Solving CFD")

    def run_particle_tracking(self, log_file=None):
        """
        Runs particle tracking (Lagrangian).
        Assuming we use icoUncoupledKinematicParcelFoam for one-way coupling test.
        """
        # Check if properties exist
        cloud_props = os.path.join(self.case_dir, "constant", "kinematicCloudProperties")
        if not os.path.exists(cloud_props):
            print("Warning: kinematicCloudProperties not found. Skipping particle tracking.")
            return False

        return self.run_command(["icoUncoupledKinematicParcelFoam"], log_file=log_file, description="Particle Tracking")

    def run_command(self, cmd, log_file=None, ignore_error=False, description="Running command"):

        final_cmd = cmd
        if self.use_docker:
            # Wrap in docker call
            final_cmd = self._get_docker_command(cmd, self.case_dir)
            # When using Docker, we are effectively running "docker" as the command,
            # so we shouldn't fail on FileNotFoundError for the inner command.
            # But subprocess.run will invoke 'docker', which must exist.

        # Use passed log_file or fallback to self.log_file
        target_log = log_file if log_file else self.log_file

        if not log_file:
            print(f"Running {' '.join(final_cmd)}...")

        try:
            cwd = self.case_dir if not self.use_docker else os.getcwd()

            if log_file:
                run_command_with_spinner(final_cmd, target_log, cwd=cwd, description=description)
            else:
                 # Legacy/Fallback behavior
                with open(target_log, "a") as log:
                    log.write(f"\n# Executing: {' '.join(final_cmd)}\n")
                    log.flush()
                    subprocess.run(
                        final_cmd,
                        cwd=cwd,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        check=True
                    )

            return True
        except subprocess.CalledProcessError:
            if not log_file:
                print(f"Command {' '.join(cmd)} failed.")

            if not ignore_error:
                return False
            return True
        except FileNotFoundError:
            if self.use_docker:
                print("Error: 'docker' executable not found.")
            else:
                print(f"Executable {cmd[0]} not found.")
            return False

    def get_metrics(self, log_file=None):
        """
        Parses logs to get metrics.
        Returns dict: {'delta_p': float, 'residuals': float, 'particle_data': ...}
        """
        metrics = {'delta_p': None, 'residuals': None}

        target_log = log_file if log_file else self.log_file

        # 1. Parse Residuals from log
        if os.path.exists(target_log):
            with open(target_log, 'r') as f:
                lines = f.readlines()
                # Find last "Solving for Ux, ... Initial residual = X, Final residual = Y"
                for line in reversed(lines):
                    if "Solving for Ux" in line:
                        m = re.search(r"Final residual = ([\d\.e\-\+]+)", line)
                        if m:
                            metrics['residuals'] = float(m.group(1))
                        break

        # 2. Parse Pressure Drop
        # Look for postProcessing/inletPressure/0/surfaceFieldValue.dat
        # and postProcessing/outletPressure/0/surfaceFieldValue.dat
        p_in = self._read_latest_postProcessing("inletPressure")
        p_out = self._read_latest_postProcessing("outletPressure")

        if p_in is not None and p_out is not None:
            metrics['delta_p'] = abs(p_in - p_out)

        # 3. Parse Particle Tracking (Separation Efficiency)
        # We look for "Injector model1: injected X parcels" and "Current number of parcels" at the end.
        if os.path.exists(target_log):
            total_injected = 0
            current_parcels = 0

            with open(target_log, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    # "Injector model1: injected 100 parcels, mass 1e-06 kg"
                    if "injected" in line and "parcels" in line:
                         m = re.search(r"injected\s+(\d+)\s+parcels", line)
                         if m:
                             total_injected += int(m.group(1))

                # Check the FINAL "Current number of parcels"
                for line in reversed(lines):
                    if "Current number of parcels" in line:
                        m = re.search(r"Current number of parcels\s+=\s+(\d+)", line)
                        if m:
                            current_parcels = int(m.group(1))
                        break

            if total_injected > 0:
                # Efficiency: Percentage of particles remaining (stuck to walls)
                # Assumption: Outlet/Inlet are 'escape', Walls are 'stick'.
                metrics['separation_efficiency'] = (current_parcels / total_injected) * 100.0
                metrics['particles_injected'] = total_injected
                metrics['particles_captured'] = current_parcels

        return metrics

    def _read_latest_postProcessing(self, func_name):
        """
        Reads the last value from a function object output.
        """
        # Path: case/postProcessing/func_name/*/surfaceFieldValue.dat
        base_path = os.path.join(self.case_dir, "postProcessing", func_name)
        if not os.path.exists(base_path):
            return None

        # Find latest time directory
        time_dirs = glob.glob(os.path.join(base_path, "*"))
        if not time_dirs:
            return None
        latest_dir = max(time_dirs, key=os.path.getmtime)

        dat_file = os.path.join(latest_dir, "surfaceFieldValue.dat")
        if not os.path.exists(dat_file):
            return None

        try:
            with open(dat_file, 'r') as f:
                lines = f.readlines()
                # Last line should contain data. Skip comments #
                for line in reversed(lines):
                    if line.strip() and not line.startswith("#"):
                        # Format: time value
                        parts = line.split()
                        if len(parts) >= 2:
                            return float(parts[1])
        except Exception as e:
            print(f"Error reading {dat_file}: {e}")

        return None

if __name__ == "__main__":
    driver = FoamDriver("corkscrewFilter")
    print("FoamDriver initialized.")
