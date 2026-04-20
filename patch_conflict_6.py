import re

with open("optimizer/foam_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# The pattern `c5` replaced `<<<<<<< HEAD` with just the content and `=======\n.*?\n>>>>>>> origin/main`.
# Let's fix the file correctly again. Let's revert and do a manual pass.
