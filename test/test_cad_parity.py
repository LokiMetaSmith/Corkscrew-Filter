import os
import sys
import pytest
import trimesh
import numpy as np

# Ensure sys.path includes optimizer directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'optimizer')))

from optimizer.scad_driver import ScadDriver
from optimizer.build123d_driver import Build123dDriver

@pytest.fixture
def tmp_output_dir(tmp_path):
    d = tmp_path / "cad_parity_test"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)

def compare_stl_geometry(stl1_path, stl2_path, volume_tol_percent=1.5, bounds_tol_percent=1.5):
    """
    Compares two STL files using trimesh to evaluate geometric parity.
    Returns (vol_diff_pct, bounds_diff_pct).
    """
    m1 = trimesh.load(stl1_path)
    m2 = trimesh.load(stl2_path)

    if isinstance(m1, trimesh.Scene):
        m1 = trimesh.util.concatenate(tuple(m1.geometry.values()))
    if isinstance(m2, trimesh.Scene):
        m2 = trimesh.util.concatenate(tuple(m2.geometry.values()))

    # Bounding box comparison
    b1_ext = m1.bounding_box.extents
    b2_ext = m2.bounding_box.extents

    bounds_diff_pct = np.max(np.abs(b1_ext - b2_ext) / np.maximum(b1_ext, 1e-6)) * 100.0

    # Volume comparison
    vol1 = abs(m1.volume)
    vol2 = abs(m2.volume)

    if vol1 > 1e-6:
        vol_diff_pct = abs(vol1 - vol2) / vol1 * 100.0
    else:
        vol_diff_pct = 0.0

    return vol_diff_pct, bounds_diff_pct

def test_dipole_antenna_parity(tmp_output_dir):
    params = {
        "length": 50.0,
        "thickness": 2.0,
        "gap": 2.0
    }
    scad_drv = ScadDriver("dipole_antenna.scad")
    b3d_drv = Build123dDriver("dipole_antenna.scad")

    scad_stl = os.path.join(tmp_output_dir, "dipole_scad.stl")
    b3d_stl = os.path.join(tmp_output_dir, "dipole_b3d.stl")

    assert scad_drv.generate_stl(params, scad_stl)
    assert b3d_drv.generate_stl(params, b3d_stl)

    vol_diff, bounds_diff = compare_stl_geometry(scad_stl, b3d_stl)
    print(f"Dipole Antenna - Vol Diff: {vol_diff:.2f}%, Bounds Diff: {bounds_diff:.2f}%")
    assert bounds_diff <= 1.5

def test_puck_antenna_parity(tmp_output_dir):
    params = {
        "puck_radius": 40.0,
        "puck_height": 15.0,
        "panel_radius": 35.0,
        "panel_thickness": 2.0,
        "panel_height_above_puck": 8.0,
        "num_antennas": 4,
        "antenna_length": 25.0,
        "antenna_width": 3.0,
        "antenna_thickness": 1.0
    }
    scad_drv = ScadDriver("puck_antenna.scad")
    b3d_drv = Build123dDriver("puck_antenna.scad")

    scad_stl = os.path.join(tmp_output_dir, "puck_scad.stl")
    b3d_stl = os.path.join(tmp_output_dir, "puck_b3d.stl")

    assert scad_drv.generate_stl(params, scad_stl)
    assert b3d_drv.generate_stl(params, b3d_stl)

    vol_diff, bounds_diff = compare_stl_geometry(scad_stl, b3d_stl)
    print(f"Puck Antenna - Vol Diff: {vol_diff:.2f}%, Bounds Diff: {bounds_diff:.2f}%")
    assert bounds_diff <= 1.5

def test_inlet_cap_parity(tmp_output_dir):
    params = {
        "tube_od_mm": 30.0,
        "tube_wall_mm": 2.0,
        "insert_length_mm": 60.0,
        "cfd_shape": "circle",
        "part_to_generate": "inlet_cap"
    }
    scad_drv = ScadDriver("corkscrew.scad")
    b3d_drv = Build123dDriver("corkscrew.scad")

    scad_stl = os.path.join(tmp_output_dir, "inlet_scad.stl")
    b3d_stl = os.path.join(tmp_output_dir, "inlet_b3d.stl")

    assert scad_drv.generate_stl(params, scad_stl)
    assert b3d_drv.generate_stl(params, b3d_stl)

    vol_diff, bounds_diff = compare_stl_geometry(scad_stl, b3d_stl)
    print(f"Inlet Cap - Vol Diff: {vol_diff:.2f}%, Bounds Diff: {bounds_diff:.2f}%")
    assert bounds_diff <= 1.5

def test_cfd_wall_parity(tmp_output_dir):
    params = {
        "tube_od_mm": 30.0,
        "tube_wall_mm": 2.0,
        "insert_length_mm": 60.0,
        "cfd_shape": "circle",
        "part_to_generate": "cfd_wall"
    }
    scad_drv = ScadDriver("corkscrew.scad")
    b3d_drv = Build123dDriver("corkscrew.scad")

    scad_stl = os.path.join(tmp_output_dir, "wall_scad.stl")
    b3d_stl = os.path.join(tmp_output_dir, "wall_b3d.stl")

    assert scad_drv.generate_stl(params, scad_stl)
    assert b3d_drv.generate_stl(params, b3d_stl)

    vol_diff, bounds_diff = compare_stl_geometry(scad_stl, b3d_stl)
    print(f"CFD Wall - Vol Diff: {vol_diff:.2f}%, Bounds Diff: {bounds_diff:.2f}%")
    assert bounds_diff <= 1.5
