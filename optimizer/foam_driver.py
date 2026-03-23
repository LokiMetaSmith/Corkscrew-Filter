import os
import shutil
import subprocess
import glob
import re
import math
import sys
import contextlib
import shlex
import numpy as np
import jinja2
from utils import run_command_with_spinner

class FoamDriver:
    def __init__(self, case_dir, config=None, template_dir=None, container_engine="auto", num_processors=1, verbose=False):
        self.case_dir = os.path.abspath(case_dir)
        self.config = config or {}
        self.template_dir = os.path.abspath(template_dir) if template_dir else self.case_dir
        self.log_file = os.path.join(self.case_dir, "run_foam.log")
        self.docker_image = os.environ.get("OPENFOAM_IMAGE", "opencfd/openfoam-default:2512")
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
            "/bin/bash", "-lc", f"cd {container_workdir} && " + shlex.join(cmd)
        ]

        return container_cmd

    def run_command(self, cmd, log_file=None, description="Processing", ignore_error=False, timeout=None):
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
                description=description,
                timeout=timeout
            )
            return True

        except subprocess.TimeoutExpired as e:
            if not ignore_error:
                print(f"\nTimeout executing {' '.join(cmd)} after {timeout} seconds.")
                self._print_log_tail(target_log)
                return False
            return False
        except subprocess.CalledProcessError as e:
            if not ignore_error:
                print(f"\nError executing {' '.join(cmd)}: {e}")
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

    def prepare_case(self, keep_mesh=False, bin_config=None, turbulence="laminar"):
        """
        Prepares the case directory.
        """
        if not keep_mesh and self.case_dir != self.template_dir:
            if os.path.exists(self.case_dir):
                shutil.rmtree(self.case_dir)
            shutil.copytree(self.template_dir, self.case_dir)

        # Dynamically set inlet velocity in 0.orig/U
        if bin_config:
            self._update_inlet_velocity(bin_config)

        tri_surface = os.path.join(self.case_dir, "constant", "triSurface")
        os.makedirs(tri_surface, exist_ok=True)

        # Ensure extendedFeatureEdgeMesh exists for surfaceFeatureExtract
        edge_mesh = os.path.join(self.case_dir, "constant", "extendedFeatureEdgeMesh")
        if os.path.exists(edge_mesh):
            shutil.rmtree(edge_mesh)
        os.makedirs(edge_mesh, exist_ok=True)

        # Clean previous results (numeric time directories and processors)
        for d in os.listdir(self.case_dir):
            path = os.path.join(self.case_dir, d)
            # Use float check to catch scientific notation like 1e-5
            try:
                is_numeric = False
                if d != "0":
                    float(d)
                    is_numeric = True
            except ValueError:
                is_numeric = False

            if os.path.isdir(path) and is_numeric:
                shutil.rmtree(path, ignore_errors=True)

        for p_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
            shutil.rmtree(p_dir, ignore_errors=True)

        # Ensure 0 folder
        zero_orig = os.path.join(self.case_dir, "0.orig")
        zero = os.path.join(self.case_dir, "0")
        if os.path.exists(zero_orig):
            if os.path.exists(zero):
                shutil.rmtree(zero)
            shutil.copytree(zero_orig, zero)

        # Setup Physics (Turbulence)
        # kOmegaSST fields (omega, k, nut, epsilon) are in 0.orig
        cfd_settings = self.config.get('cfd_settings', {})
        if cfd_settings and 'turbulence_model' in cfd_settings:
            turbulence = cfd_settings['turbulence_model']

        self._generate_turbulence_fields(zero, cfd_settings)
        self._apply_boundary_conditions(zero)
        self._update_turbulence_properties(turbulence)
        self._update_fvSchemes(turbulence)
        self._update_fvSolution(turbulence, cfd_settings)

        # Add function objects to controlDict if not present
        self._inject_function_objects()


    def _generate_turbulence_fields(self, zero_dir, cfd_settings):
        """
        Dynamically generates initial fields based on cfd_settings.
        """
        if not cfd_settings or 'initial_fields' not in cfd_settings:
            return

        initial_fields = cfd_settings['initial_fields']

        allowed_fields = list(initial_fields.keys()) + ["U", "p", "nut", "nuTilda"]
        for field_file in os.listdir(zero_dir):
            if os.path.isfile(os.path.join(zero_dir, field_file)) and field_file not in allowed_fields:
                os.remove(os.path.join(zero_dir, field_file))

        for field_name, field_config in initial_fields.items():
            field_path = os.path.join(zero_dir, field_name)

            internal_field = field_config.get('internalField', 'uniform 1e-7')
            wall_function = field_config.get('wallFunction', 'zeroGradient')

            # Procedural override: Never use zeroGradient for k or epsilon to prevent stochasticDispersionRAS SIGFPE
            if wall_function == "zeroGradient":
                if field_name == "epsilon":
                    wall_function = "epsilonWallFunction"
                    print("Procedurally overriding epsilon initial wall function from zeroGradient to epsilonWallFunction to prevent SIGFPE.")
                elif field_name == "k":
                    wall_function = "kqRWallFunction"
                    print("Procedurally overriding k initial wall function from zeroGradient to kqRWallFunction to prevent SIGFPE.")

            dimensions = "[0 2 -2 0 0 0 0]"
            if field_name == "epsilon":
                dimensions = "[0 2 -3 0 0 0 0]"
            elif field_name == "omega":
                dimensions = "[0 0 -1 0 0 0 0]"
            elif field_name == "nut":
                dimensions = "[0 2 -1 0 0 0 0]"

            header = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2512                                 |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       volScalarField;
    location    "0";
    object      {field_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      {dimensions};

internalField   {internal_field};

boundaryField
{{
"""

            physics = self.config.get('physics', {})
            boundaries = physics.get('boundaries', {})

            blocks = []

            for patch_name, patch_info in boundaries.items():
                patch_type = patch_info.get("type", "patch")
                if patch_type == "wall":
                    blocks.append(f"    {patch_name}\n    {{\n        type            {wall_function};\n        value           $internalField;\n    }}")
                elif "inlet" in patch_name.lower():
                    blocks.append(f"    {patch_name}\n    {{\n        type            fixedValue;\n        value           $internalField;\n    }}")
                else:
                    blocks.append(f"    {patch_name}\n    {{\n        type            zeroGradient;\n    }}")

            blocks_str = "\n".join(blocks)
            footer = "\n}\n"

            blocks_str += f"""
    ".*"
    {{
        type            zeroGradient;
    }}
"""

            with open(field_path, 'w') as f:
                f.write(header + blocks_str + footer)

    def _apply_boundary_conditions(self, zero_dir):
        """
        Applies dynamic boundary conditions from the YAML config to fields in 0.
        """
        physics = self.config.get('physics', {})
        boundaries = physics.get('boundaries', {})

        if not boundaries:
            return

        for field in os.listdir(zero_dir):
            file_path = os.path.join(zero_dir, field)
            if not os.path.isfile(file_path):
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            # Find the boundaryField block
            match = re.search(r'boundaryField\s*\{', content)
            if not match:
                continue

            start_idx = match.end()

            # Find the matching closing brace for boundaryField
            brace_level = 1
            end_idx = start_idx
            while brace_level > 0 and end_idx < len(content):
                if content[end_idx] == '{':
                    brace_level += 1
                elif content[end_idx] == '}':
                    brace_level -= 1
                end_idx += 1

            end_idx -= 1 # adjust to point to the closing brace

            if end_idx <= start_idx:
                continue

            inner_text = content[start_idx:end_idx]

            # Parse existing blocks
            blocks = {}
            tokens = re.finditer(r'([a-zA-Z0-9_"\.\*\-]+)|\{|\}', inner_text)
            brace_level = 0
            last_word = None
            current_name = None
            start = 0

            for m in tokens:
                val = m.group(0)
                if val == '{':
                    if brace_level == 0 and last_word:
                        current_name = last_word.strip('"')
                        start = m.end()
                    brace_level += 1
                elif val == '}':
                    brace_level -= 1
                    if brace_level == 0 and current_name:
                        blocks[current_name] = inner_text[start:m.start()].strip()
                        current_name = None
                else:
                    if brace_level == 0:
                        last_word = val

            # Modify/Add configured blocks
            for patch_name, patch_config in boundaries.items():
                new_block = ""
                # Check if specific field configuration is provided
                if field in patch_config:
                    field_val = patch_config[field]
                    if isinstance(field_val, str) and " " in field_val:
                        parts = field_val.split(maxsplit=1)
                        if len(parts) == 2:
                            new_block += f"type            {parts[0]};\n"
                            new_block += f"value           {parts[1]};\n"
                        else:
                            new_block += f"type            {field_val};\n"
                    else:
                        new_block += f"type            {field_val};\n"
                else:
                    # If the field isn't in patch_config, AND it's not already in the file, we add a fallback.
                    # If it IS already in the file, we DO NOT OVERWRITE it.
                    if patch_name in blocks:
                        continue

                    # Fallback defaults based on type
                    patch_type = patch_config.get('type')
                    if patch_type == 'wall':
                        if field == 'U':
                            new_block += "type            noSlip;\n"
                        elif field == 'p':
                            new_block += "type            zeroGradient;\n"
                        elif field in ['k', 'epsilon', 'omega', 'nut']:
                            # Should use calculated/zeroGradient if we don't know
                            new_block += "type            calculated;\nvalue           uniform 1e-7;\n"
                        else:
                            new_block += "type            calculated;\nvalue           uniform 0;\n"
                    else:
                        if field in ['U', 'p']:
                            new_block += "type            zeroGradient;\n"
                        elif field in ['k', 'epsilon', 'omega', 'nut']:
                            new_block += "type            calculated;\nvalue           uniform 1e-7;\n"
                        else:
                            new_block += "type            calculated;\nvalue           uniform 0;\n"

                # Procedural override: Never use zeroGradient for k or epsilon on walls to prevent stochasticDispersionRAS SIGFPE
                patch_type = patch_config.get('type')
                if patch_type == 'wall':
                    if field == "epsilon" and "type            zeroGradient;" in new_block:
                        new_block = new_block.replace("type            zeroGradient;", "type            epsilonWallFunction;\n        value           $internalField;")
                        print(f"Procedurally overriding epsilon boundary wall function from zeroGradient to epsilonWallFunction on {patch_name} to prevent SIGFPE.")
                    elif field == "k" and "type            zeroGradient;" in new_block:
                        new_block = new_block.replace("type            zeroGradient;", "type            kqRWallFunction;\n        value           $internalField;")
                        print(f"Procedurally overriding k boundary wall function from zeroGradient to kqRWallFunction on {patch_name} to prevent SIGFPE.")

                blocks[patch_name] = new_block.strip()

            # Reconstruct the inner boundary field block
            new_boundary_field = "\n"
            for patch_name, block_content in blocks.items():
                # Handle quotes for catch-all
                display_name = f'"{patch_name}"' if patch_name == '.*' else patch_name
                new_boundary_field += f"    {display_name}\n    {{\n"
                # preserve indentation
                for line in block_content.split('\n'):
                    if line.strip():
                        new_boundary_field += f"        {line.strip()}\n"
                new_boundary_field += "    }\n\n"

            new_content = content[:start_idx] + new_boundary_field + content[end_idx:]

            with open(file_path, 'w') as f:
                f.write(new_content)
    def _update_turbulence_properties(self, turbulence):
        tp_path = os.path.join(self.case_dir, "constant", "turbulenceProperties")
        if not os.path.exists(tp_path): return

        with open(tp_path, 'r') as f:
            content = f.read()

        if turbulence == "laminar" or turbulence == "kOmegaSST_disabled":
            # Cleanly disable turbulence without removing the underlying model.
            content = re.sub(r"simulationType\s+.*?;", "simulationType  RAS;", content)
            content = re.sub(r"turbulence\s+.*?;", "turbulence      off;", content)
        else:
            content = re.sub(r"simulationType\s+.*?;", "simulationType  RAS;", content)
            content = re.sub(r"model\s+.*?;", f"model           {turbulence};", content)
            content = re.sub(r"turbulence\s+.*?;", "turbulence      on;", content)

        with open(tp_path, 'w') as f:
            f.write(content)

    def _update_fvSchemes(self, turbulence):
        import shutil
        template_path = os.path.join(self.case_dir, "system", "fvSchemes.template")
        target_path = os.path.join(self.case_dir, "system", "fvSchemes")

        # Recover from permanent modification if user lacks template
        if not os.path.exists(template_path) and os.path.exists(target_path):
            shutil.copy2(target_path, template_path)

        if os.path.exists(template_path):
            shutil.copy2(template_path, target_path)

        if not os.path.exists(target_path): return

        with open(target_path, 'r') as f:
            content = f.read()

        # Apply limited correctors for high-skew automated meshes
        # This prevents SIGFPEs in snGrad and laplacian calculations
        content = re.sub(r"(snGradSchemes\s*\{[^}]*?default\s+).*?;", r"\g<1>limited corrected 0.33;", content)
        content = re.sub(r"(laplacianSchemes\s*\{[^}]*?default\s+).*?;", r"\g<1>Gauss linear limited corrected 0.33;", content)

        if turbulence == "laminar":
            content = re.sub(r"div\(phi,k\).*?;", "", content)
            content = re.sub(r"div\(phi,epsilon\).*?;", "", content)
            content = re.sub(r"div\(phi,omega\).*?;", "", content)
            content = re.sub(r"div\(phi,R\).*?;", "", content)
            # Switch to upwind for U to ensure stability on coarse mesh without turbulent viscosity
            content = re.sub(r"div\(phi,U\).*?;", "div(phi,U)      bounded Gauss upwind;", content)
        elif turbulence == "RNGkEpsilon":
            content = re.sub(r"div\(phi,omega\).*?;", "", content)
            content = re.sub(r"div\(phi,R\).*?;", "", content)
            # Upwind U to ensure stability on coarse/scaled meshes with turbulence enabled
            content = re.sub(r"div\(phi,U\).*?;", "div(phi,U)      bounded Gauss upwind;", content)

            # Robustly inject if missing due to prior corrupted files (handles Windows CRLF and arbitrary spacing)
            if "div(phi,k)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,k)      bounded Gauss upwind;", content, count=1)
            if "div(phi,epsilon)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,epsilon) bounded Gauss upwind;", content, count=1)

        elif turbulence == "kOmegaSST" or turbulence == "kOmegaSST_disabled":
            content = re.sub(r"div\(phi,R\).*?;", "", content)

            if "div(phi,k)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,k)      bounded Gauss upwind;", content, count=1)
            if "div(phi,omega)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,omega) bounded Gauss upwind;", content, count=1)

        with open(target_path, 'w', newline='\n') as f:
            # Clean up empty lines created by regex sub and enforce Unix line endings
            cleaned = "\n".join([s for s in content.splitlines() if s.strip()])
            f.write(cleaned + "\n")

        # If we had to synthesize the file from scratch because template was corrupted, save it
        if not os.path.exists(template_path):
            shutil.copy2(target_path, template_path)

    def _update_fvSolution(self, turbulence, cfd_settings=None):
        import shutil
        template_path = os.path.join(self.case_dir, "system", "fvSolution.template")
        target_path = os.path.join(self.case_dir, "system", "fvSolution")

        default_base_template = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2512                                 |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solvers
{
    p
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-6;
        relTol          0.01;
    }

    U
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0.1;
    }

    k
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0.1;
    }

    epsilon
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0.1;
    }

    omega
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0.1;
    }

    R
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0.1;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 2; // Add 2 or 3 of these
    consistent      no;
    pRefCell        0;
    pRefValue       0;
    residualControl
    {
        p               1e-4;
        U               1e-4;
        k               1e-4;
        epsilon         1e-4;
        omega           1e-4;
        R               1e-4;
    }
}

relaxationFactors
{
    fields
    {
        p               0.2;
    }
    equations
    {
        U               0.5;
        k               0.5;
        epsilon         0.5;
        omega           0.5;
        R               0.5;
    }
}

// ************************************************************************* //
"""

        # Repair corrupted templates from previous bugs
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                template_content = f.read()

            # If the template is an outdated regex block template, or is missing critical base fields
            # (which means it was corrupted by the previous overwrite bug), restore it to the full default.
            is_corrupted = False
            if '"(U|k|epsilon)"' in template_content or '"(U|k|epsilon|omega)"' in template_content:
                is_corrupted = True
            elif not re.search(r"\bepsilon\b\s*\{", template_content) or not re.search(r"\bomega\b\s*\{", template_content):
                # Only repair if it looks like our default file structure
                if "FoamFile" in template_content and "solvers" in template_content:
                    is_corrupted = True

            if is_corrupted:
                with open(template_path, 'w', newline='\n') as f:
                    f.write(default_base_template)

        # Recover from permanent modification if user lacks template entirely
        if not os.path.exists(template_path):
            if os.path.exists(target_path):
                shutil.copy2(target_path, template_path)
            else:
                with open(template_path, 'w', newline='\n') as f:
                    f.write(default_base_template)

        if os.path.exists(template_path):
            shutil.copy2(template_path, target_path)

        if not os.path.exists(target_path): return

        with open(target_path, 'r') as f:
            content = f.read()

        def remove_block(text, block_name):
            pattern_solver = r"\s*\b" + block_name + r"\b\s*\{[^}]+\}"
            text = re.sub(pattern_solver, "", text)
            pattern_line = r"^\s*\b" + block_name + r"\b\s+[\d\.e\-\+]+;\s*$"
            text = re.sub(pattern_line, "", text, flags=re.MULTILINE)
            return text

        if turbulence == "laminar":
            for field in ["k", "epsilon", "omega", "R"]:
                content = remove_block(content, field)
        elif turbulence == "RNGkEpsilon":
            for field in ["omega", "R"]:
                content = remove_block(content, field)
        elif turbulence == "kOmegaSST" or turbulence == "kOmegaSST_disabled":
            for field in ["epsilon", "R"]:
                content = remove_block(content, field)

        if cfd_settings and 'relaxation_factors' in cfd_settings:
            relax_factors = cfd_settings['relaxation_factors']
            parts = content.split("relaxationFactors", 1)
            if len(parts) > 1:
                relax_block = parts[1]
                for factor_name, factor_value in relax_factors.items():
                    relax_block = re.sub(rf"\b{factor_name}\s+[\d\.\-e\+]+;", f"{factor_name}               {factor_value};", relax_block)
                content = parts[0] + "relaxationFactors" + relax_block
            else:
                for factor_name, factor_value in relax_factors.items():
                    content = re.sub(rf"\b{factor_name}\s+[\d\.\-e\+]+;", f"{factor_name}               {factor_value};", content)

        # Clean up empty lines created by regex sub and enforce Unix line endings for OpenFOAM in Podman
        cleaned = "\n".join([s for s in content.splitlines() if s.strip()])

        with open(target_path, 'w', newline='\n') as f:
            f.write(cleaned + "\n")

    def _generate_decomposeParDict(self, num_processors=None, method="scotch"):
        """
        Generates system/decomposeParDict for parallel execution using Jinja2.
        Supports 'scotch' and 'hierarchical' methods.
        """
        if num_processors is None:
            num_processors = self.num_processors

        coeffs_block = ""
        if method == "hierarchical":
            # For hierarchical, we need to find 3 factors that multiply to num_processors
            # A simple heuristic: try to balance x, y, z roughly equally, or x=y and z different.
            # Here's a basic prime factorization to get 3 factors
            def get_3_factors(n):
                # Try to find x, y, z close to each other
                best = (1, 1, n)
                min_diff = n
                for i in range(1, int(n**(1/3.0)) + 2):
                    if n % i == 0:
                        rem = n // i
                        for j in range(1, int(rem**0.5) + 2):
                            if rem % j == 0:
                                k = rem // j
                                diff = max(i, j, k) - min(i, j, k)
                                if diff < min_diff:
                                    min_diff = diff
                                    best = (i, j, k)
                return best

            fx, fy, fz = get_3_factors(num_processors)
            coeffs_block = f"""
hierarchicalCoeffs
{{
    n           ({fx} {fy} {fz});
    delta       0.001;
    order       xyz;
}}
"""

        template_str = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2512                                 |
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

numberOfSubdomains {{{{ num_processors }}}};

method          {method};
{coeffs_block}
// ************************************************************************* //
"""
        template = jinja2.Template(template_str)
        content = template.render(num_processors=num_processors)

        with open(os.path.join(self.case_dir, "system", "decomposeParDict"), 'w') as f:
            f.write(content)

    def _inject_function_objects(self):
        """
        Injects surfaceFieldValue function objects from config using Jinja2 template.
        """
        control_dict = os.path.join(self.case_dir, "system", "controlDict")
        template_dict = os.path.join(self.case_dir, "system", "controlDict.template")

        if os.path.exists(template_dict):
            with open(template_dict, 'r') as f:
                template_str = f.read()

            extractors = self.config.get('optimization', {}).get('extractors', [])

            physics_boundaries = self.config.get('physics', {}).get('boundaries', {})
            # Post process extractors slightly if needed (e.g., figure out patch names)
            for ext in extractors:
                if 'patch_name' not in ext:
                    # Try to infer patch name from metric_name or function_name
                    is_inlet = 'in' in ext.get('metric_name', '').lower() or 'in' in ext.get('function_name', '').lower()
                    is_outlet = 'out' in ext.get('metric_name', '').lower() or 'out' in ext.get('function_name', '').lower()

                    found_patch = None
                    if is_inlet:
                        for name in physics_boundaries:
                            if 'inlet' in name.lower():
                                found_patch = name
                                break
                        ext['patch_name'] = found_patch if found_patch else 'inlet'
                    elif is_outlet:
                        for name in physics_boundaries:
                            if 'clean_outlet' in name.lower():
                                found_patch = name
                                break
                            elif 'outlet' in name.lower() and not 'dust' in name.lower():
                                found_patch = name

                        if not found_patch:
                            if '1' in ext.get('metric_name', ''):
                                 ext['patch_name'] = 'outlet_1'
                            elif '2' in ext.get('metric_name', ''):
                                 ext['patch_name'] = 'outlet_2'
                            else:
                                 ext['patch_name'] = 'outlet'
                        else:
                            ext['patch_name'] = found_patch

            template = jinja2.Template(template_str)
            content = template.render(extractors=extractors)

            with open(control_dict, 'w') as f:
                f.write(content)
        else:
            print("Warning: controlDict.template not found. Skipping function object injection.")

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
            (new_min[0], new_min[1], new_min[2]),
            (new_max[0], new_min[1], new_min[2]),
            (new_max[0], new_max[1], new_min[2]),
            (new_min[0], new_max[1], new_min[2]),
            (new_min[0], new_min[1], new_max[2]),
            (new_max[0], new_min[1], new_max[2]),
            (new_max[0], new_max[1], new_max[2]),
            (new_min[0], new_max[1], new_max[2])
        ]

        bm_path = os.path.join(self.case_dir, "system", "blockMeshDict")
        template_path = os.path.join(self.case_dir, "system", "blockMeshDict.template")

        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                template_str = f.read()
            template = jinja2.Template(template_str)
            content = template.render(vertices=vertices, nx=nx, ny=ny, nz=nz)
            with open(bm_path, 'w') as f:
                f.write(content)
        else:
            print("Error: blockMeshDict template not found. Using fallback regex.")
            # Fallback for old templates without jinja variables
            if os.path.exists(bm_path):
                with open(bm_path, 'r') as f:
                    content = f.read()
                new_vertices_str = "\n    ".join([f"({v[0]} {v[1]} {v[2]})" for v in vertices])
                pattern = re.compile(r"vertices\s*\((.*?)\);", re.DOTALL)
                if pattern.search(content):
                    content = pattern.sub(f"vertices\n(\n    {new_vertices_str}\n);", content)
                pattern_blocks = re.compile(r"hex\s*\([^\)]+\)\s*\(\s*\d+\s+\d+\s+\d+\s*\)", re.DOTALL)
                if pattern_blocks.search(content):
                     content = pattern_blocks.sub(f"hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz})", content)
                with open(bm_path, 'w') as f:
                    f.write(content)

    def update_snappyHexMesh_location(self, bounds, custom_location=None, helix_path_radius_mm=None):
        """
        Updates locationInMesh in system/snappyHexMeshDict to be inside the fluid domain.
        """
        location = None

        # 1. ALWAYS prefer the analytical center of the fluid channel
        if helix_path_radius_mm is not None:
            try:
                r_m = float(helix_path_radius_mm) * 0.001
                location = f"({r_m:.4f} 0 0)"
                print(f"Using reliable analytical locationInMesh: {location}")
            except (ValueError, TypeError):
                pass

        # 2. Fallback to custom ray-traced location ONLY if radius isn't provided
        if location is None and custom_location is not None:
            location = f"({custom_location[0]:.3f} {custom_location[1]:.3f} {custom_location[2]:.3f})"
            print(f"Using ray-traced locationInMesh: {location}")

        if location is None:
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
        template_path = os.path.join(self.case_dir, "system", "snappyHexMeshDict.template")

        # Use template if available, else fallback
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                content = f.read()
        elif os.path.exists(shm_path):
            with open(shm_path, 'r') as f:
                content = f.read()
        else:
            print("Error: snappyHexMeshDict template not found.")
            return

        # Regex to find locationInMesh (x y z); (Using DOTALL to catch multi-line formatting)
        pattern = re.compile(r"locationInMesh\s*\(.*?\);", re.DOTALL)
        if pattern.search(content):
            content = pattern.sub(f"locationInMesh {location};", content)

        with open(shm_path, 'w') as f:
            f.write(content)

    def _check_boundary_patches(self):
        """
        Checks if the required patches exist and have faces.
        Returns True if valid, False otherwise.
        """
        boundary_file = os.path.join(self.case_dir, "constant", "polyMesh", "boundary")
        if not os.path.exists(boundary_file):
            print("Error: polyMesh/boundary file not found.")
            return False

        with open(boundary_file, 'r') as f:
            content = f.read()

        patches_to_check = ["corkscrew"]
        physics_boundaries = self.config.get('physics', {}).get('boundaries', {})
        if physics_boundaries:
            for name, opts in physics_boundaries.items():
                if opts.get("type") == "patch":
                    patches_to_check.append(name)
        else:
            patches_to_check.extend(["inlet", "outlet"])

        for patch in patches_to_check:
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

    def _generate_topoSetDict(self, bin_config=None, skip_io=False):
        """
        Generates system/topoSetDict using Jinja2.
        skip_io: if True, skips generation of inlet/outlet face sets.
        """
        template_str = r"""/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2512                                 |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      topoSetDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

actions
(
    // 1. Select all faces in 'corkscrew' patch
    {
        name    corkscrewFaces;
        type    faceSet;
        action  new;
        source  patchToFace;
        patch   corkscrew;
    }
    {% if not skip_io %}
    {% for b in dynamic_boundaries %}
    // Select {{ b.name }} Faces
    {
        name    {{ b.name }}Faces;
        type    faceSet;
        action  new;
        source  normalToFace;
        normal  {{ b.normal }};
        cos     0.8; // Tolerance
    }
    {
        name    {{ b.name }}Faces;
        type    faceSet;
        action  subset;
        source  faceToFace;
        set     corkscrewFaces;
    }
    {% endfor %}
    {% endif %}

    {% if bins %}
    // 4. Bin Split Actions
    {% for bin in bins %}
    // Bin {{ bin.index }}
    {
        name    bin_{{ bin.index }}_faces;
        type    faceSet;
        action  new;
        source  boxToFace;
        box     (-100 -100 {{ "%.5f"|format(bin.z_min) }}) (100 100 {{ "%.5f"|format(bin.z_max) }});
    }
    {
        name    bin_{{ bin.index }}_faces;
        type    faceSet;
        action  subset;
        source  faceToFace;
        set     corkscrewFaces;
    }
    {% if not skip_io %}
    {% for b in dynamic_boundaries %}
    {
        name    bin_{{ bin.index }}_faces;
        type    faceSet;
        action  subtract;
        source  faceToFace;
        set     {{ b.name }}Faces;
    }
    {% endfor %}
    {% endif %}
    {% endfor %}
    {% endif %}
);

// ************************************************************************* //
"""
        bins = []
        if bin_config and bin_config.get("num_bins", 1) > 1:
            num_bins = int(bin_config["num_bins"])
            length = float(bin_config.get("insert_length_mm", 50.0))
            scale = 0.001
            z_start = -(length * scale) / 2.0
            bin_h = (length * scale) / num_bins

            for i in range(num_bins):
                z_min = z_start + i * bin_h
                z_max = z_start + (i + 1) * bin_h
                bins.append({"index": i+1, "z_min": z_min, "z_max": z_max})

        dynamic_boundaries = []
        physics_boundaries = self.config.get('physics', {}).get('boundaries', {})
        for name, opts in physics_boundaries.items():
            if opts.get("type") == "patch":
                align = opts.get("alignment")
                # Infer normal from alignment or name
                if align == "vertical" and "inlet" in name.lower():
                    normal = "(0 0 -1)"
                elif align == "horizontal":
                    normal = "(0 0 1)"
                elif "out" in name.lower():
                    normal = "(0 0 1)"
                else:
                    normal = "(0 0 -1)" # Default fallback
                dynamic_boundaries.append({"name": name, "normal": normal})

        # Fallback if config is missing
        if not dynamic_boundaries:
            dynamic_boundaries = [
                {"name": "inlet", "normal": "(0 0 -1)"},
                {"name": "outlet", "normal": "(0 0 1)"}
            ]

        template = jinja2.Template(template_str)
        content = template.render(skip_io=skip_io, bins=bins, dynamic_boundaries=dynamic_boundaries)

        with open(os.path.join(self.case_dir, "system", "topoSetDict"), 'w') as f:
            f.write(content)

    def _generate_createPatchDict(self, bin_config=None, skip_io=False):
        """
        Generates system/createPatchDict using Jinja2.
        """
        template_str = """/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2512                                 |
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
    {% if not skip_io %}
    {% for b in dynamic_boundaries %}
    {
        name {{ b.name }};
        patchInfo
        {
            type patch;
            inGroups ({{ b.name }}Group);
        }
        constructFrom set;
        set {{ b.name }}Faces;
    }
    {% endfor %}
    {% endif %}
    {% if bins %}
    {% for bin in bins %}
    {
        name bin_{{ bin.index }};
        patchInfo
        {
            type patch;
            inGroups (corkscrew_bins);
        }
        constructFrom set;
        set bin_{{ bin.index }}_faces;
    }
    {% endfor %}
    {% endif %}
);

// ************************************************************************* //
"""
        bins = []
        if bin_config and bin_config.get("num_bins", 1) > 1:
            num_bins = int(bin_config["num_bins"])
            for i in range(num_bins):
                bins.append({"index": i+1})

        dynamic_boundaries = []
        physics_boundaries = self.config.get('physics', {}).get('boundaries', {})
        for name, opts in physics_boundaries.items():
            if opts.get("type") == "patch":
                dynamic_boundaries.append({"name": name})

        # Fallback if config is missing
        if not dynamic_boundaries:
            dynamic_boundaries = [
                {"name": "inlet"},
                {"name": "outlet"}
            ]

        template = jinja2.Template(template_str)
        content = template.render(skip_io=skip_io, bins=bins, dynamic_boundaries=dynamic_boundaries)

        with open(os.path.join(self.case_dir, "system", "createPatchDict"), 'w') as f:
            f.write(content)

    def _generate_kinematicCloudProperties(self, bin_config=None, turbulence="laminar"):
        """
        Generates constant/kinematicCloudProperties with size binning and spatial binning using Jinja2.
        """
        template_str = r"""/*--------------------------------*- C++ -*----------------------------------*\
        Generates constant/kinematicCloudProperties with dynamic size binning and spatial binning.
        """
        # Default fallback values
        sizes_um = [5, 10, 20, 50, 100]
        rho0_val = 3100  # Moon Dust density
        tube_od_m = 0.032
        fluid_velocity_z = 5.0

        # Extract dynamic values from config if provided
        if bin_config:
            sizes_um = bin_config.get("dust_sizes_um", sizes_um)
            if isinstance(sizes_um, str): # Handle comma-separated string from LLM if needed
                sizes_um = [float(x.strip()) for x in sizes_um.split(',')]

            rho0_val = float(bin_config.get("dust_density", rho0_val))
            tube_od_m = float(bin_config.get("tube_od_mm", 32.0)) / 1000.0
            fluid_velocity_z = float(bin_config.get("fluid_velocity", 5.0))

        # 1. Scale parcels per second based on cross-sectional area
        # Baseline: 5000 parcels/sec for a 32mm pipe
        inlet_area_m2 = math.pi * ((tube_od_m / 2.0)**2)
        baseline_area = math.pi * ((0.032 / 2.0)**2)
        area_ratio = inlet_area_m2 / baseline_area
        parcels_per_sec = int(5000 * area_ratio)

        template_str = r"""/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2512                                 |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "constant";
    object      kinematicCloudProperties;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

solution
{
    active          true;
    coupled         false; // One-way coupling
    transient       yes;
    maxTrackTime    10.0;
    calcFrequency   1;
    cellValueSourceCorrection off;

    interpolationSchemes
    {
        rho             cell;
        U               cellPoint;
        mu              cell;{{ turb_interpolation }}
    }

    integrationSchemes
    {
        U               analytical;
    }
}

constantVolume      false;

// Moon Dust Properties (Basaltic Regolith)
rho0            {{ rho0 }}; // kg/m^3 (approx. 3.1 g/cm^3)

// Young's Modulus: ~70 GPa (Basalt)
// Poisson's Ratio: 0.25 (Basalt)
// Restitution Coefficient: ~0.8-0.9

subModels
{
    particleForces
    {
        sphereDrag;
        gravity;
    }

    collisionModel none;
    // For dilute flows, stochastic collisions are negligible.
    // If enabled, use: stochasticCollision; with coefficients for Basalt.
    stochasticCollisionModel none;

    injectionModels
    {
        {% for injection in injections %}
        model_{{ injection.size_um }}um
        {
            type            patchInjection;
            patch           {{ inlet_patch_name }};
            parcelBasisType mass;
            massTotal       {{ "%.6e"|format(injection.mass_flow_rate) }};
            duration        1;
            SOI             0;
            parcelsPerSecond 5000;
            flowRateProfile constant 1;
            U0              (0 0 5);
            sizeDistribution
            {
                type        fixedValue;
                fixedValueDistribution
                {
                    value   {{ injection.size_m }};
                }
            }
        }
        {% endfor %}
    }

    dispersionModel {{ disp_model }};//gradientDispersionRAS;

    patchInteractionModel localInteraction;

    localInteractionCoeffs
    {
        patches
        (
            "(.*)"
            {
                type rebound;
                e    0.97;
                mu   0.09;
            }
            corkscrew
            {
                type stick;
            }
            {% if bins %}
            {% for bin in bins %}
            bin_{{ bin.index }}
            {
                type stick;
            }
            {% endfor %}
            {% endif %}
            {% for b in dynamic_boundaries %}
            {% if b.is_outlet %}
            {{ b.name }}
            {
                type escape;
            }
            {% elif b.is_inlet %}
            {{ b.name }}
            {
                type escape;
            }
            {% else %}
            {{ b.name }}
            {
                type stick;
            }
            {% endif %}
            {% endfor %}
        );
    }

    surfaceFilmModel none;
}

cloudFunctions
{
    // particleCollector1
    // {
    //     type            particleCollector;
    //     mode            patch;
    //     patches         ( corkscrew inlet outlet {% if bins %}{% for bin in bins %} bin_{{ bin.index }}{% endfor %}{% endif %} );
    //     removeCollected false;
    //     resetOnWrite    false;
    //     log             true;
    //     negateParcelsOppositeNormal false;
    //     surfaceFormat   vtk;
    //     polygonData     off;
    // }

    //patchPostProcessing1
    //{
    //    type            patchPostProcessing;
    //    patches         ( corkscrew inlet outlet {% if bins %}{% for bin in bins %} bin_{{ bin.index }}{% endfor %}{% endif %} );
    //    maxStoredParcels 1000000;
    //    resetOnWrite    false;
    //    log             true;
    //}
}

// ************************************************************************* //
"""
        physics_config = self.config.get('physics', {})
        particles_config = physics_config.get('particles', {})

        # Default fallback values
        sizes_um = particles_config.get('sizes_um', [5, 10, 20, 50, 100])
        rho0_val = particles_config.get('rho0', 3100)  # Moon Dust density
        tube_od_m = 0.032
        fluid_velocity_z = 5.0

        # Extract dynamic values from config if provided
        if bin_config:
            sizes_um = bin_config.get("dust_sizes_um", sizes_um)
            if isinstance(sizes_um, str): # Handle comma-separated string from LLM if needed
                sizes_um = [float(x.strip()) for x in sizes_um.split(',')]

            rho0_val = float(bin_config.get("dust_density", rho0_val))
            tube_od_m = float(bin_config.get("tube_od_mm", 32.0)) / 1000.0
            fluid_velocity_z = float(bin_config.get("fluid_velocity", 5.0))

        # 1. Scale parcels per second based on cross-sectional area
        # Baseline: 5000 parcels/sec for a 32mm pipe
        inlet_area_m2 = math.pi * ((tube_od_m / 2.0)**2)
        baseline_area = math.pi * ((0.032 / 2.0)**2)
        area_ratio = inlet_area_m2 / baseline_area
        parcels_per_sec = int(5000 * area_ratio)

        injections = []
        for d_um in sizes_um:
            d_m = d_um * 1e-6
            volume = (4.0/3.0) * math.pi * ((d_m / 2.0)**3)
            mass_flow_rate = rho0_val * volume * parcels_per_sec
            injections.append({
                "size_um": d_um,
                "size_m": d_m,
                "mass_flow_rate": mass_flow_rate
            })

        bins = []
        if bin_config and bin_config.get("num_bins", 1) > 1:
            num_bins = int(bin_config["num_bins"])
            for i in range(num_bins):
                bins.append({"index": i+1})

        # --- NEW: Dynamic Turbulence Detection ---
        # Read turbulenceProperties to see if we are running laminar or turbulent
        is_laminar = False
        turb_path = os.path.join(self.case_dir, "constant", "turbulenceProperties")
        if os.path.exists(turb_path):
            with open(turb_path, 'r') as f:
                t_content = f.read()
                if "simulationType laminar;" in t_content or "simulationType  laminar;" in t_content:
                    is_laminar = True
                if "turbulence      off;" in t_content or "turbulence off;" in t_content:
                    is_laminar = True  # Treat as laminar for dispersion model purposes!

        if turbulence == "force_laminar_fallback" or turbulence == "laminar":
            is_laminar = True

        # Build the conditional strings
        if is_laminar:
            turb_interpolation = ""
            disp_model = "none"
        else:
            turb_interpolation = """
        k               cellPoint;
        epsilon         cellPoint;"""

            # Add omega only if not using RNGkEpsilon (which doesn't solve omega)
            cfd_settings = self.config.get('cfd_settings', {})
            turbulence_model = cfd_settings.get('turbulence_model', 'laminar')
            if turbulence_model != "RNGkEpsilon":
                turb_interpolation += "\n        omega           cellPoint;"

            disp_model = "stochasticDispersionRAS"
        # -----------------------------------------

        dynamic_boundaries = []
        physics_boundaries = self.config.get('physics', {}).get('boundaries', {})
        inlet_patch_name = "inlet"

        for name, opts in physics_boundaries.items():
            if opts.get("type") == "patch":
                is_inlet = "inlet" in name.lower()
                is_outlet = "out" in name.lower()
                if is_inlet:
                    inlet_patch_name = name
                dynamic_boundaries.append({
                    "name": name,
                    "is_inlet": is_inlet,
                    "is_outlet": is_outlet
                })

        if not dynamic_boundaries:
            dynamic_boundaries = [
                {"name": "inlet", "is_inlet": True, "is_outlet": False},
                {"name": "outlet", "is_inlet": False, "is_outlet": True}
            ]

        template = jinja2.Template(template_str)
        content = template.render(
            rho0=rho0_val,
            injections=injections,
            bins=bins,
            parcels_per_sec=parcels_per_sec,
            fluid_velocity_z=fluid_velocity_z,
            turb_interpolation=turb_interpolation,
            disp_model=disp_model,
            dynamic_boundaries=dynamic_boundaries,
            inlet_patch_name=inlet_patch_name
        )

        with open(os.path.join(self.case_dir, "constant", "kinematicCloudProperties"), 'w') as f:
            f.write(content)

    def scale_mesh(self, stl_filename="corkscrew_fluid.stl", scale_factor=0.001, log_file=None):
        """
        Scales the STL mesh using surfaceMeshConvert.
        Crucially converts Windows paths to Linux paths for the container.
        """
        # Construct the relative path
        # FORCE forward slashes for Linux container compatibility
        stl_rel_path = f"constant/triSurface/{stl_filename}"

        # Use a temporary output file to avoid in-place overwrite issues on mounted volumes
        temp_filename = f"temp_{stl_filename}"
        temp_rel_path = f"constant/triSurface/{temp_filename}"

        # Command: surfaceMeshConvert input output -scale factor
        cmd = ["surfaceMeshConvert", stl_rel_path, temp_rel_path, "-scale", str(scale_factor)]

        if not self.run_command(cmd, log_file=log_file, description="Scaling Mesh (mm -> m)"):
            return False

        # Rename temp file to original (overwrite) on host
        src = os.path.join(self.case_dir, "constant", "triSurface", temp_filename)
        dst = os.path.join(self.case_dir, "constant", "triSurface", stl_filename)

        try:
            if os.path.exists(dst):
                os.remove(dst)
            shutil.move(src, dst)
            return True
        except Exception as e:
            print(f"Error renaming scaled mesh: {e}")
            if log_file:
                with open(log_file, 'a') as f:
                    f.write(f"\nError renaming scaled mesh: {e}\n")
            return False

    def _generate_snappyHexMeshDict(self, stl_assets, add_layers=True):
        """
        Updates system/snappyHexMeshDict to include all assets as geometry/patches using Jinja2.
        """
        if not stl_assets: return

        physics_boundaries = self.config.get('physics', {}).get('boundaries', {})

        geometries = []
        for key, filename in stl_assets.items():
            patch_name = "corkscrew"
            if key in physics_boundaries:
                patch_name = key
            elif key == "wall":
                patch_name = "corkscrew"
            elif key == "inlet":
                patch_name = "inlet"
            elif key == "outlet":
                patch_name = "outlet"

            geom = {
                "filename": filename,
                "name": patch_name,
                "level": "(1 1)",
                "patch_info": key in physics_boundaries or key in ["inlet", "outlet"]
            }
            geometries.append(geom)

        template_path = os.path.join(self.case_dir, "system", "snappyHexMeshDict.template")
        shm_path = os.path.join(self.case_dir, "system", "snappyHexMeshDict")

        # We need to preserve the dynamically injected locationInMesh if it exists in the active dict
        preserved_location = None
        if os.path.exists(shm_path):
            with open(shm_path, 'r') as f:
                existing_content = f.read()
                pattern = re.compile(r"locationInMesh\s*\((.*?)\);", re.DOTALL)
                m = pattern.search(existing_content)
                if m:
                    preserved_location = m.group(1)

        if os.path.exists(template_path):
            with open(template_path, 'r') as f: content = f.read()
        else:
            print("Error: snappyHexMeshDict.template missing")
            return

        with open(template_path, 'r') as f:
            template_str = f.read()

        # Extract existing locationInMesh to preserve it if it was updated earlier
        shm_path = os.path.join(self.case_dir, "system", "snappyHexMeshDict")
        location_in_mesh = "(-0.007 -0.007 -0.012)" # Default fallback
        if os.path.exists(shm_path):
            with open(shm_path, 'r') as f:
                content = f.read()
            match = re.search(r"locationInMesh\s*(\(.*?\));", content, re.DOTALL)
            if match:
                location_in_mesh = match.group(1)

        template = jinja2.Template(template_str)
        content = template.render(
            add_layers=add_layers,
            geometries=geometries,
            location_in_mesh=location_in_mesh
        )

        # Restore preserved location
        if preserved_location:
            pattern = re.compile(r"locationInMesh\s*\(.*?\);", re.DOTALL)
            if pattern.search(content):
                content = pattern.sub(f"locationInMesh ({preserved_location});", content)

        with open(shm_path, 'w') as f:
            f.write(content)

    def run_meshing(self, log_file=None, bin_config=None, stl_assets=None, add_layers=True, **kwargs):
        """
        Runs the meshing pipeline.
        stl_assets: dict of filenames {'fluid': '...', 'inlet': '...', ...}
        """
        cfd_settings = self.config.get('cfd_settings', {})
        mesh_procs = cfd_settings.get('mesh_processors', self.num_processors)
        mesh_method = cfd_settings.get('mesh_decompose_method', 'hierarchical')

        # 1. Update snappyHexMeshDict if assets provided
        using_assets = False
        if stl_assets and isinstance(stl_assets, dict):
            self._generate_snappyHexMeshDict(stl_assets, add_layers=add_layers)
            using_assets = True

        # 2. Generate patch creation configs
        self._generate_topoSetDict(bin_config, skip_io=False)
        self._generate_createPatchDict(bin_config, skip_io=False)

        # Ensure we capture output
        # Step 1: Base Mesh
        if not self.run_command(["blockMesh"], log_file=log_file, description="Meshing (blockMesh)"): return False

        # For surfaceFeatureExtract, if using assets, we might need to update that dict too?
        if not self.run_command(["surfaceFeatureExtract"], log_file=log_file, description="Meshing (surfaceFeatureExtract)"): return False

        if mesh_procs > 1:
            self._generate_decomposeParDict(num_processors=mesh_procs, method=mesh_method)

            # Temporarily hide 0 dir so decomposePar doesn't crash due to missing patches from blockMesh
            zero_dir = os.path.join(self.case_dir, "0")
            zero_bak = os.path.join(self.case_dir, "0.bak")
            if os.path.exists(zero_dir):
                shutil.move(zero_dir, zero_bak)

            success_decompose = self.run_command(["decomposePar", "-force"], log_file=log_file, description="Decomposing for Meshing")

            # Restore 0 dir
            if os.path.exists(zero_bak):
                shutil.move(zero_bak, zero_dir)

            if not success_decompose: return False

            cmd = ["mpirun", "--allow-run-as-root", "--oversubscribe", "-np", str(mesh_procs), "snappyHexMesh", "-overwrite", "-parallel"]
            if not self.run_command(cmd, log_file=log_file, description="Meshing (snappyHexMesh Parallel)", timeout=3600):
                print("Error: Meshing failed. Boundary layers are critical, design rejected.")
                return False

            if not self.run_command(["reconstructParMesh", "-constant"], log_file=log_file, description="Reconstructing Mesh"): return False

            # After reconstruction, clean up processor directories to save disk space
            for proc_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
                shutil.rmtree(proc_dir, ignore_errors=True)

            # Step 2: Create Patches (Serial, after reconstruction to prevent boundary overlap bugs)
            if not self.run_command(["topoSet"], log_file=log_file, description="Meshing (topoSet)"): return False
            if not self.run_command(["createPatch", "-overwrite"], log_file=log_file, description="Meshing (createPatch)"): return False

        else:
            if not self.run_command(["snappyHexMesh", "-overwrite"], log_file=log_file, description="Meshing (snappyHexMesh)", timeout=3600):
                print("Error: Meshing failed. Boundary layers are critical, design rejected.")
                return False

            # Step 2: Create Patches (Serial)
            if not self.run_command(["topoSet"], log_file=log_file, description="Meshing (topoSet)"): return False
            if not self.run_command(["createPatch", "-overwrite"], log_file=log_file, description="Meshing (createPatch)"): return False

        # Step 3: Check
        if not self.run_command(["checkMesh"], log_file=log_file, description="Meshing (checkMesh)"): return False

        # Post-meshing verification
        if not self._check_boundary_patches():
            print("Meshing failed verification: missing or empty inlet/outlet patches.")
            return False

        return True

    def _apply_fallback_wall_functions(self):
        """
        Applies fallback wall functions if the mesh was scaled up for memory limits.
        Driven by `cfd_settings.fallback_wall_functions` in the config.
        """
        cfd_settings = self.config.get('cfd_settings', {})
        fallback_funcs = cfd_settings.get('fallback_wall_functions', {})
        if not fallback_funcs:
            return

        # Find all 0 directories (base + processor)
        zero_dirs = [os.path.join(self.case_dir, "0")]
        zero_dirs.extend(glob.glob(os.path.join(self.case_dir, "processor*", "0")))

        for field_name, new_wall_func in fallback_funcs.items():

            # Procedural override: Never use zeroGradient for k or epsilon to prevent stochasticDispersionRAS SIGFPE
            if new_wall_func == "zeroGradient":
                if field_name == "epsilon":
                    new_wall_func = "epsilonWallFunction"
                    print("Procedurally overriding epsilon fallback wall function from zeroGradient to epsilonWallFunction to prevent SIGFPE.")
                elif field_name == "k":
                    new_wall_func = "kqRWallFunction"
                    print("Procedurally overriding k fallback wall function from zeroGradient to kqRWallFunction to prevent SIGFPE.")

            for z_dir in zero_dirs:
                field_path = os.path.join(z_dir, field_name)
                if not os.path.exists(field_path):
                    continue

                with open(field_path, "r") as f:
                    content = f.read()

                # The current wall function is likely from initial_fields
                initial_fields = cfd_settings.get('initial_fields', {})
                old_wall_func = None
                if field_name in initial_fields:
                    old_wall_func = initial_fields[field_name].get('wallFunction')

                # Only apply fallback to patches defined as type "wall" (and the catch-all ".*")
                physics = self.config.get('physics', {})
                boundaries = physics.get('boundaries', {})

                wall_patches = ['".*"']
                if boundaries:
                    for patch_name, patch_config in boundaries.items():
                        if patch_config.get('type') == 'wall':
                            wall_patches.append(patch_name)
                else:
                    wall_patches.append("corkscrew")

                for patch in wall_patches:
                    escaped_patch = re.escape(patch)

                    if old_wall_func:
                        pattern = re.compile(rf'({escaped_patch}\s*\{{[^}}]*?type\s+){old_wall_func}(;)', re.DOTALL)
                        content = pattern.sub(rf'\g<1>{new_wall_func}\g<2>', content)
                    else:
                        if field_name == "nut":
                            pattern = re.compile(rf'({escaped_patch}\s*\{{[^}}]*?type\s+)nutkRoughWallFunction(;)', re.DOTALL)
                            content = pattern.sub(rf'\g<1>{new_wall_func}\g<2>', content)
                        elif field_name == "epsilon":
                            pattern = re.compile(rf'({escaped_patch}\s*\{{[^}}]*?type\s+)epsilonWallFunction(;)', re.DOTALL)
                            content = pattern.sub(rf'\g<1>{new_wall_func}\g<2>', content)
                        elif field_name == "k":
                            pattern = re.compile(rf'({escaped_patch}\s*\{{[^}}]*?type\s+)kqRWallFunction(;)', re.DOTALL)
                            content = pattern.sub(rf'\g<1>{new_wall_func}\g<2>', content)

                    # Clean up roughness constants just in case we are replacing a rough wall function
                    if "nut" in field_name or new_wall_func == "nutkWallFunction":
                        pattern_ks = re.compile(rf'({escaped_patch}\s*\{{[^}}]*?)\s*Ks\s+.*?;\n?', re.DOTALL)
                        content = pattern_ks.sub(r'\g<1>', content)
                        pattern_cs = re.compile(rf'({escaped_patch}\s*\{{[^}}]*?)\s*Cs\s+.*?;\n?', re.DOTALL)
                        content = pattern_cs.sub(r'\g<1>', content)

                    if new_wall_func == "zeroGradient":
                        pattern_val1 = re.compile(rf'({escaped_patch}\s*\{{[^}}]*?type\s+zeroGradient;\s+)value\s+uniform\s+[\d\.\-e\+]+;\n?', re.DOTALL)
                        content = pattern_val1.sub(r'\g<1>', content)
                        pattern_val2 = re.compile(rf'({escaped_patch}\s*\{{[^}}]*?type\s+zeroGradient;\s+)value\s+\$internalField;\n?', re.DOTALL)
                        content = pattern_val2.sub(r'\g<1>', content)
                    elif old_wall_func == "zeroGradient":
                        # If we replaced zeroGradient with something else (like epsilonWallFunction), we must append the missing value field
                        # Use regex to only append if 'value' is missing from that block
                        pattern = re.compile(rf'({escaped_patch}\s*\{{[^}}]*?type\s+{new_wall_func};)(?!\s*value\s+)', re.DOTALL)
                        content = pattern.sub(rf'\g<1>\n        value           $internalField;', content)

                with open(field_path, "w") as f:
                    f.write(content)

            print(f"Applied fallback wall function {new_wall_func} to {field_name} due to mesh scaling.")

    def run_solver(self, log_file=None, mesh_scaled_for_memory=False, **kwargs):
        """
        Runs the solver.
        """
        cfd_settings = self.config.get('cfd_settings', {})
        mesh_procs = cfd_settings.get('mesh_processors', self.num_processors)
        solve_procs = cfd_settings.get('solve_processors', self.num_processors)
        solve_method = cfd_settings.get('solve_decompose_method', 'scotch')

        if mesh_scaled_for_memory:
            self._apply_fallback_wall_functions()

        # Clean up any crashed or old time directories to ensure a fresh start from 0 for the new mesh
        for d in os.listdir(self.case_dir):
            path = os.path.join(self.case_dir, d)
            try:
                if d != "0" and os.path.isdir(path):
                    float(d)  # Check if it's a numeric time directory
                    shutil.rmtree(path, ignore_errors=True)
            except ValueError:
                pass

        # Also clean up processor time directories if running in parallel
        for p_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
            shutil.rmtree(p_dir, ignore_errors=True)

        def _execute():
            if solve_procs > 1:
                self._generate_decomposeParDict(num_processors=solve_procs, method=solve_method)
                if not self.run_command(["decomposePar", "-force"], log_file=log_file, description="Decomposing Domain"): return False
                cmd = ["mpirun", "--allow-run-as-root", "--oversubscribe", "-np", str(solve_procs), "simpleFoam", "-parallel"]
                if not self.run_command(cmd, log_file=log_file, description=f"Solving CFD (Parallel {solve_procs} CPUs)", timeout=14400): return False
                if not self.run_command(["reconstructPar", "-latestTime"], log_file=log_file, description="Reconstructing Domain"): return False
                for proc_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
                    shutil.rmtree(proc_dir, ignore_errors=True)
                return True
            else:
                return self.run_command(["simpleFoam"], log_file=log_file, description="Solving CFD", timeout=14400)

        success = _execute()

        # If it failed, and we haven't applied fallback wall functions yet, try doing so to recover from unstable baseline!
        if not success and not mesh_scaled_for_memory:
            print("Solver failed on standard mesh. Attempting to recover by disabling turbulence...")

            # Cleanly disable turbulence to prevent epsilonWallFunction FPEs on bad mesh boundary cells
            self._update_turbulence_properties("laminar")
            self._update_fvSchemes("laminar")
            self._update_fvSolution("laminar", self.config.get('cfd_settings', {}))

            # Since turbulence is off, wall functions should NOT be applied

            # Clean up any crashed time directories to ensure a fresh start from 0
            for d in os.listdir(self.case_dir):
                path = os.path.join(self.case_dir, d)
                try:
                    if d != "0" and os.path.isdir(path):
                        float(d)  # Check if it's a numeric time directory
                        shutil.rmtree(path, ignore_errors=True)
                except ValueError:
                    pass

            # Also clean up processor time directories if running in parallel
            for p_dir in glob.glob(os.path.join(self.case_dir, "processor*")):
                for d in os.listdir(p_dir):
                    path = os.path.join(p_dir, d)
                    try:
                        if d != "0" and os.path.isdir(path):
                            float(d)
                            shutil.rmtree(path, ignore_errors=True)
                    except ValueError:
                        pass

            success = _execute()

        return success

    def _create_constant_field(self, time_dir, field_name, value, dimensions, class_type="volScalarField", boundary_type="fixedValue"):
        """
        Creates a uniform field file in the specified time directory.
        Used to create 'rho' and 'mu' for particle tracking.
        """
        header = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  v2512                                 |
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
        files = ["system/controlDict", "system/fvSchemes", "constant/kinematicCloudProperties", "constant/turbulenceProperties"]
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

    def _prepare_transient_run(self, source_time, turbulence="laminar"):
        """
        Resets the simulation to time 0, copies fields from source_time, and generates rho/mu.
        """
        zero_dir = os.path.join(self.case_dir, "0")
        source_dir = os.path.join(self.case_dir, str(source_time))

        # 1. Clean 0 directory
        if os.path.exists(zero_dir):
            shutil.rmtree(zero_dir)
        os.makedirs(zero_dir)

        # 2. Check and generate missing phi
        phi_src = os.path.join(source_dir, "phi")
        if not os.path.exists(phi_src):
            print("Generating missing 'phi' field...")
            self.run_command(["postProcess", "-func", "writePhi", "-time", str(source_time)], description="Generating phi")

        if turbulence != "laminar" and turbulence != "kOmegaSST_disabled":
            # 3. Check and generate missing epsilon (CRITICAL FOR DISPERSION)
            eps_src = os.path.join(source_dir, "epsilon")
            if not os.path.exists(eps_src):
                print("Generating 'epsilon' field for turbulent dispersion...")
                self.run_command(["postProcess", "-func", "epsilon", "-time", str(source_time)], description="Generating epsilon")

        # 4. Copy fields from source_time to 0
        if turbulence == "RNGkEpsilon":
            fields_to_copy = ["U", "p", "phi", "k", "epsilon", "nut"]
        else:
            fields_to_copy = ["U", "p", "phi", "k", "epsilon", "omega", "nut"]

        for field in fields_to_copy:
            src = os.path.join(source_dir, field)
            dst = os.path.join(zero_dir, field)
            if os.path.exists(src):
                shutil.copy2(src, dst)
            else:
                orig_src = os.path.join(self.case_dir, "0.orig", field)
                if os.path.exists(orig_src):
                    shutil.copy2(orig_src, dst)
                elif field == "phi":
                     print("Warning: 'phi' field still missing after generation attempt.")

        # 5. Generate rho and mu
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

    def _update_inlet_velocity(self, bin_config):
        """
        Updates the inlet velocity in 0.orig/U.
        Directly uses fluid_velocity if provided.
        """
        new_u = float(bin_config.get("fluid_velocity", 5.0))

        u_file = os.path.join(self.case_dir, "0.orig", "U")
        if not os.path.exists(u_file):
            return

        with open(u_file, 'r') as f:
            content = f.read()

        # Replace the value inside the inlet block
        # Look for inlet { ... value uniform (0 0 5); ... }
        # Need a somewhat robust replacement since spacing could vary

        # A simple regex for the inlet block's value
        pattern = re.compile(r"(inlet\s*\{[^}]*?value\s+uniform\s*\(\s*0\s+0\s+)([\d\.\-]+)(\s*\)\s*;)", re.DOTALL)

        if pattern.search(content):
            content = pattern.sub(rf"\g<1>{new_u:.6f}\g<3>", content)

        with open(u_file, 'w') as f:
            f.write(content)

    def run_particle_tracking(self, log_file=None, bin_config=None, turbulence=None, mesh_scaled_for_memory=False, **kwargs):
        """
        Runs particle tracking (Lagrangian) using a robust transient strategy on frozen flow.
        """
        if turbulence is None:
            turbulence = self.config.get('cfd_settings', {}).get('turbulence_model', 'laminar')
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
            self._generate_kinematicCloudProperties(bin_config, turbulence=turbulence)

            # Debug: print generated cloud config
            c_path = os.path.join(self.case_dir, "constant", "kinematicCloudProperties")
            if os.path.exists(c_path):
                 with open(c_path, 'r') as f:
                     print(f"--- Generated kinematicCloudProperties ---\n{f.read()}\n----------------------------------------")

            # 2. Reset Time & Prepare Fields
            self._prepare_transient_run(latest_time, turbulence=turbulence)

            # 3. Update Configurations
            self._update_controlDict_for_particles()
            self._switch_fvSchemes_to_transient()
            # Turbulence is KEPT ON for stochasticDispersionRAS

            # 4. Run Solver
            success = self.run_command(["icoUncoupledKinematicParcelFoam"], log_file=log_file, description="Particle Tracking", timeout=14400)

            c_path = os.path.join(self.case_dir, "constant", "kinematicCloudProperties")
            was_using_dispersion = False
            if os.path.exists(c_path):
                with open(c_path, 'r') as f:
                    if "stochasticDispersionRAS" in f.read():
                        was_using_dispersion = True

            if not success and was_using_dispersion:
                print("Particle tracking failed with dispersion. Attempting to recover by disabling dispersion model...")
                self._update_turbulence_properties("laminar")
                self._generate_kinematicCloudProperties(bin_config, turbulence="force_laminar_fallback")
                self._update_turbulence_properties("laminar")
                success = self.run_command(["icoUncoupledKinematicParcelFoam"], log_file=log_file, description="Particle Tracking (Recovery)", timeout=14400)

            return success

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
            'efficiency_by_bin': {},
            'injected_by_model': {}
        }

        target_log = log_file if log_file else self.log_file

        # 0. Check custom metrics defined in config
        if self.config and 'optimization' in self.config:
            extractors = self.config['optimization'].get('extractors', [])
            for ext in extractors:
                if ext.get('type') == 'surfaceFieldValue':
                    func_name = ext.get('function_name')
                    metric_name = ext.get('metric_name')
                    if func_name and metric_name:
                        val = self._read_latest_postProcessing(func_name)
                        if val is not None:
                            metrics[metric_name] = val
                # Implement other extractors as needed (e.g. log parsing regex)

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
            # In v2512, it's usually compact.

            # Let's try to find ANY mention of "bin_" and numbers.
            # If not found, we leave the dict empty.

            # Try to parse `particleCollector` file output if available (replaced patchPostProcessing)
            # Path: case/postProcessing/lagrangian/cloud/particleCollector1/*/particleCollector1.dat
            # pp_base = os.path.join(self.case_dir, "postProcessing", "lagrangian", "cloud", "particleCollector1")

            # Path: case/postProcessing/kinematicCloud/patchPostProcessing1/*/patchPostProcessing1.dat
            pp_base = os.path.join(self.case_dir, "postProcessing", "kinematicCloud", "patchPostProcessing1")

            if os.path.exists(pp_base):
                 # Find latest time
                 time_dirs = glob.glob(os.path.join(pp_base, "*"))
                 if time_dirs:
                     latest_pp_dir = max(time_dirs, key=os.path.getmtime)
                     dat_file = os.path.join(latest_pp_dir, "patchPostProcessing1.dat")
                     # dat_file = os.path.join(latest_pp_dir, "particleCollector1.dat")

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

        # Calculate Efficiency Per Bin (Percent)
        # Relies on total injected particles (sum of all models)
        total_injected = metrics.get('particles_injected', 0)

        # Ensure capture_by_bin exists
        if 'capture_by_bin' in metrics:
            for bin_name, count in metrics['capture_by_bin'].items():
                if total_injected > 0:
                    metrics['efficiency_by_bin'][bin_name] = (count / total_injected) * 100.0
                else:
                    metrics['efficiency_by_bin'][bin_name] = 0.0

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
