import argparse
import sys
import re
from foam_driver import FoamDriver

def parse_openfoam_version(version_str):
    """
    Parses OpenFOAM version string (e.g., 'v2512') into an integer (2512).
    Returns None if parsing fails.
    """
    # Look for vYYMM format
    match = re.search(r"v(\d{4})", version_str)
    if match:
        return int(match.group(1))

    # Handle other potential formats (e.g., 'v2406')
    match = re.search(r"Version:\s*v(\d{4})", version_str)
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

    if not driver.has_tools:
        print("Error: OpenFOAM tools not found (neither native nor containerized).")
        sys.exit(1)

    # Run simpleFoam -help to get version
    # We use a temporary log file or capture output directly?
    # FoamDriver.run_command uses run_command_with_spinner which streams to file.
    # We can try to capture stdout by running subprocess directly via driver's method?
    # No, driver.run_command is high level.
    # Let's use driver._get_container_command if containerized, or just run subprocess if native.

    cmd = ["simpleFoam", "-help"]

    try:
        if driver.use_container:
            # Construct container command
            full_cmd = driver._get_container_command(cmd, driver.case_dir)
        else:
            full_cmd = cmd

        # Run and capture output
        import subprocess
        result = subprocess.run(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False # Don't throw error on non-zero exit (help often exits 0 or 1)
        )

        output = result.stdout

        # Parse version from output
        # Expecting: "OpenFOAM: The Open Source CFD Toolbox           | Version:  v2512"
        # or similar standard header

        version_int = parse_openfoam_version(output)

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

    except Exception as e:
        print(f"Error running version check: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
