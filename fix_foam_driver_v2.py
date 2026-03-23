with open("optimizer/foam_driver.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if ") as f:\n" in line and "'" in line and "newline=" not in line and "target_path" in lines[i-1]:
        print(f"Fixing line {i+1}: {line.strip()}")
        # Replace the multi-line split
        lines[i-1] = "        with open(target_path, \"w\", newline='\\n') as f:\n"
        lines[i] = ""

with open("optimizer/foam_driver.py", "w") as f:
    f.writelines(lines)
