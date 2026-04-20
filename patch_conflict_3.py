import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the remaining conflicts that belong to fvSchemes appending and fvSolution
pat1 = re.compile(r"<<<<<<< HEAD\n=======\n        if not os\.path\.exists\(target_path\): return.*?\n        with open\(target_path, 'w', newline='\\n'\) as f:\n            f\.write\(cleaned \+ \"\\n\"\)\n\n        # If we had to synthesize the file from scratch because template was corrupted, save it\n        if not os\.path\.exists\(template_path\):\n            shutil\.copy2\(target_path, template_path\)\n\n        return turbulence\n\n    def _update_fvSolution\(self, turbulence, cfd_settings=None, relaxation_override=None\):\n>>>>>>> origin/main\n", re.DOTALL)
content = pat1.sub(r'', content)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
