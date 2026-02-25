// =============================================================================
// --- CFD Helper Modules ---
// =============================================================================
// This file contains modules for generating explicit CFD boundaries (inlet, outlet, walls)
// as separate STL files. Supports cylindrical, square, and hexagonal profiles.

/**
 * Module: CapShape
 * Description: Generates the 2D profile for the cap.
 */
module CapShape(d, shape="circle") {
    if (shape == "square") {
        square([d, d], center=true);
    } else if (shape == "hex") {
        // cylinder with $fn=6 creates a hexagon.
        // d is usually corner-to-corner diameter if using cylinder(d=...)
        circle(d=d, $fn=6);
    } else {
        circle(d=d);
    }
}

/**
 * Module: InletCap
 * Description: Generates a flat disk/plate representing the inlet patch.
 * Arguments:
 * d: Characteristic dimension (Diameter for circle/hex, Side for square).
 * h: Length of the fluid domain.
 * shape: "circle", "square", "hex"
 */
module InletCap(d, h, shape="circle") {
    // Positioned at the bottom (Z-) face
    translate([0, 0, -h/2])
        linear_extrude(height=0.5, center=true)
            CapShape(d, shape);
}

/**
 * Module: OutletCap
 * Description: Generates a flat disk/plate representing the outlet patch.
 * Arguments:
 * d: Characteristic dimension.
 * h: Length of the fluid domain.
 * shape: "circle", "square", "hex"
 */
module OutletCap(d, h, shape="circle") {
    // Positioned at the top (Z+) face
    translate([0, 0, h/2])
        linear_extrude(height=0.5, center=true)
            CapShape(d, shape);
}

/**
 * Module: CFDWall
 * Description: Generates a shell representing the outer wall of the fluid domain.
 * Arguments:
 * d: Characteristic dimension (Inner size).
 * h: Length of the fluid domain.
 * shape: "circle", "square", "hex"
 */
module CFDWall(d, h, shape="circle") {
    wall_thickness = 1.0;

    // Outer dimension depends on shape to maintain wall thickness
    // For circle: d + 2*t
    // For square: d + 2*t (side)
    // For hex: d is diam (corner-to-corner).

    difference() {
        linear_extrude(height=h, center=true)
            CapShape(d + 2*wall_thickness, shape);

        linear_extrude(height=h + 1, center=true)
            CapShape(d, shape);
    }
}
