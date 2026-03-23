with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "Attempt" in line and "strategy['name']" in line:
        if i > 0 and lines[i-1].strip() == "print(f\"\\n🚀 Attempt {i+1}: {strategy['name']}\")":
            continue
        new_lines.append("            print(f\"\\n🚀 Attempt {i+1}: {strategy['name']}\")\n")
    else:
        new_lines.append(line)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
