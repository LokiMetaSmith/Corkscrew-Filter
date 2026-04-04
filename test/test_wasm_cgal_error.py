import subprocess
import os

def test_single_cell_filter_cgal_error():
    """
    Test that reproducing single_cell_filter triggers the known
    CGAL precondition violation in openscad-wasm.
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
    with open("test_cgal_scf.scad", "w") as f:
        f.write(scad_content)

    result = subprocess.run(["node", "export.js", "-o", "test_cgal_scf.stl", "test_cgal_scf.scad"], capture_output=True, text=True)

    # Cleanup
    if os.path.exists("test_cgal_scf.scad"):
        os.remove("test_cgal_scf.scad")
    if os.path.exists("test_cgal_scf.stl"):
        os.remove("test_cgal_scf.stl")

    assert result.returncode != 0
    assert "CGAL error: precondition violation!" in result.stderr
    assert "Expr: dimension() < 2" in result.stderr

def test_flat_end_screw_cgal_error():
    """
    Test that reproducing flat_end_screw triggers the known
    CGAL NFE / unclosed mesh error in openscad-wasm.
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
    with open("test_cgal_fes.scad", "w") as f:
        f.write(scad_content)

    result = subprocess.run(["node", "export.js", "-o", "test_cgal_fes.stl", "test_cgal_fes.scad"], capture_output=True, text=True)

    # Cleanup
    if os.path.exists("test_cgal_fes.scad"):
        os.remove("test_cgal_fes.scad")
    if os.path.exists("test_cgal_fes.stl"):
        os.remove("test_cgal_fes.stl")

    # In my bash tests, FlatEndScrew actually returns 0 (Success) but prints
    # 'ERROR: The given mesh is not closed!' in stderr and generates a broken STL.
    # We check for the specific error string.
    assert "ERROR: The given mesh is not closed" in result.stderr
