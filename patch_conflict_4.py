import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Our regex failed because of exact string matching. Let's just rip out the conflict block.
pattern = re.compile(r"<<<<<<< HEAD\n=======\n.*?>>>>>>> origin/main\n", re.DOTALL)
content = pattern.sub(r"", content)

# Remove any lingering HEAD conflict markers that have other formats
pattern2 = re.compile(r"<<<<<<< HEAD\n(.*?)\n=======\n.*?\n>>>>>>> origin/main\n", re.DOTALL)

def replacer(match):
    return match.group(1) + "\n"

content = pattern2.sub(replacer, content)

with open("optimizer/foam_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
