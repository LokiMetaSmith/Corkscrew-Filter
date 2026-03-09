with open("corkscrewFilter/system/fvSchemes", "r") as f:
    lines = f.readlines()

for line in lines:
    if "div(phi," in line:
        print(line.strip())
