include <BOSL2/std.scad>
include <BOSL2/threading.scad>
include <barbs.scad>
include <primitives.scad>

/**
 * Module: FilterHolder
 * Description: A barb fitting with dual O-ring grooves (inner and outer) to hold a filter cartridge
 * inside a pipe/bin.
 *
 * Parameters:
 * tube_id: Inner diameter of the main pipe/bin (outer seal surface).
 * cartridge_od: Outer diameter of the filter cartridge (inner seal surface).
 * barb_od: Outer diameter of the barb.
 * barb_id: Inner diameter of the barb.
 * thread_inner: (bool) If true, adds threads to the inner lip.
 * thread_outer: (bool) If true, adds threads to the outer lip.
 */
module FilterHolder(
    tube_id = 30, // Fits inside this pipe
    cartridge_od = 10, // Holds this cartridge
    barb_od = 6.5,
    barb_id = 4,
    thread_inner = false,
    thread_outer = false,
    oring_cs = 1.5
) {
    // Dimensions
    base_height = 5;
    lip_height = 10;

    // Derived
    outer_seal_od = tube_id - 0.2; // Tolerance for fit
    inner_seal_id = cartridge_od + 0.2; // Tolerance for fit

    // Thread/Seal Segmentation
    // We assume the lip is split:
    // - Distal half (farthest from base): O-Ring Seal
    // - Proximal half (closest to base): Threading (if enabled)
    segment_h = lip_height / 2;

    union() {
        // 1. Central Barb
        translate([0, 0, base_height])
        Barb(
            hose_id = barb_id,
            hose_od = barb_od,
            barb_count = 3,
            wall_thickness = (barb_od - barb_id)/2,
            swell = 1
        );

        // 2. Main Body Plate
        difference() {
            cylinder(d = outer_seal_od, h = base_height, $fn=$fn);
            // Center hole for flow
            translate([0,0,-1]) cylinder(d = barb_id, h = base_height + 2, $fn=$fn);
        }

        // 3. Seal Lips (Extending Downwards)
        translate([0, 0, -lip_height]) {
            difference() {
                union() {
                    // --- OUTER LIP CONSTRUCTION ---
                    // Distal Segment (Seal) - Always Smooth
                    translate([0,0,segment_h])
                        difference() {
                            cylinder(d = outer_seal_od, h = segment_h, $fn=$fn);
                            translate([0,0,-1]) cylinder(d = outer_seal_od - 4, h = segment_h+2, $fn=$fn);
                        }

                    // Proximal Segment (Base)
                    if (thread_outer) {
                        // Threaded Rod (replaces smooth cylinder)
                         threaded_rod(d=outer_seal_od, h=segment_h, pitch=1.5, internal=false, $fn=$fn);
                         // Note: threaded_rod is solid, need to hollow it out
                    } else {
                        // Smooth Cylinder
                         difference() {
                            cylinder(d = outer_seal_od, h = segment_h, $fn=$fn);
                            translate([0,0,-1]) cylinder(d = outer_seal_od - 4, h = segment_h+2, $fn=$fn);
                        }
                    }

                    // --- INNER LIP CONSTRUCTION ---
                    // Distal Segment (Seal) - Always Smooth
                    translate([0,0,segment_h])
                        difference() {
                            cylinder(d = inner_seal_id + 4, h = segment_h, $fn=$fn);
                            translate([0,0,-1]) cylinder(d = inner_seal_id, h = segment_h+2, $fn=$fn);
                        }

                    // Proximal Segment (Base)
                    if (thread_inner) {
                         // We cut the thread later in the difference block, so here we provide material.
                         // Standard material block
                         cylinder(d = inner_seal_id + 4, h = segment_h, $fn=$fn);
                    } else {
                        // Smooth Cylinder
                        difference() {
                            cylinder(d = inner_seal_id + 4, h = segment_h, $fn=$fn);
                            translate([0,0,-1]) cylinder(d = inner_seal_id, h = segment_h+2, $fn=$fn);
                        }
                    }

                    // Connecting Base (overlap with main body to ensure solid)
                    translate([0,0,lip_height-1])
                        cylinder(d = outer_seal_od, h = 1, $fn=$fn);
                }

                // --- SUBTRACTIONS (Holes, Threads, O-Rings) ---

                // 1. Hollow out the Outer Threaded Rod if it was added (it's solid by default)
                if (thread_outer) {
                     translate([0,0,-1]) cylinder(d = outer_seal_od - 4, h = segment_h+2, $fn=$fn);
                }

                // 2. Cut Inner Threads
                if (thread_inner) {
                     translate([0,0,-1])
                        threaded_rod(d=inner_seal_id, h=segment_h+2, pitch=1.5, internal=true, $fn=$fn);
                }

                // 3. O-Ring Grooves (Distal Segment)
                // Outer O-Ring (Seals against Pipe ID) -> Groove on OD of Outer Lip
                translate([0,0,segment_h + segment_h/2])
                    OringGroove_OD_Cutter(outer_seal_od, oring_cs);

                // Inner O-Ring (Seals against Cartridge OD) -> Groove on ID of Inner Lip
                translate([0,0,segment_h + segment_h/2])
                    OringGroove_ID_Cutter(inner_seal_id, oring_cs);

                // 4. Clear center flow path (for entire height)
                 translate([0,0,-1]) cylinder(d = barb_id, h = lip_height + 2, $fn=$fn);
            }
        }
    }
}
