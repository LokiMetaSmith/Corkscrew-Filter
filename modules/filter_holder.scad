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
 * thread_inner: (bool) If true, adds threads to the inner lip (and uses face seal).
 * thread_outer: (bool) If true, adds threads to the outer lip (and uses face seal).
 * tube_wall: Wall thickness of the pipe (needed for flange calculation if threaded).
 */
module FilterHolder(
    tube_id = 30, // Fits inside this pipe
    cartridge_od = 10, // Holds this cartridge
    barb_od = 6.5,
    barb_id = 4,
    thread_inner = false,
    thread_outer = false,
    oring_cs = 1.5,
    tube_wall = 2
) {
    // Dimensions
    base_height = 5;
    lip_height = 10;

    // Derived
    // If threaded outer, we create a flange that sits on the pipe rim (Face Seal).
    // The flange must cover the pipe wall.
    base_plate_od = thread_outer ? (tube_id + 2 * max(tube_wall, 2)) : (tube_id - 0.2);

    outer_seal_od = thread_outer ? (tube_id - 2 * max(tube_wall, 2)) : tube_id - 0.2; // Tolerance for fit
    inner_seal_id = cartridge_od + 0.2; // Tolerance for fit

    // Thread/Seal Segmentation
    // Segment 1: Top (Proximal, near Base) -> z=5 to 10 relative to lip group origin (-5 to 0 global)
    // Segment 2: Bottom (Distal, Tip) -> z=0 to 5 relative to lip group origin (-10 to -5 global)
    segment_h = lip_height / 2;

    union() {
        // 1. Central Barb
        translate([0, 0, base_height])
        color("Blue", 1.0)
        Barb(
            hose_id = barb_id,
            hose_od = barb_od,
            barb_count = 3,
            wall_thickness = (barb_od - barb_id)/2,
            swell = 1
        );

        // 2. Main Body Plate
        difference() {
            color("Chartreuse", 1.0) cylinder(d = base_plate_od, h = base_height, $fn=$fn);
            // Center hole for flow
            translate([0,0,-1]) cylinder(d = barb_id, h = base_height + 2, $fn=$fn);

            // Face Seals
            if (thread_outer) {
                // Seal against Pipe Rim (Axial) on underside
                // Move O-ring to major diameter of the flange (minus seal thickness)
                rim_center = base_plate_od - oring_cs;
                // Use primitives.scad module
                OringGroove_Face_Cutter(rim_center, oring_cs);
            }

            if (thread_inner) {
                // Seal against Cartridge Rim (Axial) on underside (ceiling of hole)
                // Groove at cartridge_od
                OringGroove_Face_Cutter(cartridge_od, oring_cs);
            }
        }

        // 3. Seal Lips (Extending Downwards)
        translate([0, 0, -lip_height]) {
            difference() {
                union() {
                    // --- OUTER LIP CONSTRUCTION ---
                    if (thread_outer) {
                        // Thread the entire length
                        color("Orange", 1.0)translate([0,0,segment_h])
                        threaded_rod(d=tube_id, h=lip_height, pitch=1.5, internal=false, $fn=$fn);
                         
                    } else {
                        // Smooth Seal - Top Segment
                        translate([0,0,segment_h]) {
                             color("Orange", 1.0) difference() {
                                cylinder(d = outer_seal_od, h = segment_h, $fn=$fn);
                                translate([0,0,-1]) cylinder(d = outer_seal_od - 4, h = segment_h+2, $fn=$fn);
                            }
                        }
                        // Smooth Seal - Bottom Segment
                        color("Gold", 1.0) difference() {
                            cylinder(d = outer_seal_od, h = segment_h, $fn=$fn);
                            translate([0,0,-1]) cylinder(d = outer_seal_od - 4, h = segment_h+2, $fn=$fn);
                        }
                    }

                    // --- INNER LIP CONSTRUCTION ---
                    // Top Segment (Proximal/Base) - z=5 to 10
                    translate([0,0,segment_h]) {
                         // Provide material
                         color("Cyan", 1.0) cylinder(d = inner_seal_id + 4, h = segment_h, $fn=$fn);
                    }

                    // Bottom Segment (Distal/Tip) - z=0 to 5
                    // Provide material
                    color("Purple", 1.0) cylinder(d = inner_seal_id + 4, h = segment_h, $fn=$fn);


                    // Connecting Base (overlap with main body to ensure solid)
                    translate([0,0,lip_height-1])
                        color("Magenta", 1.0) cylinder(d = outer_seal_od, h = 1, $fn=$fn);
                }

                // --- SUBTRACTIONS (Holes, Threads, O-Rings) ---

                // 1. Hollow out the Outer Threaded Rod if it was added
                if (thread_outer) {
                     // The entire lip is threaded, need to hollow it.
                     // We must preserve the inner cup structure if it exists.
                     // Create a "donut" cut between outer wall ID and inner cup OD.

                     outer_cut_d = outer_seal_od - 4; // ID of outer threaded wall
                     inner_keep_d = inner_seal_id + 4; // OD of inner cup wall

                     if (outer_cut_d > inner_keep_d) {
                         translate([0,0,-1])
                         difference() {
                            cylinder(d = outer_cut_d, h = lip_height+2, $fn=$fn);
                            cylinder(d = inner_keep_d, h = lip_height+3, $fn=$fn); // Protect inner cup
                         }
                     }
                }

                // 2. Cut Inner Threads
                if (thread_inner) {
                     // Threads moved to Top Segment (Proximal)
                     translate([0,0,segment_h-1])
                        threaded_rod(d=inner_seal_id, h=segment_h+2, pitch=1.5, internal=true, $fn=$fn);
                }

                // Clear inner lip center (Smooth bore where not threaded)
                // If thread_inner, Bottom is smooth.
                // If !thread_inner, Both are smooth.
                // The material provided was cylinder(d=inner_seal_id + 4).
                // We need to cut the ID hole.

                if (thread_inner) {
                    // Cut bottom smooth bore
                    translate([0,0,-1]) cylinder(d = inner_seal_id, h = segment_h+2, $fn=$fn);
                } else {
                    // Cut both smooth bores
                     translate([0,0,-1]) cylinder(d = inner_seal_id, h = lip_height+2, $fn=$fn);
                }


                // 3. O-Ring Grooves (Radial)
                // Only if NOT threaded (Radial Seal)

                if (!thread_outer) {
                    // Outer O-Ring (Seals against Pipe ID) -> Groove on Top Segment
                    translate([0,0,segment_h + segment_h/2])
                        OringGroove_OD_Cutter(outer_seal_od, oring_cs);
                } else {
                     rim_center = base_plate_od - oring_cs;
                    translate([0,0,lip_height ])
                        OringGroove_OD_Cutter(rim_center, oring_cs);
                }

                if (!thread_inner) {
                    // Inner O-Ring (Seals against Cartridge OD) -> Groove on Top Segment
                    translate([0,0,segment_h + segment_h/2])
                        OringGroove_ID_Cutter(inner_seal_id, oring_cs);
                }

                // 4. Clear center flow path (for entire height)
                // Extend upwards to ensure overlap with base plate hole
                 translate([0,0,-1]) cylinder(d = barb_id, h = lip_height + 50, $fn=$fn);
            }

            // --- VISUALIZATION ---
            if (SHOW_O_RINGS) {
                 if (thread_outer) {
                      // Face Seal Visualization (Outer)
                      // Sits on the underside of the base plate (Global Z=0)
                      rim_center = base_plate_od - oring_cs;
                      translate([0, 0, lip_height])
                          OringVisualizer_Face(rim_center, oring_cs);
                 } else {
                     // Outer O-Ring (Radial)
                     translate([0,0,segment_h + segment_h/2])
                        OringVisualizer(outer_seal_od, oring_cs);
                 }

                 if (thread_inner) {
                     // Face Seal Visualization (Inner)
                     // Sits on the underside of the base plate (Global Z=0)
                     translate([0, 0, lip_height])
                        OringVisualizer_Face(cartridge_od, oring_cs);
                 } else {
                     // Inner O-Ring (Radial)
                     translate([0,0,segment_h + segment_h/2])
                        OringVisualizer_ID(inner_seal_id, oring_cs);
                 }
            }
        }
    }
}
