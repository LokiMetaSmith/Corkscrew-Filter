import subprocess
import os
import pytest

@pytest.mark.xfail(reason="Upstream CGAL bug in openscad-wasm when processing complex twisted intersections")
def test_single_cell_filter_cgal_error(tmp_path):
    """
    Test that reproducing single_cell_filter works without a
    CGAL precondition violation.
    This tracks the upstream issue.
    """
    scad_content = """
    include <config.scad>
    include <modules/primitives.scad>
    include <modules/core.scad>
    include <modules/cutters.scad>
    include <modules/helpers.scad>

    // Reproduce the core of single_cell_filter
    StagedHelicalStructure(cell_length, cell_diameter, num_helices, num_stages);
    """
    scad_path = tmp_path / "test_cgal_scf.scad"
    stl_path = tmp_path / "test_cgal_scf.stl"

    scad_path.write_text(scad_content)

    result = subprocess.run(["node", "export.js", "-o", str(stl_path), str(scad_path)], capture_output=True, text=True)

    # Check if the execution succeeded without the specific errors
    assert result.returncode == 0
    assert "CGAL error: precondition violation!" not in result.stderr
    assert "Expr: dimension() < 2" not in result.stderr

@pytest.mark.xfail(reason="Upstream CGAL bug in openscad-wasm processing complex differences before intersection")
def test_flat_end_screw_cgal_error(tmp_path):
    """
    Test that reproducing flat_end_screw works without
    a CGAL NFE / unclosed mesh error.
    """
    scad_content = """
    include <config.scad>
    include <modules/primitives.scad>
    include <modules/core.scad>
    include <modules/cutters.scad>
    include <modules/helpers.scad>

    h = 20;
    twist = 720;
    num_bins = 2;
    screw_outer_dia = 2 * (helix_path_radius_mm + helix_profile_radius_mm) * 1.2;

    intersection() {
        difference() {
            Corkscrew(h + 0.5, twist, void = false);
            CorkscrewSlitKnife(twist, h, num_bins);
        }
        cylinder(d = screw_outer_dia, h = h, center = true);
    }
    """
    scad_path = tmp_path / "test_cgal_fes.scad"
    stl_path = tmp_path / "test_cgal_fes.stl"

    scad_path.write_text(scad_content)

    result = subprocess.run(["node", "export.js", "-o", str(stl_path), str(scad_path)], capture_output=True, text=True)

    assert "ERROR: The given mesh is not closed" not in result.stderr
