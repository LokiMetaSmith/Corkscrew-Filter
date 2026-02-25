include <BOSL2/std.scad>

// =============================================================================
// --- CFD Helper Modules (BOSL2 Refactor) ---
// =============================================================================
// This file contains modules for generating explicit CFD boundaries (inlet, outlet, walls)
// as separate STL files. Supports cylindrical, square, and hexagonal profiles using
// BOSL2 attachments for robust alignment.

/**
 * Module: CFD_Reference_Shape
 * Description: Generates the reference fluid domain shape used for attaching caps.
 * This object is usually used as a phantom (%) parent.
 * Arguments:
 * d: Characteristic dimension (Diameter for circle/hex, Side for square).
 * h: Length of the fluid domain.
 * shape: "circle", "square", "hex"
 * anchor: BOSL2 anchor (default CENTER)
 */
module CFD_Reference_Shape(d, h, shape="circle", anchor=CENTER, spin=0, orient=UP) {
    if (shape == "square") {
        // cuboid takes size=[x,y,z]
        cuboid(size=[d, d, h], anchor=anchor, spin=spin, orient=orient);
    } else if (shape == "hex") {
        // cyl with $fn=6 is a hex prism
        // circum = true means d is the diameter of the circumcircle (corner-to-corner)
        // This matches standard cylinder(d=...) behavior for $fn=6 in OpenSCAD?
        // OpenSCAD cylinder(d=...) fits vertices to the circle.
        // BOSL2 cyl(d=...) does the same.
        cyl(d=d, h=h, $fn=6, anchor=anchor, spin=spin, orient=orient);
    } else {
        // circle
        cyl(d=d, h=h, anchor=anchor, spin=spin, orient=orient);
    }
}

/**
 * Module: CapGeometry
 * Description: The actual geometry of the cap (thin plate).
 */
module CapGeometry(d, shape="circle", thickness=0.5, anchor=CENTER, spin=0, orient=UP) {
    if (shape == "square") {
        cuboid(size=[d, d, thickness], anchor=anchor, spin=spin, orient=orient);
    } else if (shape == "hex") {
        cyl(d=d, h=thickness, $fn=6, anchor=anchor, spin=spin, orient=orient);
    } else {
        cyl(d=d, h=thickness, anchor=anchor, spin=spin, orient=orient);
    }
}

/**
 * Module: InletCap
 * Description: Generates the inlet patch attached to the BOTTOM of the fluid domain.
 */
module InletCap(d, h, shape="circle") {
    // Create the phantom fluid volume and attach the cap to its bottom
    %CFD_Reference_Shape(d, h, shape=shape)
        attach(BOTTOM)
            CapGeometry(d, shape=shape, thickness=0.5, anchor=CENTER); // anchor=CENTER aligns center of cap with bottom of fluid
            // Wait, attach(BOTTOM) puts the child at the bottom face.
            // If child anchor is CENTER, the child's center is at the parent's bottom face.
            // This means half the cap is inside, half outside.
            // Ideally, the patch surface is the interface.
            // If the fluid is -H/2 to H/2. Bottom is -H/2.
            // We want the cap face to be at -H/2.
            // If we use anchor=TOP for the cap, its TOP face touches the parent's BOTTOM face.
            // That places the cap strictly OUTSIDE (below) the fluid.
            // If we use anchor=BOTTOM, it's inside.
            // For CFD patches, we usually want the face itself.
            // SnappyHexMesh works best if the STL surface is exactly on the boundary.
            // A 0.5mm thick plate centered at the boundary is fine.
            // So anchor=CENTER is robust.
}

/**
 * Module: OutletCap
 * Description: Generates the outlet patch attached to the TOP of the fluid domain.
 */
module OutletCap(d, h, shape="circle") {
    %CFD_Reference_Shape(d, h, shape=shape)
        attach(TOP)
            CapGeometry(d, shape=shape, thickness=0.5, anchor=CENTER);
}

/**
 * Module: CFDWall
 * Description: Generates the outer wall shell.
 */
module CFDWall(d, h, shape="circle") {
    wall_thickness = 1.0;

    // Create a larger shell and subtract the inner reference shape
    // We can use diff() on the outer shape

    difference() {
        CFD_Reference_Shape(d + 2*wall_thickness, h, shape=shape);
        // Inner void (slightly taller to ensure clean cut)
        CFD_Reference_Shape(d, h + 1, shape=shape);
    }
}
