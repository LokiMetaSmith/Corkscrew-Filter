with open("optimizer/foam_driver.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "with open(target_path, \"w\", newline='" in line:
        print(f"Fixing line {i+1}: {line.strip()}")
        # Fix unterminated string
        lines[i] = "        with open(target_path, \"w\", newline='\\n') as f:\n"

with open("optimizer/foam_driver.py", "w") as f:
    f.writelines(lines)
