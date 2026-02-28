import os
import sys

sys.path.append("optimizer")
from optimizer.foam_driver import FoamDriver

foam_driver = FoamDriver("corkscrewFilter", num_processors=1)
assets = {'fluid': 'corkscrew_fluid.stl', 'inlet': 'inlet.stl', 'outlet': 'outlet.stl', 'wall': 'wall.stl'}
foam_driver._generate_snappyHexMeshDict(assets)
print("Done")
