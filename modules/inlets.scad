include <BOSL2/std.scad>
include <BOSL2/threading.scad>
include <barbs.scad>

// =============================================================================
// --- Inlet Component Modules ---
// =============================================================================
// This file contains modules for creating different types of inlets for
// the filter assembly.

/**
 * Module: ThreadedInlet
 * Description: Creates a threaded inlet piece with a flange, designed to be added to an end spacer.
 * Note: This creates a functional thread using BOSL2 threaded_rod.
 */
module ThreadedInlet() {
    flange_height = 2;
    difference() {
        union() {
            threaded_rod(d = threaded_inlet_id_mm, l = threaded_inlet_height, pitch = 1, anchor = BOTTOM, $fn=$fn);
            cylinder(d = threaded_inlet_flange_od, h = flange_height);
        }
        down(1)
            cylinder(d = threaded_inlet_id_mm - 2, h = threaded_inlet_height + 2);
    }
}

/**
 * Module: BarbInlet
 * Description: Creates a hose barb inlet with a flange, designed to be added to an end spacer.
 */
module BarbInlet() {
    flange_height = 2;
    union(){
        // Flange at the base
        difference(){
            cylinder(d = barb_inlet_flange_od, h = flange_height);
            translate([0, 0, -0.1])
                cylinder(d = barb_inlet_id_mm-1, h = flange_height+0.5);
        }
        // Barb itself, starting on top of the flange
        translate([0, 0, flange_height])
             Barb(
                hose_id = barb_inlet_id_mm,
                hose_od = barb_inlet_id_mm + 1.5, // Simple default logic or parameterized
                barb_count = barb_inlet_count,
                barb_length = 3, // Default length
                swell = 1,
                wall_thickness = 1,
                bore = true,
                shell = true
             );
    }
}
