with open("optimizer/foam_driver.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if skip:
        skip = False
        continue
    if line.strip() == 'print(f"':
        if i + 1 < len(lines) and "Attempt {i+1}: {strategy['name']}\")" in lines[i+1]:
            new_lines.append("            print(f\"\\n🚀 Attempt {i+1}: {strategy['name']}\")\n")
            skip = True
            print(f"Fixed broken string at lines {i+1}-{i+2}")
            continue
    new_lines.append(line)

with open("optimizer/foam_driver.py", "w") as f:
    f.writelines(new_lines)
