import os
import subprocess
import glob
import sys

def main():
    source_dir = "configs"
    output_dir = "exports"

    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Find all SCAD files in the configs directory
    scad_files = glob.glob(os.path.join(source_dir, "*.scad"))

    if not scad_files:
        print(f"No .scad files found in {source_dir}")
        return

    print(f"Found {len(scad_files)} configuration files to export.")

    success_count = 0
    fail_count = 0

    for scad_file in scad_files:
        filename = os.path.basename(scad_file)
        name_no_ext = os.path.splitext(filename)[0]
        output_file = os.path.join(output_dir, f"{name_no_ext}.stl")

        print(f"\nProcessing: {scad_file} -> {output_file}")

        cmd = ["openscad", "-o", output_file, scad_file]

        try:
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("Success!")
            success_count += 1
        except subprocess.CalledProcessError as e:
            print(f"Error exporting {scad_file}:")
            print(f"Return code: {e.returncode}")
            print(f"Stderr: {e.stderr}")
            fail_count += 1
        except FileNotFoundError:
            print("Error: 'openscad' executable not found. Please install OpenSCAD and ensure it is in your PATH.")
            # If openscad is missing, no point in trying the rest
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            fail_count += 1

    print("\n--- Export Summary ---")
    print(f"Successfully exported: {success_count}")
    print(f"Failed: {fail_count}")

if __name__ == "__main__":
    main()
