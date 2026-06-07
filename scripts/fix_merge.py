import re

filepath = 'optimizer/foam_driver.py'

with open(filepath, 'r') as f:
    content = f.read()

# Let's check if there are any merge conflict markers left in the file
if '<<<<<<<' in content or '=======' in content or '>>>>>>>' in content:
    print("Found merge conflict markers in foam_driver.py")
else:
    print("No merge conflict markers found in foam_driver.py")

