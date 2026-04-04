// =============================================================================
// --- Core Geometry Modules ---
// =============================================================================
// This file contains the most fundamental modules for generating the
// helical shapes.

/**
 * Module: HelicalShape
 * Description: The fundamental building block for the helical screw. It generates a helical
 * shape by extruding an elliptical profile along a twisted path.
 * Arguments:
 * h:         The height of the helical extrusion.
 * twist:     The total twist angle in degrees over the height `h`.
 * path_r:    The radius of the helical path from the central axis.
 * profile_r: The base radius of the circular profile before it's scaled into an ellipse.
 */
module HelicalShape(h, twist, path_r, profile_r) {
    $fn = $preview ? 32 : 128;
    linear_extrude(height = h, center = true, convexity = 10, twist = twist) {
        // Create the main elliptical profile
        // and a fillet that connects it smoothly to the central axis (r=0)
        union() {
            translate([path_r, 0, 0]) {
                scale([1, helix_profile_scale_ratio]) {
                    circle(r = profile_r);
                }
            }
            translate([path_r / 2, 0, 0]) {
                square([path_r, profile_r], center=true);
            }
        }
    }
}

/**
 * Module: Corkscrew
 * Description: A wrapper for `HelicalShape` that creates either the solid part of the screw
 * or the void (the internal channel, used as a cutting tool).
 * Arguments:
 * h:     The height of the corkscrew.
 * twist: The total twist angle in degrees.
 * void:  (boolean) If false, generates the solid screw. If true, generates the larger void for cutting.
 */
module Corkscrew(h, twist, void = false) {
    // Enforce safety margin mathematically to avoid center-axis singularity in CGAL
    safe_profile_radius = min(helix_profile_radius_mm, helix_path_radius_mm - 0.5);

    profile_r = void
        ? helix_void_profile_radius_mm + tolerance_channel
        : safe_profile_radius;
    HelicalShape(h, twist, helix_path_radius_mm, profile_r);
}

/**
 * Module: HollowHelicalShape
 * Description: Generates a hollow helical extrusion (tube) by subtracting an inner profile from an outer profile
 * before extrusion. This is much more efficient than 3D boolean differences.
 * Arguments:
 * h:         The height of the helical extrusion.
 * twist:     The total twist angle in degrees over the height `h`.
 * path_r:    The radius of the helical path from the central axis.
 * outer_r:   The base radius of the outer circular profile.
 * inner_r:   The base radius of the inner circular profile.
 */
module HollowHelicalShape(h, twist, path_r, outer_r, inner_r) {
    $fn = $preview ? 32 : 128;
    linear_extrude(height = h, center = true, convexity = 10, twist = twist) {
        difference() {
            union() {
                translate([path_r, 0, 0]) scale([1, helix_profile_scale_ratio]) circle(r = outer_r);
                translate([path_r / 2, 0, 0]) {
                    square([path_r, outer_r], center=true);
                }
            }
            translate([path_r, 0, 0]) scale([1, helix_profile_scale_ratio]) circle(r = inner_r);
        }
    }
}
