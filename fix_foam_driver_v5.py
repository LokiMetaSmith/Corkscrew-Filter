with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if skip:
        skip = False
        continue
    if "print(f\"" in line and "Attempt" not in line and "{" not in line and line.strip() == "print(f\"":
        if i + 1 < len(lines) and "Attempt" in lines[i+1]:
            new_lines.append("            print(f\"\\n🚀 Attempt {i+1}: {strategy['name']}\")\n")
            skip = True
            continue
    new_lines.append(line)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
