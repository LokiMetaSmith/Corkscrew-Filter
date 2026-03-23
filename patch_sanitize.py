import re

with open("optimizer/foam_driver.py", "r") as f:
    content = f.read()

sanitize_func = """    def _sanitize_fields(self, turbulence):
        zero_dir = os.path.join(self.case_dir, "0")

        def fix_internal_field(file, min_val):
            path = os.path.join(zero_dir, file)
            if not os.path.exists(path):
                return

            with open(path, "r") as f:
                content = f.read()

            import re

            content = re.sub(
                r"internalField\\s+uniform\\s+([-\\deE\\.]+);",
                lambda m: f"internalField uniform {max(float(m.group(1)), min_val)};",
                content
            )

            with open(path, "w") as f:
                f.write(content)

        if turbulence != "laminar":
            fix_internal_field("k", 1e-6)
            fix_internal_field("epsilon", 1e-6)
            fix_internal_field("omega", 1e-6)
            fix_internal_field("nut", 1e-7)

"""

# Insert _sanitize_fields before _execute_simpleFoam or run_solver
# Finding the position of def run_solver(self,
pos = content.find("    def run_solver(self")
if pos != -1:
    content = content[:pos] + sanitize_func + content[pos:]

with open("optimizer/foam_driver.py", "w") as f:
    f.write(content)
