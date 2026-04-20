import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix remaining single HEAD block.
# Wait, why is it just `<<<<<<< HEAD` without `======`? Because `pattern.sub` ate the rest!
# Let me just restore the file from git to undo the naive pattern match that broke the file structure and resolve properly.
