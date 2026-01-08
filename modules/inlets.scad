// =============================================================================
// --- Inlet Component Modules ---
// =============================================================================
// This file contains modules for creating different types of inlets for
// the filter assembly.

/**
 * Module: ThreadedInlet
 * Description: Creates a threaded inlet piece with a flange, designed to be added to an end spacer.
 * Note: This creates a cosmetic thread; for a functional thread, replace the inner
 * cylinder with a proper thread library module.
 */
module ThreadedInlet() {
    flange_height = 2;
    difference() {
        union() {
            cylinder(d = threaded_inlet_id_mm, h = threaded_inlet_height);
            cylinder(d = threaded_inlet_flange_od, h = flange_height);
        }
        translate([0, 0, -1])
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
            barb(inside_diameter = barb_inlet_id_mm, count = barb_inlet_count);
    }
}
