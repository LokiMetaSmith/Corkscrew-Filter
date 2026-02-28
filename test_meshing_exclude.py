import os
import sys
import shutil

sys.path.append("optimizer")
from optimizer.foam_driver import FoamDriver

def _generate_snappyHexMeshDict_mod(self, stl_assets, add_layers=True):
    geometry_str = ""
    refinement_str = ""

    if not stl_assets: return

    for key, filename in stl_assets.items():
        if key == "fluid":
            continue

        patch_name = "corkscrew"
        if key == "inlet": patch_name = "inlet"
        elif key == "outlet": patch_name = "outlet"
        elif key == "wall": patch_name = "corkscrew"

        geometry_str += f"""
    {filename}
    {{
        type triSurfaceMesh;
        name {patch_name};
    }}
"""
        level = "(1 1)"
        patch_info = ""
        if key in ["inlet", "outlet"]:
            patch_info = f"""
            patchInfo
            {{
                type patch;
                inGroups ({patch_name}Group);
            }}"""

        refinement_str += f"""
        {patch_name}
        {{
            level {level};{patch_info}
        }}
"""

    template_path = os.path.join(self.case_dir, "system", "snappyHexMeshDict.template")
    with open(template_path, 'r') as f: content = f.read()

    content = content.replace("_ADD_LAYERS_FLAG_", "true" if add_layers else "false")
    content = self._replace_block(content, "geometry", geometry_str)
    content = self._replace_block(content, "refinementSurfaces", refinement_str)

    with open(os.path.join(self.case_dir, "system", "snappyHexMeshDict"), 'w') as f:
        f.write(content)

FoamDriver._generate_snappyHexMeshDict = _generate_snappyHexMeshDict_mod

foam_driver = FoamDriver("corkscrewFilter", num_processors=1)
assets = {'fluid': 'corkscrew_fluid.stl', 'inlet': 'inlet.stl', 'outlet': 'outlet.stl', 'wall': 'wall.stl'}
foam_driver._generate_snappyHexMeshDict(assets)
print("Done")
