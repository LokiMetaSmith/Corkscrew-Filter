with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line == "    def _execute_simpleFoam(self, return_output=False, log_file=None, solve_procs=1, solve_method=\"scotch\"):\n":
        print("Found _execute_simpleFoam")
    new_lines.append(line)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
