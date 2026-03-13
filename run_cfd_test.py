import os
import sys

sys.path.append("optimizer")
from optimizer.foam_driver import FoamDriver
import shutil

foam_driver = FoamDriver("corkscrewFilter", num_processors=1)
foam_driver.prepare_case(keep_mesh=False)
assets = {'fluid': 'corkscrew_fluid.stl', 'inlet': 'inlet.stl', 'outlet': 'outlet.stl', 'wall': 'wall.stl'}
# Check if files exist in corkscrewFilter/constant/triSurface
for k,v in assets.items():
    if not os.path.exists(f"corkscrewFilter/constant/triSurface/{v}"):
        with open(f"corkscrewFilter/constant/triSurface/{v}", "w") as f:
            f.write("solid\nendsolid\n")
foam_driver.run_meshing(log_file="test_meshing3.log", bin_config={"num_bins": 1}, stl_assets=assets, add_layers=False)
