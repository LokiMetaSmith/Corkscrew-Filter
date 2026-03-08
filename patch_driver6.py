import re

with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

search_block = """            # Robustly inject if missing due to prior corrupted files
            if "div(phi,k)" not in content and "divSchemes" in content:
                content = content.replace("divSchemes\\n{", "divSchemes\\n{\\n    div(phi,k)      bounded Gauss upwind;")
            if "div(phi,epsilon)" not in content and "divSchemes" in content:
                content = content.replace("divSchemes\\n{", "divSchemes\\n{\\n    div(phi,epsilon) bounded Gauss upwind;")

        elif turbulence == "kOmegaSST" or turbulence == "kOmegaSST_disabled":
            content = re.sub(r"div\(phi,R\).*?;", "", content)

            if "div(phi,k)" not in content and "divSchemes" in content:
                content = content.replace("divSchemes\\n{", "divSchemes\\n{\\n    div(phi,k)      bounded Gauss upwind;")
            if "div(phi,omega)" not in content and "divSchemes" in content:
                content = content.replace("divSchemes\\n{", "divSchemes\\n{\\n    div(phi,omega) bounded Gauss upwind;")"""

replace_block = """            # Robustly inject if missing due to prior corrupted files (handles Windows CRLF and arbitrary spacing)
            if "div(phi,k)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,k)      bounded Gauss upwind;", content, count=1)
            if "div(phi,epsilon)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,epsilon) bounded Gauss upwind;", content, count=1)

        elif turbulence == "kOmegaSST" or turbulence == "kOmegaSST_disabled":
            content = re.sub(r"div\(phi,R\).*?;", "", content)

            if "div(phi,k)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,k)      bounded Gauss upwind;", content, count=1)
            if "div(phi,omega)" not in content and "divSchemes" in content:
                content = re.sub(r"(divSchemes\s*\{)", r"\1\n    div(phi,omega) bounded Gauss upwind;", content, count=1)"""

content = content.replace(search_block, replace_block)

search_block2 = """        # If it failed, and we haven't applied fallback wall functions yet, try doing so to recover from unstable baseline!
        if not success and not mesh_scaled_for_memory:
            print("Solver failed on standard mesh. Attempting to recover by applying fallback wall functions...")
            self._apply_fallback_wall_functions()
            # Need to clean up potentially broken fields, simpleFoam will continue from latest time or 0
            # If it failed at Time 1, it might try to restart from 1.
            # We can just try executing again.
            success = _execute()"""

replace_block2 = """        # If it failed, and we haven't applied fallback wall functions yet, try doing so to recover from unstable baseline!
        if not success and not mesh_scaled_for_memory:
            print("Solver failed on standard mesh. Attempting to recover by applying fallback wall functions...")
            self._apply_fallback_wall_functions()

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

            success = _execute()"""

content = content.replace(search_block2, replace_block2)

with open("optimizer/foam_driver.py", "w") as f:
    f.write(content)
