import os
import sys

sys.path.append("optimizer")
from optimizer.foam_driver import FoamDriver

# simulate failed _check_boundary_patches
foam_driver = FoamDriver("corkscrewFilter", num_processors=1)
# Create dummy files
os.makedirs("corkscrewFilter/constant/polyMesh", exist_ok=True)
with open("corkscrewFilter/constant/polyMesh/boundary", "w") as f:
    f.write("""
inlet
{
    nFaces 10;
}
outlet
{
    nFaces 10;
}
""")

print("boundary check:", foam_driver._check_boundary_patches())
