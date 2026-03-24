from optimizer.foam_driver import FoamDriver
import os

d = FoamDriver("test_case")
os.makedirs("test_case/0", exist_ok=True)
os.makedirs("test_case/system", exist_ok=True)
os.makedirs("test_case/constant", exist_ok=True)
d._generate_decomposeParDict(num_processors=4, method="scotch")
with open("test_case/system/decomposeParDict", "r") as f:
    print(f.read())
