import os

with open("corkscrewFilter/system/fvSolution", "r") as f:
    lines = f.readlines()

for line in lines:
    if "epsilon" in line:
        print(line.strip())
