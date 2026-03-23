import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# I will find the remaining conflict blocks and resolve them directly by extracting HEAD content.
pattern = re.compile(r"<<<<<<< HEAD\n(.*?)\n=======\n.*?\n>>>>>>> origin/main\n", re.DOTALL)

def replacer(match):
    # Keep the HEAD version completely for these conflicts,
    # as they represent our improved `_sanitize_fields` and `_run_checkMesh` logic that we built previously.
    # The `main` branch attempts to inject a simpler `_run_checkMesh` right here, but ours is already defined earlier.
    return match.group(1) + "\n"

content = pattern.sub(replacer, content)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
