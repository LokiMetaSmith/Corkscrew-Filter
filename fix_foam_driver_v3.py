with open("optimizer/foam_driver.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "print(f\"" in line and "\\n🚀 Attempt {i+1}: {strategy['name']}\")" not in line and "print(f\"" == line.strip():
        print(f"Fixing line {i+1}: {line.strip()}")
        if i+1 < len(lines):
             print(f"Next line: {lines[i+1]}")

    if "print(f\"\\n🚀 Attempt {i+1}: {strategy['name']}\")" in line:
        pass # this is fine
    elif line.strip().startswith("print(f\"") and not line.strip().endswith("\")"):
        print(f"Found issue at line {i+1}: {line.strip()}")
        lines[i] = "            print(f\"\\n🚀 Attempt {i+1}: {strategy['name']}\")\n"

with open("optimizer/foam_driver.py", "w") as f:
    f.writelines(lines)
