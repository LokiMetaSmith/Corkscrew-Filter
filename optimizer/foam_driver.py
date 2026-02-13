import os
import shutil
import subprocess
import glob
import re
import math
import sys
import contextlib
import numpy as np
from utils import run_command_with_spinner

class FoamDriver:
    def __init__(self, case_dir, template_dir=None, container_engine="auto", num_processors=1, verbose=False):
        self.case_dir = os.path.abspath(case_dir)
        self.template_dir = os.path.abspath(template_dir) if template_dir else self.case_dir
        self.log_file = os.path.join(self.case_dir, "run_foam.log")
        self.docker_image = os.environ.get("OPENFOAM_IMAGE", "opencfd/openfoam-default:2406")
        self.has_tools = False
        self.container_tool = None
        self.use_container = False
        self.container_engine = container_engine
        self.num_processors = num_processors
        self.verbose = verbose

        # Attempt to recover from previous crashes (if any)
        self._recover_from_crash()

        self._check_execution_environment()

    def _recover_from_crash(self):
        """
        Checks for .bak files indicating a previous crash and restores them.
        """
        files = ["system/controlDict", "system/fvSchemes", "constant/kinematicCloudProperties"]
        restored = []
        for f in files:
            src = os.path.join(self.case_dir, f)
            bak = src + ".bak"
            if os.path.exists(bak):
                try:
                    shutil.copy2(bak, src)
                    os.remove(bak)
                    restored.append(f)
                except Exception as e:
                    print(f"Warning: Failed to recover {f} from backup: {e}")

        if restored:
            print(f"Recovered from previous crash. Restored: {', '.join(restored)}")

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

    def run_command(self, cmd, log_file=None, description="Processing", ignore_error=False):
        """
        Executes a command, optionally wrapping it in a container.
        """
        if self.use_container:
            # When using container, we need to adjust the command
            # The _get_container_command method expects the cmd list and cwd
            # We use self.case_dir as the cwd for the command inside the container
            full_cmd = self._get_container_command(cmd, self.case_dir)
            cwd = None  # Run container tool from wherever, it handles mounting
        else:
            full_cmd = cmd
            cwd = self.case_dir

        target_log = log_file if log_file else self.log_file

        try:
            run_command_with_spinner(
                full_cmd,
                target_log,
                cwd=cwd,
                description=description
            )
            return True

        except subprocess.CalledProcessError as e:
            if not ignore_error:
                print(f"\nError executing {' '.join(cmd)}: {e}")
                if self.verbose:
                    self._print_log_tail(target_log)
                return False
            return False
        except Exception as e:
            if not ignore_error:
                print(f"\nUnexpected error executing {' '.join(cmd)}: {e}")
                if self.verbose:
                    self._print_log_tail(target_log)
                return False
            return False

    def _print_log_tail(self, log_file, lines=30):
        """Prints the last N lines of the log file to stdout."""
        if not log_file or not os.path.exists(log_file):
            print(f"(Log file {log_file} not found)")
            return

        print(f"\n--- Error Log Tail ({os.path.basename(log_file)}) ---")
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                # Efficiently read last N lines?
                # For small logs, reading all lines is fine.
                # If logs are huge, we might want to seek.
                # Assuming reasonable log size for this project.
                all_lines = f.readlines()
                tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
                for line in tail:
                    print(line.rstrip())
        except Exception as e:
            print(f"Error reading log: {e}")
        print("--------------------------------------------------\n")

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

        # Setup Physics (Turbulence)
        self._generate_turbulenceProperties()
        self._generate_omega_field() # Required for kOmegaSST

        # Add function objects to controlDict if not present
        self._inject_function_objects()

    def _generate_decomposeParDict(self):
        """
        Generates system/decomposeParDict for parallel execution.
        """
        content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    object      decomposeParDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

numberOfSubdomains {self.num_processors};

method          scotch;

