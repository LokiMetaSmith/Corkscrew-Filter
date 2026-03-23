with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "🚀 Attempt" in line:
        lines[i] = "            print(f\"\\n🚀 Attempt {i+1}: {strategy['name']}\")\n"
        print(f"Fixed string issue at line {i+1}")

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
