import os
import shutil
import tempfile
import trimesh
import numpy as np
import sys

# Add optimizer to path
sys.path.append(os.path.abspath("optimizer"))

from scad_driver import ScadDriver
from foam_driver import FoamDriver

def test_internal_point_and_location_update():
    # 1. Setup temp directory
    tmp_dir = tempfile.mkdtemp()
    try:
        stl_path = os.path.join(tmp_dir, "test.stl")

        # 2. Create a dummy STL (Box from -10 to 10)
        mesh = trimesh.creation.box(extents=(20, 20, 20))
        # Make it a solid box.
        mesh.export(stl_path)

        # 3. Test ScadDriver.get_internal_point
        # Mock ScadDriver (we don't need real scad file)
        scad_driver = ScadDriver("dummy.scad")

        point = scad_driver.get_internal_point(stl_path)
        print(f"Internal point found: {point}")

        assert point is not None, "Failed to find internal point"
        assert len(point) == 3
        # Check if point is inside [-10, 10]
        # Since extents are 20, bounds are -10 to 10.
        for coord in point:
            assert -10.0 <= coord <= 10.0

        # 4. Test FoamDriver.update_snappyHexMesh_location
        # Need a dummy case directory structure
        case_dir = os.path.join(tmp_dir, "case")
        os.makedirs(os.path.join(case_dir, "system"))

        # Create dummy snappyHexMeshDict
        shm_path = os.path.join(case_dir, "system", "snappyHexMeshDict")
        with open(shm_path, "w") as f:
            f.write("Some config;\nlocationInMesh (0 0 0);\nMore config;")

        foam_driver = FoamDriver(case_dir)

        # Update with our point using new signature
        foam_driver.update_snappyHexMesh_location(None, custom_location=point)

        # Check file content
        with open(shm_path, "r") as f:
            content = f.read()

        print(f"Updated snappyHexMeshDict content:\n{content}")

        expected_str = f"locationInMesh ({point[0]:.4f} {point[1]:.4f} {point[2]:.4f});"
        assert expected_str in content, f"Expected '{expected_str}' in content"

        print("Test passed!")

    finally:
        shutil.rmtree(tmp_dir)

if __name__ == "__main__":
    test_internal_point_and_location_update()
