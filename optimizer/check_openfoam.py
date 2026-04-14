import argparse
import sys
import os
import re
from foam_driver import FoamDriver

def parse_openfoam_version(version_str):
    """
    Parses OpenFOAM version string (e.g., 'v2512') into an integer (2512).
    Returns None if parsing fails.
    """
    # Try multiple patterns to handle different OpenFOAM forks and outputs
    patterns = [
        r"Version:\s*v?(\d{4})",       # Version: v2512 or Version: 2206
        r"OPENFOAM=v?(\d{4})",         # OPENFOAM=2206
        r"WM_PROJECT_VERSION=v?(\d{4})", # WM_PROJECT_VERSION=v2512
        r"v(\d{4})"                    # Fallback generic v2512
    ]
    for pattern in patterns:
        match = re.search(pattern, version_str)
        if match:
            return int(match.group(1))
    return None

def main():
    parser = argparse.ArgumentParser(description="Check OpenFOAM Version")
    # Add relevant arguments from main.py to handle shared flags correctly
    parser.add_argument("--case-dir", type=str, default="corkscrewFilter", help="Path to OpenFOAM case directory")
    parser.add_argument("--container-engine", type=str, default="auto", choices=["auto", "podman", "docker"], help="Force specific container engine")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual OpenFOAM execution (mocks everything)")
    parser.add_argument("--skip-cfd", action="store_true", help="Generate geometry but skip CFD simulation")

    # Parse known args to ignore others (like --iterations, --scad-file)
    args, unknown = parser.parse_known_args()

    if args.dry_run or args.skip_cfd:
        print("Skipping OpenFOAM version check due to --dry-run or --skip-cfd.")
        return

    print("Checking OpenFOAM version...")

    # Initialize driver to use its environment detection
    driver = FoamDriver(args.case_dir, container_engine=args.container_engine)

    try:
        if not driver.has_tools:
            print("Error: OpenFOAM tools not found (neither native nor containerized).")
            sys.exit(1)

        # Ensure the case directory exists before mounting it in the container
        os.makedirs(driver.case_dir, exist_ok=True)

        # Run simpleFoam -help to get version
        # We use a temporary log file or capture output directly?
        # FoamDriver.run_command uses run_command_with_spinner which streams to file.
        # We can try to capture stdout by running subprocess directly via driver's method?
        # No, driver.run_command is high level.
        # Let's use driver._get_container_command if containerized, or just run subprocess if native.

        # We will try a few commands to extract the version, as `-help` often strips the header in newer versions.
        cmds_to_try = [
            ["simpleFoam", "-help"],
            ["foamVersion"],
            ["bash", "-c", "echo WM_PROJECT_VERSION=$WM_PROJECT_VERSION"]
        ]

        version_int = None
        output = ""

        import subprocess

        for cmd in cmds_to_try:
            try:
                if driver.use_container:
                    # Construct container command
                    full_cmd = driver._get_container_command(cmd, driver.case_dir)
                else:
                    full_cmd = cmd

                # Run and capture output
                result = subprocess.run(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False # Don't throw error on non-zero exit
                )

                current_output = result.stdout
                output += current_output + "\n"
                version_int = parse_openfoam_version(current_output)

                if version_int:
                    break
            except Exception as e:
                output += f"Error running {' '.join(cmd)}: {e}\n"
                continue

        if version_int:
            print(f"Detected OpenFOAM version: v{version_int}")
            if version_int < 2512:
                print(f"Error: OpenFOAM version v{version_int} is older than required v2512.")
                sys.exit(1)
            else:
                print("OpenFOAM version check passed.")
        else:
            print("Warning: Could not parse OpenFOAM version from output.")
            # Print head of output for debug
            print("Output head:")
            print("\n".join(output.splitlines()[:10]))
            # strict check requested? "make sure its 2512"
            # If we can't determine, maybe fail?
            # Let's fail to be safe as per "stop execution" requirement.
            print("Error: Unable to verify OpenFOAM version.")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        print(f"Error running version check: {e}")
        sys.exit(1)
    finally:
        driver.cleanup_ram_disk()

if __name__ == "__main__":
    main()
