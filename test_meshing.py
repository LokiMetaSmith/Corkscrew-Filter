import os
import re

with open("corkscrewFilter/system/snappyHexMeshDict.template", "r") as f:
    content = f.read()

# Check what the script assumes about the geometry block
print(content)
