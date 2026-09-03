import glob

# Check where tests expect SCAD files to be.
for file in glob.glob("test/*.py"):
    with open(file, "r") as f:
        content = f.read()
    if "corkscrew.scad" in content:
        print(f"Found corkscrew.scad hardcoded in {file}")
