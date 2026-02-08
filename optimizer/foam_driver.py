import os
import shutil
import subprocess
import glob
import re
import math
import sys
import numpy as np
from utils import run_command_with_spinner

class FoamDriver:
    def __init__(self, case_dir, template_dir=None, container_engine="auto"):
        self.case_dir = os.path.abspath(case_dir)
        self.template_dir = os.path.abspath(template_dir) if template_dir else self.case_dir
        self.log_file = os.path.join(self.case_dir, "run_foam.log")
        self.docker_image = os.environ.get("OPENFOAM_IMAGE", "opencfd/openfoam-default:2406")
        self.has_tools = False
        self.container_tool = None
        self.use_container = False
        self.container_engine = container_engine
        self._check_execution_environment()

    def _is_tool_usable(self, tool):
        """
        Checks if the container tool is actually usable (can connect to daemon/vm).
        """
        try:
            # Check if we can get info from the daemon/machine
            # Use short timeout because we don't want to wait long if it's hanging
            subprocess.run([tool, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _try_start_podman(self):
        print("Attempting to start Podman machine...")
        try:
            # Capture output to print specific errors
            result = subprocess.run(
                ["podman", "machine", "start"],
                check=True,
                timeout=120,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print("Podman machine start command finished. Verifying...")
            if self._is_tool_usable("podman"):
                return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to start Podman: {e.stderr.strip()}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Failed to start Podman: {e}")

        print("Failed to auto-start Podman.")
        return False

    def _check_execution_environment(self):
        """
        Determines the execution environment (Native, Podman, or Docker).
        Sets self.has_tools, self.container_tool, and self.use_container.
        """
        # 1. Native OpenFOAM (Preferred unless forced otherwise)
        if self.container_engine == "auto" and shutil.which("simpleFoam"):
            print("Native OpenFOAM found.")
            self.has_tools = True
            self.container_tool = None
            self.use_container = False
            return

        # 2. Podman
        if self.container_engine in ["auto", "podman"]:
            if shutil.which("podman") and (self._is_tool_usable("podman") or self._try_start_podman()):
                print("Using Podman wrapper.")
                self.has_tools = True
                self.container_tool = "podman"
                self.use_container = True
                return

        # 3. Docker
        if self.container_engine in ["auto", "docker"]:
            if shutil.which("docker"):
                if self._is_tool_usable("docker"):
                    print("Using Docker wrapper.")
                    self.has_tools = True
                    self.container_tool = "docker"
                    self.use_container = True
                    return
            elif self.container_engine == "docker":
                print("Debug: 'docker' executable not found in PATH.")

        # Fallback / Failure
        # Diagnostic messages
        if self.container_engine in ["auto", "podman"] and shutil.which("podman"):
            print("Warning: Podman found but not responsive. Check 'podman machine start'.")
        if self.container_engine in ["auto", "docker"] and shutil.which("docker"):
            print("Warning: Docker found but not responsive. Check Docker Desktop/daemon.")

        print("Warning: No usable OpenFOAM environment found.")
        self.has_tools = False
        self.container_tool = None
        self.use_container = False

    def _get_container_command(self, cmd, cwd):
        """
        Constructs the container command (Docker or Podman) to run the given shell command inside the container.
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
            # Only add UID mapping if using Docker.
            # Podman (rootless) usually handles mapping automatically and passing -u breaks volume permissions.
            if self.container_tool == "docker":
                uid = os.getuid()
                gid = os.getgid()
                uid_gid_args = ["-u", f"{uid}:{gid}"]

        # Mount point: Target path inside container
        container_workdir = "/home/openfoam/run"

        container_cmd = [
            self.container_tool, "run", "--rm",
            "-v", f"{cwd}:{container_workdir}",
            "-w", container_workdir,
        ] + uid_gid_args + [
            self.docker_image,
            "/bin/bash", "-lc", f"cd {container_workdir} && " + " ".join(cmd)
        ]

        return container_cmd

    def prepare_case(self, keep_mesh=False):
        """
        Prepares the case directory.
        """
        if not keep_mesh and self.case_dir != self.template_dir:
            if os.path.exists(self.case_dir):
                shutil.rmtree(self.case_dir)
            shutil.copytree(self.template_dir, self.case_dir)

        tri_surface = os.path.join(self.case_dir, "constant", "triSurface")
        os.makedirs(tri_surface, exist_ok=True)

        # Ensure extendedFeatureEdgeMesh exists for surfaceFeatureExtract
        edge_mesh = os.path.join(self.case_dir, "constant", "extendedFeatureEdgeMesh")
        if os.path.exists(edge_mesh):
            shutil.rmtree(edge_mesh)
        os.makedirs(edge_mesh, exist_ok=True)

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

    def update_blockMesh(self, bounds, margin=(1.2, 1.2, 0.9), target_cell_size=1.5):
        """
        Updates system/blockMeshDict with new bounds.
        """
        # Check for None explicitly to handle numpy array ambiguity
        if bounds is None or bounds[0] is None:
            print("Invalid bounds, skipping blockMesh update.")
            return

        self.bounds = bounds
        min_pt, max_pt = bounds

        # Ensure margin is array-like
        try:
            # Check if iterable
            iter(margin)
            margin_arr = np.array(margin)
        except TypeError:
            # Scalar
            margin_arr = np.array([margin, margin, margin])

        center = (min_pt + max_pt) / 2
        size = (max_pt - min_pt) * margin_arr

        new_min = center - size / 2
        new_max = center + size / 2

        # Calculate cell counts based on target resolution
        # target_cell_size is passed in (default 1.5mm)
        nx = max(1, int(math.ceil(size[0] / target_cell_size)))
        ny = max(1, int(math.ceil(size[1] / target_cell_size)))
        nz = max(1, int(math.ceil(size[2] / target_cell_size)))

        # Ensure minimum resolution
        nx = max(10, nx)
        ny = max(10, ny)
        nz = max(10, nz)

        print(f"Calculated blockMesh resolution: ({nx} {ny} {nz})")

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

        # Update blocks with calculated resolution
        # Matches: hex (0 1 2 3 4 5 6 7) (20 20 20)
        pattern_blocks = re.compile(r"hex\s*\([^\)]+\)\s*\(\s*\d+\s+\d+\s+\d+\s*\)", re.DOTALL)
        if pattern_blocks.search(content):
             content = pattern_blocks.sub(f"hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz})", content)

        with open(bm_path, 'w') as f:
            f.write(content)

    def update_snappyHexMesh_location(self, bounds, custom_location=None):
        """
        Updates locationInMesh in system/snappyHexMeshDict to be inside the fluid domain.
        If custom_location is provided (tuple/list of x,y,z), it uses that.
        Otherwise, assumes fluid is an annulus/void inside a tube.
        """
        if custom_location:
            location = f"({custom_location[0]:.3f} {custom_location[1]:.3f} {custom_location[2]:.3f})"
        else:
            if bounds is None or bounds[0] is None:
                return

            min_pt, max_pt = bounds

            # Calculate a safe point.
            # We assume the geometry is centered at (0,0,Z).
            # We want a point at radius ~80% of the bounds.
            # max_pt[0] is roughly the radius.

            x_target = max_pt[0] * 0.8

            # Ensure it's not too small (e.g. if bounds are tiny)
            if x_target < 2.0:
                x_target = 5.0

            location = f"({x_target:.3f} 0 0)"

        shm_path = os.path.join(self.case_dir, "system", "snappyHexMeshDict")
        if not os.path.exists(shm_path):
            return

        with open(shm_path, 'r') as f:
            content = f.read()

        # Regex to find locationInMesh (x y z);
        pattern = re.compile(r"locationInMesh\s+\(.*\);")
        if pattern.search(content):
            content = pattern.sub(f"locationInMesh {location};", content)

        with open(shm_path, 'w') as f:
            f.write(content)

    def _check_boundary_patches(self):
        """
        Checks if inlet and outlet patches exist and have faces.
        Returns True if valid, False otherwise.
        """
        boundary_file = os.path.join(self.case_dir, "constant", "polyMesh", "boundary")
        if not os.path.exists(boundary_file):
            print("Error: polyMesh/boundary file not found.")
            return False

        with open(boundary_file, 'r') as f:
            content = f.read()

        for patch in ["inlet", "outlet"]:
            # Match: patch_name { ... nFaces X; ... }
            # Use DOTALL to match across lines
            # Pattern: patch \s* \{ .*? nFaces \s+ (\d+) ;
            pattern = re.compile(rf"{patch}\s*\{{.*?nFaces\s+(\d+);", re.DOTALL)
            match = pattern.search(content)
            if not match:
                # OpenFOAM sometimes quotes patch names in boundary file
                pattern_quoted = re.compile(rf'"{patch}"\s*\{{.*?nFaces\s+(\d+);', re.DOTALL)
                match = pattern_quoted.search(content)

            if not match:
                print(f"Error: Patch '{patch}' not found in boundary file.")
                return False

            n_faces = int(match.group(1))
            if n_faces <= 0:
                print(f"Error: Patch '{patch}' has 0 faces.")
                return False

        return True

    def run_meshing(self, log_file=None):
        """
        Runs the meshing pipeline.
        """
        # Ensure we capture output
        cmds = [
            ["blockMesh"],
            ["surfaceFeatureExtract"],
            ["snappyHexMesh", "-overwrite"],
            ["checkMesh"]
        ]

        for cmd in cmds:
            # Pass command name as description
            if not self.run_command(cmd, log_file=log_file, description=f"Meshing ({cmd[0]})"):
                return False

        # Post-meshing verification
        if not self._check_boundary_patches():
            print("Meshing failed verification: missing or empty inlet/outlet patches.")
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
        if not self.has_tools:
            if not log_file:
                print(f"Skipping command {' '.join(cmd)} (no OpenFOAM/Container tools found).")
            return False

        final_cmd = cmd
        if self.use_container:
            # Wrap in container call
            final_cmd = self._get_container_command(cmd, self.case_dir)
            # When using container, we are effectively running "container_tool" as the command

        # Use passed log_file or fallback to self.log_file
        target_log = log_file if log_file else self.log_file

        if not log_file:
            print(f"Running {' '.join(final_cmd)}...")

        try:
            cwd = self.case_dir if not self.use_container else os.getcwd()

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
            else:
                # Print tail of log file
                if os.path.exists(target_log):
                    print(f"\n--- Log tail for failed command: {' '.join(cmd)} ---")
                    try:
                        with open(target_log, 'r') as f:
                            lines = f.readlines()
                            for line in lines[-50:]:
                                print(line, end='')
                    except Exception as e:
                        print(f"Error reading log file: {e}")
                    print("----------------------------------------------------\n")

            if cmd[0] == "blockMesh":
                print("Hint: If blockMesh failed with no error message, it likely ran out of memory. The mesh resolution has been automatically adjusted, but try reducing mesh resolution further if the error persists.")

            if not ignore_error:
                return False
            return True
        except FileNotFoundError:
            if self.use_container:
                print(f"Error: '{self.container_tool}' executable not found.")
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

            # 4. Try to parse explicit Parcel fate table (more accurate)
            escaped_parcels = 0
            stuck_parcels = 0
            found_fate_table = False

            with open(target_log, 'r') as f:
                content = f.read()
                # Look for "Parcel fate (number, mass)" block
                if "Parcel fate" in content:
                    # Regex for escape and stick counts
                    # Pattern: - escape      : 123, ...
                    escape_match = re.search(r"\s*-\s+escape\s+:\s+(\d+)", content)
                    stick_match = re.search(r"\s*-\s+stick\s+:\s+(\d+)", content)

                    if escape_match:
                        escaped_parcels = int(escape_match.group(1))
                        found_fate_table = True
                    if stick_match:
                        stuck_parcels = int(stick_match.group(1))
                        found_fate_table = True

            if total_injected > 0:
                if found_fate_table:
                    # Use explicit fate counts
                    # Captured = Stuck + (Current - Escaped? No, Current is remaining in domain)
                    # Actually, if the simulation finished, Current should be small/zero if everything settled.
                    # But if we treat 'stuck' as captured (on bin walls) and 'escape' as lost.

                    # Separation Efficiency = 1 - (Escaped / Injected)
                    metrics['separation_efficiency'] = (1.0 - (escaped_parcels / total_injected)) * 100.0
                    metrics['particles_injected'] = total_injected
                    metrics['particles_captured'] = stuck_parcels # Explicitly stuck
                    metrics['particles_escaped'] = escaped_parcels
                    metrics['particles_remaining'] = current_parcels # Suspended in flow

                    # Total captured could be interpreted as Stuck + Remaining (if remaining are in bin)
                    # For now, let's report strict "Stuck" as captured, unless the user considers residence as capture.
                    # The user said "measure ... total particulate that gets captured in the volume".
                    # So 'current' particles might be captured.
                    # Let's add a combined metric.
                    metrics['total_retained'] = stuck_parcels + current_parcels

                else:
                    # Fallback to legacy logic (Efficiency = Remaining / Injected)
                    # This assumes all non-remaining particles escaped.
                    metrics['separation_efficiency'] = (current_parcels / total_injected) * 100.0
                    metrics['particles_injected'] = total_injected
                    metrics['particles_captured'] = current_parcels
                    metrics['note'] = "Using legacy tracking (implicit escape)"

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
