// =============================================================================
// --- Primitive Modules ---
// =============================================================================
// This file contains basic, reusable primitive shapes and tools.

// --- O-Ring Primitives (from corkscrew_filter_v40.scad) ---

/**
 * Module: OringGroove_OD_Cutter
 * Description: Creates a cutting tool for an O-ring groove on an outer cylindrical or flat surface.
 * Arguments:
 * object_dia: The diameter of the object to cut the groove into.
 * oring_cs:   The cross-section diameter of the O-ring.
 * flat:       (boolean) If true, creates a straight cutter for a flat face instead of a toroidal one.
 */
module OringGroove_OD_Cutter(object_dia, oring_cs, flat = false) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    cutter_dia = object_dia - 2 * groove_depth;
    if (flat) {
        translate([-object_dia / 2, -groove_width / 2, 0])
            cube([object_dia, groove_width, groove_depth]);
    }
    else {
        difference() {
            cylinder(d = object_dia + 0.2, h = groove_width, center = true);
            cylinder(d = cutter_dia, h = groove_width + 0.2, center = true);
        }
    }
}

/**
 * Module: OringVisualizer
 * Description: Renders a torus shape to represent an O-ring for visualization purposes.
 * Arguments:
 * object_dia: The diameter of the object the O-ring sits on.
 * oring_cs:   The cross-section diameter of the O-ring.
 */
module OringVisualizer(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    torus_radius = object_dia / 2 - groove_depth / 2;
    color("IndianRed") rotate_extrude(convexity = 10) translate([torus_radius, 0, 0]) circle(r = oring_cs / 2);
}

/**
 * Module: OringGroove_ID_Cutter
 * Description: Creates a cutting tool for an O-ring groove on an inner cylindrical surface.
 * Arguments:
 * object_id: The inner diameter of the object to cut the groove into.
 * oring_cs:  The cross-section diameter of the O-ring.
 */
module OringGroove_ID_Cutter(object_id, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    rotate_extrude(convexity = 10) translate([object_id / 2 + groove_depth / 2, 0, 0]) square([groove_depth, groove_width], center = true);
}


// --- Barb Primitives (from BarbGenerator-v3.scad by jsc, corrected implementation) ---

/**
 * Module: barbnotch
 * Description: Generates a single barb notch. This is the fundamental shape of the barb.
 * Arguments:
 * inside_diameter: The target inner diameter of the hose.
 */
module barbnotch( inside_diameter ) {
  // Generate a single barb notch. Note r1/r2 are swapped from v40 for correct geometry.
  cylinder( h = inside_diameter * 1.0, r1 = inside_diameter * 0.85 / 2, r2 = inside_diameter * 1.16 / 2, $fa = 0.5, $fs = 0.5 );
}

/**
 * Module: solidbarbstack
 * Description: Stacks multiple barbnotches to create the body of the barb.
 * Arguments:
 * inside_diameter: The target inner diameter of the hose.
 * count:           The number of barb notches to stack.
 */
module solidbarbstack( inside_diameter, count ) {
    union() {
      barbnotch( inside_diameter );
		for (i=[2:count]) {
			translate([0,0,(i-1) * inside_diameter * 0.9]) barbnotch( inside_diameter );
		}
    }
}

/**
 * Module: barb
 * Description: Creates a complete hose barb with an internal channel.
 * Arguments:
 * inside_diameter: The target inner diameter of the hose.
 * count:           The number of barb notches.
 */
module barb( inside_diameter, count ) {
  difference() {
    solidbarbstack( inside_diameter, count );
    translate([0,0,-0.3]) cylinder( h = inside_diameter * (count + 1), r = inside_diameter * 0.75 / 2, $fa = 0.5, $fs = 0.5 );
  }
}
