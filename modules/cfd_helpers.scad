// =============================================================================
// --- CFD Helper Modules ---
// =============================================================================
// This file contains modules for generating explicit CFD boundaries (inlet, outlet, walls)
// as separate STL files.

/**
 * Module: InletCap
 * Description: Generates a flat disk representing the inlet patch.
 * Arguments:
 * d: Diameter of the fluid domain (tube ID).
 * h: Length of the fluid domain.
 */
module InletCap(d, h) {
    // Positioned at the bottom (Z-) face
    // Thickness 0.5mm to ensure robust intersection with boundary faces
    translate([0, 0, -h/2])
        cylinder(d = d, h = 0.5, center = true);
}

/**
 * Module: OutletCap
 * Description: Generates a flat disk representing the outlet patch.
 * Arguments:
 * d: Diameter of the fluid domain (tube ID).
 * h: Length of the fluid domain.
 */
module OutletCap(d, h) {
    // Positioned at the top (Z+) face
    translate([0, 0, h/2])
        cylinder(d = d, h = 0.5, center = true);
}

/**
 * Module: CFDWall
 * Description: Generates a cylindrical shell representing the outer wall of the fluid domain.
 * This can be used to explicitly patch the tube walls.
 * Arguments:
 * d: Diameter of the fluid domain (tube ID).
 * h: Length of the fluid domain.
 */
module CFDWall(d, h) {
    wall_thickness = 1.0;
    difference() {
        cylinder(d = d + 2 * wall_thickness, h = h, center = true);
        cylinder(d = d, h = h + 1, center = true);
    }
}