// ************************************************************************* //
"""
        with open(os.path.join(self.case_dir, "system", "decomposeParDict"), 'w') as f:
            f.write(content)

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

    def update_snappyHexMesh_location(self, bounds, custom_location=None, helix_path_radius_mm=None):
        """
        Updates locationInMesh in system/snappyHexMeshDict to be inside the fluid domain.
        If custom_location is provided (tuple/list of x,y,z), it uses that.
        Otherwise, if helix_path_radius_mm is provided, uses analytic center of channel.
        Otherwise, falls back to heuristic based on bounds.
        """
        if custom_location:
            location = f"({custom_location[0]:.3f} {custom_location[1]:.3f} {custom_location[2]:.3f})"
        elif helix_path_radius_mm is not None:
            # Analytic fallback: Use helix path radius (scaled to m)
            # The helix center at Z=0 is at (R, 0, 0) relative to axis?
            # Actually helix path is helical. At Z=0 (if it starts there), angle might be 0.
            # Assuming helix starts at angle 0, X=R.
            try:
                r_m = float(helix_path_radius_mm) * 0.001
                # Use a slightly offset point to be safe inside the channel, but R should be center.
                # Just use R.
                location = f"({r_m:.4f} 0 0)"
                print(f"Using analytic locationInMesh: {location}")
            except (ValueError, TypeError):
                # Fallback to bounds if conversion fails
                location = None
        else:
            location = None

        if location is None:
            # Legacy fallback
            if bounds is None or bounds[0] is None:
                return

            min_pt, max_pt = bounds

            # Calculate a safe point.
            # We assume the geometry is centered at (0,0,Z).
            # We want a point at radius ~80% of the bounds.
            # max_pt[0] is roughly the radius.

            x_target = max_pt[0] * 0.8

            # Ensure it's not too small (e.g. if bounds are tiny)
            if x_target < 0.002: # 2mm
                 x_target = 0.005 # 5mm

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

    def _generate_turbulenceProperties(self):
        """
        Generates constant/turbulenceProperties with kOmegaSST model.
        """
        content = """/*--------------------------------*- C++ -*----------------------------------*\\
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
    location    "constant";
    object      turbulenceProperties;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

simulationType  RAS;

RAS
{
    model           kOmegaSST;

    turbulence      on;

    printCoeffs     on;
}

// ************************************************************************* //
"""
        with open(os.path.join(self.case_dir, "constant", "turbulenceProperties"), 'w') as f:
            f.write(content)

    def _generate_omega_field(self):
        """
        Generates 0/omega field required for kOmegaSST.
        """
        # Omega ~ Epsilon / (k * Cmu) ~ 14.8 / (0.09375 * 0.09) ~ 1750?
        # Standard wall function setup.
        content = """/*--------------------------------*- C++ -*----------------------------------*\\
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
    class       volScalarField;
    object      omega;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 0 -1 0 0 0 0];

internalField   uniform 150;

boundaryField
{
    inlet
    {
        type            turbulentMixingLengthFrequencyInlet;
        mixingLength    0.007;
        value           uniform 150;
    }

    outlet
    {
        type            zeroGradient;
    }

    walls
    {
        type            omegaWallFunction;
        value           uniform 150;
    }

    corkscrew
    {
        type            omegaWallFunction;
        value           uniform 150;
    }
}

// ************************************************************************* //
"""
        with open(os.path.join(self.case_dir, "0", "omega"), 'w') as f:
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

    def _generate_topoSetDict(self, bin_config=None):
        """
        Generates system/topoSetDict.
        If bin_config is provided ({'num_bins': int, 'total_length': float}), it generates
        bin-specific face sets.
        """
        bin_actions = ""
        if bin_config and bin_config.get("num_bins", 1) > 1:
            num_bins = int(bin_config["num_bins"])
            length = float(bin_config.get("insert_length_mm", 50.0))
            # Convert to meters if needed? Usually snappyHexMesh works in scaled units if scaled.
            # BUT the mesh is scaled to meters (x0.001) in simulation_runner logic before foam is run?
            # Wait, simulation_runner scales the STL. `snappyHexMesh` uses the STL dimensions.
            # So the mesh inside OpenFOAM is in Meters.
            # `length` passed here is likely in mm (from params). We must scale it.
            scale = 0.001

            # Geometry is centered at Z=0.
            # Range: [-L/2, L/2]
            z_start = -(length * scale) / 2.0
            bin_h = (length * scale) / num_bins

            for i in range(num_bins):
                z_min = z_start + i * bin_h
                z_max = z_start + (i + 1) * bin_h

                bin_actions += f"""
    // Bin {i+1}
    {{
        name    bin_{i+1}_faces;
        type    faceSet;
        action  new;
        source  boxToFace;
        box     (-100 -100 {z_min:.5f}) (100 100 {z_max:.5f}); // Large box in X/Y
    }}
    {{
        name    bin_{i+1}_faces;
        type    faceSet;
        action  subset;
        source  faceToFace;
        set     corkscrewFaces;
    }}
"""

        content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    // 1. Select all faces in 'corkscrew' patch (if it exists) or all boundary faces
    // Since snappyHexMesh puts everything in 'corkscrew' (from STL name), start with that.
    {{
        name    corkscrewFaces;
        type    faceSet;
        action  new;
        source  patchToFace;
        patch   corkscrew;
    }}

    // 2. Select Inlet Faces (Bottom, Normal 0 0 -1)
    {{
        name    inletFaces;
        type    faceSet;
        action  new;
        source  normalToFace;
        normal  (0 0 -1);
        cos     0.8; // Tolerance (allow some deviation)
    }}
    // Intersect with corkscrew boundary faces
    {{
        name    inletFaces;
        type    faceSet;
        action  subset;
        source  faceToFace;
        set     corkscrewFaces;
    }}

    // 3. Select Outlet Faces (Top, Normal 0 0 1)
    {{
        name    outletFaces;
        type    faceSet;
        action  new;
        source  normalToFace;
        normal  (0 0 1);
        cos     0.8;
    }}
    {{
        name    outletFaces;
        type    faceSet;
        action  subset;
        source  faceToFace;
        set     corkscrewFaces;
    }}

    // 4. Bin Split Actions
    {bin_actions}
);

// ************************************************************************* //
"""
        with open(os.path.join(self.case_dir, "system", "topoSetDict"), 'w') as f:
            f.write(content)

    def _generate_createPatchDict(self, bin_config=None):
        """
        Generates system/createPatchDict.
        """
        bin_patches = ""
        if bin_config and bin_config.get("num_bins", 1) > 1:
            num_bins = int(bin_config["num_bins"])
            for i in range(num_bins):
                bin_patches += f"""
    {{
        name bin_{i+1};
        patchInfo
        {{
            type patch;
            inGroups (corkscrew_bins);
        }}
        constructFrom set;
        set bin_{i+1}_faces;
    }}"""

        content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    object      createPatchDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

pointSync false;

patches
(
    {{
        name inlet;
        patchInfo
        {{
            type patch;
            inGroups (inlet);
        }}
        constructFrom set;
        set inletFaces;
    }}
    {{
        name outlet;
        patchInfo
        {{
            type patch;
            inGroups (outlet);
        }}
        constructFrom set;
        set outletFaces;
    }}
    {bin_patches}
);

// ************************************************************************* //
"""
        with open(os.path.join(self.case_dir, "system", "createPatchDict"), 'w') as f:
            f.write(content)

    def _generate_kinematicCloudProperties(self, bin_config=None):
        """
        Generates constant/kinematicCloudProperties with size binning and spatial binning.
        """
        # Sizes to simulate (in meters)
        sizes_um = [5, 10, 20, 50, 100]

        injections = ""
        for d_um in sizes_um:
            d_m = d_um * 1e-6
            # Use distinct model names for parsing
            model_name = f"model_{d_um}um"

            injections += f"""
        {model_name}
        {{
            type            patchInjection;
            patch           inlet;
            parcelBasisType number;
            parcelsPerSecond 5000; // Total ~25000/s across 5 bins
            duration        1;
            SOI             0;
            nParticle       1;
            massFlowRate    2e-6; // Approximate
            flowRateProfile constant 1;
            U0              (0 0 5);
            sizeDistribution
            {{
                type        fixedValue;
                fixedValueDistribution
                {{
                    value   {d_m};
                }}
            }}
        }}"""

        # Patch Interaction
        patch_interactions = """
            corkscrew
            {
                type stick;
            }
            outlet
            {
                type escape;
            }
            inlet
            {
                type escape;
            }"""

        patch_list_str = "corkscrew inlet outlet"

        if bin_config and bin_config.get("num_bins", 1) > 1:
            num_bins = int(bin_config["num_bins"])
            patch_interactions = """
            corkscrew
            {
                type stick;
            }""" # Keep main wall just in case parts remain

            patch_list_str = "corkscrew inlet outlet"

            for i in range(num_bins):
                patch_interactions += f"""
            bin_{i+1}
            {{
                type stick;
            }}"""
                patch_list_str += f" bin_{i+1}"

            patch_interactions += """
            outlet
            {
                type escape;
            }
            inlet
            {
                type escape;
            }"""

        content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    location    "constant";
    object      kinematicCloudProperties;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solution
{{
    active          true;
    coupled         false; // One-way coupling
    transient       yes;
    maxTrackTime    10.0;
    calcFrequency   1;
    cellValueSourceCorrection off;

    interpolationSchemes
    {{
        rho             cell;
        U               cell;     // Use cell center values for robustness
        mu              cell;
    }}

    integrationSchemes
    {{
        U               Euler;
    }}

    sourceTerms
    {{
        schemes
        {{
            U               explicit 1;
        }}
    }}
}}

constantVolume      false;

// Moon Dust Properties (Basaltic Regolith)
rho0            3100; // kg/m^3 (approx. 3.1 g/cm^3)

// Young's Modulus: ~70 GPa (Basalt)
// Poisson's Ratio: 0.25 (Basalt)
// Restitution Coefficient: ~0.8-0.9

subModels
{{
    particleForces
    {{
        sphereDrag;
        gravity;
    }}

    collisionModel none;
    // For dilute flows, stochastic collisions are negligible.
    // If enabled, use: stochasticCollision; with coefficients for Basalt.
    stochasticCollisionModel none;

    injectionModels
    {{
        {injections}
    }}

    dispersionModel none;

    patchInteractionModel localInteraction;

    localInteractionCoeffs
    {{
        patches
        (
            {patch_interactions}
        );
    }}

    surfaceFilmModel none;
}}

cloudFunctions
{{
    patchPostProcessing1
    {{
        type            patchPostProcessing;
        maxStoredParcels 20;
        patches         ( {patch_list_str} );
        writeControl    writeTime;
        writeInterval   1;
    }}
}}

// ************************************************************************* //
"""
        with open(os.path.join(self.case_dir, "constant", "kinematicCloudProperties"), 'w') as f:
            f.write(content)

    def scale_mesh(self, stl_filename="corkscrew_fluid.stl", scale_factor=0.001):
        """
        Scales the STL mesh using surfaceMeshConvert.
        Crucially converts Windows paths to Linux paths for the container.
        """
        # Construct the relative path
        # FORCE forward slashes for Linux container compatibility
        stl_rel_path = f"constant/triSurface/{stl_filename}"

        # Command: surfaceMeshConvert input output -scale factor
        cmd = ["surfaceMeshConvert", stl_rel_path, stl_rel_path, "-scale", str(scale_factor)]

        return self.run_command(cmd, description="Scaling Mesh (mm -> m)")

    def run_meshing(self, log_file=None, bin_config=None, stl_filename="corkscrew_fluid.stl"):
        """
        Runs the meshing pipeline.
        bin_config: {'num_bins': int, 'total_length': float (mm)}
        """
        # Step 0: Scale STL (Fix for "Scale of the Giants")
        # We assume the STL is already in constant/triSurface/
        if not self.scale_mesh(stl_filename, scale_factor=0.001):
             print("Error: Failed to scale mesh.")
             return False

        # Generate patch creation configs
        self._generate_topoSetDict(bin_config)
        self._generate_createPatchDict(bin_config)

        # Ensure we capture output
        # Step 1: Base Mesh
        if not self.run_command(["blockMesh"], log_file=log_file, description="Meshing (blockMesh)"): return False
        if not self.run_command(["surfaceFeatureExtract"], log_file=log_file, description="Meshing (surfaceFeatureExtract)"): return False
        if not self.run_command(["snappyHexMesh", "-overwrite"], log_file=log_file, description="Meshing (snappyHexMesh)"): return False

        # Step 2: Create Patches
        if not self.run_command(["topoSet"], log_file=log_file, description="Meshing (topoSet)"): return False
        if not self.run_command(["createPatch", "-overwrite"], log_file=log_file, description="Meshing (createPatch)"): return False

        # Step 3: Check
        if not self.run_command(["checkMesh"], log_file=log_file, description="Meshing (checkMesh)"): return False

        # Post-meshing verification
        if not self._check_boundary_patches():
            print("Meshing failed verification: missing or empty inlet/outlet patches.")
            return False

        return True

    def run_solver(self, log_file=None):
        """
        Runs the solver.
        """
        if self.num_processors > 1:
            self._generate_decomposeParDict()

            # 1. Decompose
            if not self.run_command(["decomposePar", "-force"], log_file=log_file, description="Decomposing Domain"): return False

            # 2. Run Parallel
            # Note: mpirun might be named differently (e.g. mpiexec). OpenFOAM containers usually have mpirun.
            cmd = ["mpirun", "-np", str(self.num_processors), "simpleFoam", "-parallel"]

            if not self.run_command(cmd, log_file=log_file, description=f"Solving CFD (Parallel {self.num_processors} CPUs)"): return False

            # 3. Reconstruct
            # Reconstruct latest time for particle tracking and visualization
            if not self.run_command(["reconstructPar", "-latestTime"], log_file=log_file, description="Reconstructing Domain"): return False

            return True
        else:
            return self.run_command(["simpleFoam"], log_file=log_file, description="Solving CFD")

    def _create_constant_field(self, time_dir, field_name, value, dimensions, class_type="volScalarField", boundary_type="fixedValue"):
        """
        Creates a uniform field file in the specified time directory.
        Used to create 'rho' and 'mu' for particle tracking.
        """
        header = f"""/*--------------------------------*- C++ -*----------------------------------*\\
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
    class       {class_type};
    location    "{time_dir}";
    object      {field_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      {dimensions};

internalField   uniform {value};

boundaryField
{{
    ".*"
    {{
        type            {boundary_type};
        value           uniform {value};
    }}
}}

// ************************************************************************* //
"""
        file_path = os.path.join(self.case_dir, str(time_dir), field_name)
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w') as f:
            f.write(header)

    def _generate_particle_tracking_fields(self, time_dir, fallback_dirs=None):
        """
        Generates missing fields (rho, mu) required for kinematicCloud.
        Optionally generates them in fallback_dirs (list of time dirs) as well.
        """
        # 1. Get properties from transportProperties if available, else defaults
        rho_val = 1.2
        nu_val = 1.48e-5

        tp_path = os.path.join(self.case_dir, "constant", "transportProperties")
        if os.path.exists(tp_path):
            try:
                with open(tp_path, 'r') as f:
                    content = f.read()
                    # Parse rhoInf
                    m_rho = re.search(r"rhoInf\s+.*?([\d\.e\-\+]+);", content)
                    if m_rho:
                        rho_val = float(m_rho.group(1))

                    # Parse nu (kinematic viscosity)
                    m_nu = re.search(r"nu\s+.*?([\d\.e\-\+]+);", content)
                    if m_nu:
                        nu_val = float(m_nu.group(1))
            except Exception as e:
                print(f"Warning: Failed to parse transportProperties: {e}. Using defaults.")

        mu_val = rho_val * nu_val

        target_dirs = [str(time_dir)]
        if fallback_dirs:
            target_dirs.extend([str(d) for d in fallback_dirs])

        print(f"Generating particle tracking fields (rho={rho_val}, mu={mu_val:.3e}) in: {', '.join(target_dirs)}")

        for t_dir in target_dirs:
            # 2. Create rho (Density) [1 -3 0 0 0 0 0]
            self._create_constant_field(t_dir, "rho", rho_val, "[1 -3 0 0 0 0 0]", boundary_type="fixedValue")

            # 3. Create mu (Dynamic Viscosity) [1 -1 -1 0 0 0 0]
            self._create_constant_field(t_dir, "mu", mu_val, "[1 -1 -1 0 0 0 0]", boundary_type="fixedValue")

    @contextlib.contextmanager
    def _backup_restore_config(self):
        """
        Context manager to backup and restore system configuration files.
        """
        files = ["system/controlDict", "system/fvSchemes", "constant/kinematicCloudProperties"]
        backups = {}

        try:
            # Backup
            for f in files:
                src = os.path.join(self.case_dir, f)
                if os.path.exists(src):
                    dst = src + ".bak"
                    try:
                        shutil.copy2(src, dst)
                        backups[src] = dst
                    except Exception as e:
                        print(f"Warning: Failed to backup {f}: {e}")
            yield
        finally:
            # Restore
            for src, dst in backups.items():
                if os.path.exists(dst):
                    try:
                        # Use copy + remove to better handle Windows file locking
                        if os.path.exists(src):
                            os.remove(src) # Try to remove original first
                        shutil.copy2(dst, src)
                        os.remove(dst)
                    except Exception as e:
                         print(f"Error restoring {src}: {e}. You may need to manually recover from {dst}.")

    def _switch_fvSchemes_to_transient(self):
        """
        Switches ddtSchemes to Euler for transient particle tracking.
        """
        fvSchemes = os.path.join(self.case_dir, "system", "fvSchemes")
        if not os.path.exists(fvSchemes): return

        with open(fvSchemes, 'r') as f:
            content = f.read()

        # Replace ddtSchemes
        # ddtSchemes { default steadyState; } -> ddtSchemes { default Euler; }
        pattern = re.compile(r"ddtSchemes\s*\{[^\}]*\}", re.DOTALL)
        if pattern.search(content):
            content = pattern.sub("ddtSchemes\n    {\n        default         Euler;\n    }", content)

        with open(fvSchemes, 'w') as f:
            f.write(content)

    def _prepare_transient_run(self, source_time):
        """
        Resets the simulation to time 0, copies fields from source_time, and generates rho/mu.
        """
        zero_dir = os.path.join(self.case_dir, "0")
        source_dir = os.path.join(self.case_dir, str(source_time))

        # 1. Clean 0 directory (but keep mesh files if present, though usually they are in constant/polyMesh)
        # We overwrite 0 with new fields.
        if os.path.exists(zero_dir):
            shutil.rmtree(zero_dir)
        os.makedirs(zero_dir)

        # 2. Copy fields
        fields_to_copy = ["U", "p", "phi", "k", "epsilon", "omega", "nut"]
        for field in fields_to_copy:
            src = os.path.join(source_dir, field)
            dst = os.path.join(zero_dir, field)
            if os.path.exists(src):
                shutil.copy2(src, dst)
            elif field == "phi":
                 print("Warning: 'phi' field missing in source time. Solver might fail.")

        # 3. Generate rho and mu (in both 0 and source_time for robustness)
        self._generate_particle_tracking_fields("0", fallback_dirs=[source_time])

    def _update_controlDict_for_particles(self):
        """
        Updates controlDict for particle tracking (Reset Time Strategy):
        - startFrom startTime
        - startTime 0
        - endTime 10.0
        - deltaT 0.001
        """
        control_dict = os.path.join(self.case_dir, "system", "controlDict")
        if not os.path.exists(control_dict):
            return

        with open(control_dict, 'r') as f:
            content = f.read()

        # Update application
        if "application" in content:
            content = re.sub(r"application\s+.*?;", "application icoUncoupledKinematicParcelFoam;", content)

        # Update startFrom
        if "startFrom" in content:
            content = re.sub(r"startFrom\s+.*?;", "startFrom startTime;", content)

        # Update startTime
        if "startTime" in content:
            content = re.sub(r"startTime\s+.*?;", "startTime 0;", content)

        # Update endTime (10s sufficient for particles to exit)
        if "stopAt" in content:
            content = re.sub(r"stopAt\s+.*?;", "stopAt endTime;", content)

        if "endTime" in content:
            content = re.sub(r"endTime\s+.*?;", "endTime 10.0;", content)

        # Update deltaT (1ms)
        if "deltaT" in content:
            content = re.sub(r"deltaT\s+.*?;", "deltaT 0.001;", content)

        # Update writeInterval
        if "writeInterval" in content:
            content = re.sub(r"writeInterval\s+.*?;", "writeInterval 100;", content) # Write every 0.1s

        # Disable function objects
        # Robustly replace only if it looks like a block, and not already disabled
        if "functions" in content and "functions_disabled" not in content:
             # Look for "functions" at start of line or after newline
             content = re.sub(r"(^|\n)functions(\s*\{)", r"\1functions_disabled\2", content)

        with open(control_dict, 'w') as f:
            f.write(content)

    def run_particle_tracking(self, log_file=None, bin_config=None):
        """
        Runs particle tracking (Lagrangian) using a robust transient strategy on frozen flow.
        """
        # Find latest steady-state time directory
        dirs = [d for d in os.listdir(self.case_dir) if os.path.isdir(os.path.join(self.case_dir, d)) and d.replace('.', '', 1).isdigit()]

        if not dirs:
            print("Error: No time directories found for particle tracking.")
            return False

        try:
            latest_time = max(dirs, key=float)
        except ValueError:
            latest_time = dirs[-1]

        # Use context manager to backup/restore configs
        with self._backup_restore_config():
            print(f"Preparing particle tracking from steady state time {latest_time}...")

            # 1. Generate Cloud Config
            self._generate_kinematicCloudProperties(bin_config)

            # Debug: print generated cloud config
            c_path = os.path.join(self.case_dir, "constant", "kinematicCloudProperties")
            if os.path.exists(c_path):
                 with open(c_path, 'r') as f:
                     print(f"--- Generated kinematicCloudProperties ---\n{f.read()}\n----------------------------------------")

            # 2. Reset Time & Prepare Fields
            self._prepare_transient_run(latest_time)

            # 3. Update Configurations
            self._update_controlDict_for_particles()
            self._switch_fvSchemes_to_transient()

            # 4. Run Solver
            return self.run_command(["icoUncoupledKinematicParcelFoam"], log_file=log_file, description="Particle Tracking")

    def generate_vtk(self):
        """
        Runs foamToVTK to generate VTK files for visualization.
        Returns the path to the VTK directory if successful, None otherwise.
        """
        print("Generating VTK artifacts...")
        # foamToVTK -latestTime is usually enough for snapshot,
        # but user might want animation. Let's do all times if valid?
        # "incorporate viewing the most successful runs".
        # Let's stick to -latestTime to save space/time, unless requested.
        # But for particle tracks (Lagrangian), we might want the full path.
        # The Lagrangian data is time-dependent.
        # We should run foamToVTK without -latestTime to capture the particle tracks.

        # NOTE: foamToVTK usually exports all times by default.
        if self.run_command(["foamToVTK"], description="Generating VTK"):
            vtk_dir = os.path.join(self.case_dir, "VTK")
            if os.path.exists(vtk_dir):
                return vtk_dir
        return None

    def get_metrics(self, log_file=None):
        """
        Parses logs to get metrics.
        Returns dict: {'delta_p': float, 'residuals': float, 'particle_data': ...}
        """
        metrics = {
            'delta_p': None,
            'residuals': None,
            'capture_by_bin': {},
            'injected_by_model': {}
        }

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

        # 3. Parse Particle Tracking (Detailed)
        if os.path.exists(target_log):
            with open(target_log, 'r') as f:
                content = f.read()

            # -- Parse Efficiency Per Size (Injection Model) --
            # Look for "Injector model_Xum: injected Y parcels... escape : A, stick : B"
            # The log format for final stats usually groups by injector if multiple exist?
            # Or it reports global "Parcel fate" and then maybe detailed?
            # Standard OpenFOAM "Parcel fate" table sums everything.
            # However, during run, it logs "Injector model_5um: injected X parcels".
            # To get *efficiency* per model, we need to know how many from *that* model escaped/stuck.
            # Standard logs might NOT break down fate by injector model unless configured.
            # But wait, if we inject different sizes, can we differentiate them in the fate table?
            # No, the fate table is usually global type-based.

            # Fallback/Workaround:
            # If standard logs don't give per-model fate, we can only report global efficiency
            # UNLESS we use "cloud functions" or parse the explicit injection log lines
            # and assume all "stuck" are captured? No.

            # Actually, newer OpenFOAM might report it.
            # If not, we simply report global for now, but we set up the structure.
            # Let's try to parse "Injector <name>: ... injected <N>"
            # And then look for "Cloud: kinematicCloud ... "

            # Let's parse the global table first.
            global_injected = 0
            global_escaped = 0
            global_stuck = 0

            if "Parcel fate" in content:
                # Regex for escape and stick counts
                # Pattern: - escape      : 123, ...
                escape_match = re.search(r"\s*-\s+escape\s+:\s+(\d+)", content)
                stick_match = re.search(r"\s*-\s+stick\s+:\s+(\d+)", content)

                if escape_match:
                    global_escaped = int(escape_match.group(1))
                if stick_match:
                    global_stuck = int(stick_match.group(1))

            # Parse total injected per model
            # Pattern: "Injector model_(\d+)um: injected (\d+) parcels"
            # We need the FINAL count.
            injection_counts = {}
            # Regex to match all occurrences and take the last one or sum?
            # Usually "injected" accumulates or reports final.
            # "Injector model1: injected 100 parcels" appears at each step. We want the MAX.
            for m in re.finditer(r"Injector (model_[\d]+um): injected (\d+) parcels", content):
                model = m.group(1)
                count = int(m.group(2))
                # Store max seen for this model
                if count > injection_counts.get(model, 0):
                    injection_counts[model] = count

            # Add breakdown to metrics
            metrics['injected_by_model'] = injection_counts

            # If we can't get per-model fate, we distribute global efficiency? No that's wrong.
            # For now, let's store the injection counts.
            # Use 'separation_efficiency' as global.
            total_injected_parsed = sum(injection_counts.values())

            if total_injected_parsed > 0:
                metrics['particles_injected'] = total_injected_parsed
                metrics['particles_captured'] = global_stuck
                metrics['particles_escaped'] = global_escaped
                metrics['separation_efficiency'] = (global_stuck / total_injected_parsed) * 100.0 if total_injected_parsed else 0
            else:
                 # Try finding total injected generic
                 m_total = re.findall(r"injected\s+(\d+)\s+parcels", content)
                 if m_total:
                     total_injected_parsed = sum(int(x) for x in m_total)
                     metrics['particles_injected'] = total_injected_parsed

            # -- Parse Spatial Capture (Bin Patches) --
            # Look for: "Patch bin_X: stick N" (if patchInteractionModel detail is enabled)
            # OpenFOAM usually reports:
            # "Interaction with patch bin_1: ... stick N"
            # Or in the table?
            # The standard table is by *Interaction Type* (escape, stick), not by Patch.

            # However, if we use `patchInteractionModel localInteraction`, it might log per patch?
            # Actually, `StandardWallInteraction` usually doesn't log per patch in the table.
            # But the `patchInteraction` function object does.
            # We haven't enabled `cloudFunctions` in the config yet.
            # To get per-patch stats, we really need the `patchInteractionFields` or similar function object.
            # OR we rely on the log if `debug` is on?

            # Let's Add `patchPostProcessing` function object to `cloudFunctions` in `_generate_kinematicCloudProperties`?
            # That's complicated to parse.

            # Alternative: Assume for now we only get global, but check log for any "Patch <name>" patterns.
            # Sometimes "Parcel fate" has a detailed table?
            # In v2406, it's usually compact.

            # Let's try to find ANY mention of "bin_" and numbers.
            # If not found, we leave the dict empty.

            # Try to parse `patchPostProcessing` file output if available
            # Path: case/postProcessing/lagrangian/cloud/patchPostProcessing1/*/patchPostProcessing.dat
            pp_base = os.path.join(self.case_dir, "postProcessing", "lagrangian", "cloud", "patchPostProcessing1")
            if os.path.exists(pp_base):
                 # Find latest time
                 time_dirs = glob.glob(os.path.join(pp_base, "*"))
                 if time_dirs:
                     latest_pp_dir = max(time_dirs, key=os.path.getmtime)
                     dat_file = os.path.join(latest_pp_dir, "patchPostProcessing1.dat")
                     if os.path.exists(dat_file):
                         # Format: # Time patch1 patch2 ...
                         # Data: time val1 val2 ...
                         try:
                             with open(dat_file, 'r') as f:
                                 lines = f.readlines()
                                 # Parse header to get patch names
                                 header = None
                                 for line in lines:
                                     if line.startswith("#") and "Time" in line:
                                         header = line.replace("#", "").split()
                                         break

                                 if header:
                                     # Get last data line
                                     last_line = lines[-1].strip()
                                     if last_line and not last_line.startswith("#"):
                                         data = last_line.split()
                                         # Map header to data
                                         # Header: Time patch1 patch2 ...
                                         # Data: time val1 val2 ...
                                         for i, col_name in enumerate(header):
                                             if col_name.startswith("bin_"):
                                                 try:
                                                     val = float(data[i])
                                                     metrics['capture_by_bin'][col_name] = val
                                                 except (IndexError, ValueError):
                                                     pass
                         except Exception as e:
                             print(f"Error parsing patchPostProcessing: {e}")

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
