import re
import os

with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

# 1. Update run_command to support capture_output
old_run_command_def = """    def run_command(self, cmd, log_file=None, description="Processing", ignore_error=False, timeout=None):"""
new_run_command_def = """    def run_command(self, cmd, log_file=None, description="Processing", ignore_error=False, timeout=None, capture_output=False):"""
content = content.replace(old_run_command_def, new_run_command_def)

old_try_block = """        try:
            run_command_with_spinner(
                full_cmd,
                target_log,
                cwd=cwd,
                description=description,
                timeout=timeout
            )
            return True"""
new_try_block = """        try:
            output_str = ""
            if capture_output:
                # Use subprocess directly to capture output without spinner
                result = subprocess.run(
                    full_cmd,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout
                )
                output_str = result.stdout
                if result.returncode != 0 and not ignore_error:
                    print(f"\\nError executing {' '.join(cmd)}: {result.returncode}")
                    self._print_log_tail(target_log)
                    return False, output_str
                return True, output_str
            else:
                run_command_with_spinner(
                    full_cmd,
                    target_log,
                    cwd=cwd,
                    description=description,
                    timeout=timeout
                )
                return True"""

content = content.replace(old_try_block, new_try_block)

old_except_blocks = """        except subprocess.TimeoutExpired as e:
            if not ignore_error:
                print(f"\\nTimeout executing {' '.join(cmd)} after {timeout} seconds.")
                self._print_log_tail(target_log)
                return False
            return False
        except subprocess.CalledProcessError as e:
            if not ignore_error:
                print(f"\\nError executing {' '.join(cmd)}: {e}")
                self._print_log_tail(target_log)
                return False
            return False
        except Exception as e:
            if not ignore_error:
                print(f"\\nUnexpected error executing {' '.join(cmd)}: {e}")
                if self.verbose:
                    self._print_log_tail(target_log)
                return False
            return False"""
new_except_blocks = """        except subprocess.TimeoutExpired as e:
            if not ignore_error:
                print(f"\\nTimeout executing {' '.join(cmd)} after {timeout} seconds.")
                self._print_log_tail(target_log)
                return (False, "") if capture_output else False
            return (False, "") if capture_output else False
        except subprocess.CalledProcessError as e:
            if not ignore_error:
                print(f"\\nError executing {' '.join(cmd)}: {e}")
                self._print_log_tail(target_log)
                return (False, "") if capture_output else False
            return (False, "") if capture_output else False
        except Exception as e:
            if not ignore_error:
                print(f"\\nUnexpected error executing {' '.join(cmd)}: {e}")
                if self.verbose:
                    self._print_log_tail(target_log)
                return (False, "") if capture_output else False
            return (False, "") if capture_output else False"""

content = content.replace(old_except_blocks, new_except_blocks)

# 2. Add _run_checkMesh, _parse_mesh_quality, _classify_mesh
methods_to_add = """    def _run_checkMesh(self):
        success, output = self.run_command(
            ["checkMesh", "-allGeometry", "-allTopology"],
            capture_output=True
        )
        return output if success else ""

    def _parse_mesh_quality(self, output):
        def extract(pattern, default=0.0):
            m = re.search(pattern, output)
            return float(m.group(1)) if m else default

        return {
            "non_orth": extract(r"max non-orthogonality = ([\\d\\.]+)"),
            "skewness": extract(r"max skewness = ([\\d\\.]+)"),
            "min_vol": extract(r"min volume = ([\\deE\\+\\-\\.]+)", 1.0),
        }

    def _classify_mesh(self, q):
        if q["non_orth"] > 75 or q["skewness"] > 4:
            return "terrible"
        elif q["non_orth"] > 65 or q["skewness"] > 2.5:
            return "bad"
        elif q["non_orth"] > 50 or q["skewness"] > 1.5:
            return "moderate"
        else:
            return "good"

"""

# Insert methods before _update_fvSchemes
content = content.replace("    def _update_fvSchemes(self, turbulence):", methods_to_add + "    def _update_fvSchemes(self, turbulence):")

with open("optimizer/foam_driver.py", "w") as f:
    f.write(content)
