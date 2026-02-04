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
 * cartridge_thread_inner: (bool) If true, adds internal threads (Socket) for the cartridge.
 * cartridge_thread_outer: (bool) If true, adds external threads (Nipple) for the cartridge.
 * tube_thread_inner: (bool) If true, adds internal threads (Cap) for the tube (fits over tube).
 * tube_thread_outer: (bool) If true, adds external threads (Plug) for the tube (fits inside tube).
 * tube_wall: Wall thickness of the pipe (needed for flange calculation if threaded).
 * use_colors: (bool) If true, applies distinct colors to sub-parts for visualization.
 * cartridge_wall_height: (float) Height of the cartridge holder rim/screw.
 * cartridge_offset: (float) Height offset from the base for the cartridge holder.
 */
module FilterHolder(
    tube_id = 30, // Fits inside this pipe (ID)
    cartridge_od = 10, // Holds this cartridge
    barb_od = 6.5,
    barb_id = 4,
    cartridge_thread_inner = false,
    cartridge_thread_outer = false,
    tube_thread_inner = false,
    tube_thread_outer = true,
    oring_cs = 1.5,
    tube_wall = 2,
    use_colors = true,
    cartridge_wall_height = 10,
    cartridge_offset = 0
) {
    // Dimensions
    base_height = 5;
    lip_height = 10;

    // Derived Dimensions

    // Tube Interface
    tube_od = tube_id + 2 * tube_wall;

    // Plug (Male, Outer Thread) fits ID
    plug_od = tube_id - 0.2; // Tolerance for smooth fit

    // Cap (Female, Inner Thread) fits OD
    cap_id = tube_od + 0.2; // Tolerance
    cap_od = cap_id + 4; // Wall thickness for cap

    // Cartridge Interface
    // Socket (Female, Inner Thread) ID
    socket_id = cartridge_od + 0.2;

    // Nipple (Male, Outer Thread) OD
    nipple_od = cartridge_od - 0.2;

    // Calculate Cartridge Feature OD (The core cylinder we need to keep/generate)
    cartridge_feature_od = max(
        cartridge_thread_outer ? nipple_od : 0,
        cartridge_thread_inner ? (socket_id + 4) : (cartridge_od + 4)
    );

    // Base Plate Calculation
    base_plate_min_d = max(
        tube_thread_inner ? cap_od : 0,
        tube_thread_outer ? (tube_id + 2*max(tube_wall, 2)) : (tube_id - 0.2)
    );

    base_plate_od = base_plate_min_d;

    union() {
        // 1. Central Barb
        translate([0, 0, base_height])
        if (use_colors) color("Blue", 1.0)
        Barb(
            hose_id = barb_id,
            hose_od = barb_od,
            barb_count = 3,
            wall_thickness = (barb_od - barb_id)/2,
            swell = 1
        );
        else
        Barb(
            hose_id = barb_id,
            hose_od = barb_od,
            barb_count = 3,
            wall_thickness = (barb_od - barb_id)/2,
            swell = 1
        );

        // 2. Main Body Plate
        difference() {
            if (use_colors) color("Chartreuse", 1.0) cylinder(d = base_plate_od, h = base_height, anchor=BOTTOM, $fn=$fn);
            else cylinder(d = base_plate_od, h = base_height, anchor=BOTTOM, $fn=$fn);

            // Center hole for flow
            translate([0,0,-1]) cylinder(d = barb_id, h = base_height + 2, anchor=BOTTOM, $fn=$fn);

            // Face Seals (Underside of Base Plate)

            // Tube Interface Seals
            if (tube_thread_outer) {
                // Plug Flange Seal (against Tube Rim)
                rim_seal_d = tube_id + tube_wall;
                OringGroove_Face_Cutter(rim_seal_d, oring_cs);
            }
            if (tube_thread_inner) {
                // Cap Face Seal
                if (!tube_thread_outer) {
                    rim_seal_d = tube_id + tube_wall;
                    OringGroove_Face_Cutter(rim_seal_d, oring_cs);
                }
            }

            // Cartridge Interface Seals
            if (cartridge_thread_inner) {
                // Face seal at the bottom of the socket
                OringGroove_Face_Cutter(socket_id + 2, oring_cs);
            }
        }

        // 3. Interface Lips (Extending Downwards)
        // Translate to the bottom of the base plate (Z=0) and point downwards?
        // Original code: translate([0, 0, -lip_height])
        // And generated geometry upwards from there.
        // We will keep that coordinate system for consistency.

        translate([0, 0, -lip_height]) {
            difference() {
                union() {
                    // --- TUBE INTERFACE GEOMETRY ---

                    // A. Plug (Fits inside Tube)
                    if (tube_thread_outer) {
                        // Threaded Plug
                        // Generated from Z=0 upwards to lip_height
                        if (use_colors) color("Orange", 1.0)
                            threaded_rod(d=tube_id, h=lip_height, pitch=1.5, internal=false, anchor=BOTTOM, $fn=$fn);
                        else
                            threaded_rod(d=tube_id, h=lip_height, pitch=1.5, internal=false, anchor=BOTTOM, $fn=$fn);
                    } else if (!tube_thread_inner) {
                        // Smooth Plug
                         if (use_colors) color("Orange", 1.0) cylinder(d=plug_od, h=lip_height/2, anchor=BOTTOM, $fn=$fn);
                         else cylinder(d=plug_od, h=lip_height/2, anchor=BOTTOM, $fn=$fn);

                         translate([0,0,lip_height/2]) {
                             if (use_colors) color("Gold", 1.0) cylinder(d=plug_od, h=lip_height/2, anchor=BOTTOM, $fn=$fn);
                             else cylinder(d=plug_od, h=lip_height/2, anchor=BOTTOM, $fn=$fn);
                         }
                    }

                    // B. Cap (Fits over Tube)
                    if (tube_thread_inner) {
                        // Outer Wall for Cap
                        if (use_colors) color("Red", 1.0) cylinder(d=cap_od, h=lip_height, anchor=BOTTOM, $fn=$fn);
                        else cylinder(d=cap_od, h=lip_height, anchor=BOTTOM, $fn=$fn);
                    }

                    // --- CARTRIDGE INTERFACE GEOMETRY ---
                    // Explicitly generate the cartridge holder.

                    translate([0,0,cartridge_offset]) {
                        if (cartridge_thread_outer) {
                             // Nipple (Threaded Stud)
                             if (use_colors) color("Cyan", 1.0)
                                threaded_rod(d=nipple_od, h=cartridge_wall_height, pitch=1.5, internal=false, anchor=BOTTOM, $fn=$fn);
                             else
                                threaded_rod(d=nipple_od, h=cartridge_wall_height, pitch=1.5, internal=false, anchor=BOTTOM, $fn=$fn);
                        } else {
                            // Socket Wall / Core (Smooth Cylinder)
                            if (use_colors) color("Purple", 1.0)
                                cylinder(d=cartridge_feature_od, h=cartridge_wall_height, anchor=BOTTOM, $fn=$fn);
                            else
                                cylinder(d=cartridge_feature_od, h=cartridge_wall_height, anchor=BOTTOM, $fn=$fn);
                        }
                    }

                    // Connect everything to base (Ensure solid connection at top)
                    translate([0,0,lip_height-1])
                        cylinder(d=base_plate_od, h=1, anchor=BOTTOM, $fn=$fn);
                }

                // --- SUBTRACTIONS ---

                // 1. Cap Internal Threads
                if (tube_thread_inner) {
                     translate([0,0,-1])
                        threaded_rod(d=cap_id, h=lip_height+2, pitch=1.5, internal=true, anchor=BOTTOM, $fn=$fn);
                }

                // 2. Socket Internal Threads or Smooth Socket Hole
                if (cartridge_thread_inner) {
                     translate([0,0,cartridge_offset-1])
                        threaded_rod(d=socket_id, h=cartridge_wall_height+2, pitch=1.5, internal=true, anchor=BOTTOM, $fn=$fn);
                } else if (!cartridge_thread_outer) {
                    // Smooth Socket Hole (Fix for "incorrect purple circle")
                    translate([0,0,cartridge_offset-1])
                        cylinder(d=socket_id, h=cartridge_wall_height+2, anchor=BOTTOM, $fn=$fn);
                }

                // 3. Clear Center Flow Path
                translate([0,0,-1]) cylinder(d = barb_id, h = lip_height + 50, anchor=BOTTOM, $fn=$fn);

                // 4. O-Ring Grooves (Radial)
                // Positioned relative to lip_height/2 (center of lip section) if strictly centered,
                // but for now we assume they are at Z = 0.75 * lip_height relative to our group?
                // Original: translate([0,0,segment_h + segment_h/2]) -> Z=7.5.
                // Our group base is -10. 7.5 relative to base? No.
                // Original Plug was translated to segment_h (5). segment_h/2 = 2.5.
                // So original radial seal was at 5+2.5 = 7.5.
                // Global Z: -10 + 7.5 = -2.5.

                if (!tube_thread_outer && !tube_thread_inner) {
                    // Smooth Plug Radial Seal
                    translate([0,0, lip_height * 0.75])
                        OringGroove_OD_Cutter(plug_od, oring_cs);
                }

                if (!cartridge_thread_inner && !cartridge_thread_outer) {
                    // Smooth Socket Radial Seal
                    // Should be relative to cartridge holder.
                    // If cartridge_wall_height is small, this might be off.
                    // Assuming default 10mm height, 7.5mm is fine.
                    translate([0,0, cartridge_offset + (cartridge_wall_height * 0.75)])
                        OringGroove_ID_Cutter(socket_id, oring_cs);
                }

                // 5. Cleanup / Hollows
                // If Plug exists, we want to hollow it out to create the annular space for the tube wall.
                if (tube_thread_outer) {
                    plug_wall_id = tube_id - 4;
                    // Check if we need to clean up
                    if (plug_wall_id > cartridge_feature_od) {
                        translate([0,0,-1]) difference() {
                            cylinder(d=plug_wall_id, h=lip_height+2, anchor=BOTTOM, $fn=$fn);
                            cylinder(d=cartridge_feature_od, h=lip_height+3, anchor=BOTTOM, $fn=$fn);
                        }
                    }

                    // Distal Face Seal (Fix for "circled green part")
                    distal_groove_dia = tube_id - 2.1;
                    groove_depth = oring_cs * 0.8;
                    // Cut at the bottom face (Local Z=0)
                    translate([0,0, groove_depth/2])
                        OringGroove_Face_Cutter(distal_groove_dia, oring_cs);
                }
            }

            // --- VISUALIZATION ---
            if (SHOW_O_RINGS) {
                 // Tube Interface
                 if (tube_thread_outer || tube_thread_inner) {
                      // Face Seal (Base Plate)
                      rim_seal_d = tube_id + tube_wall;
                      translate([0, 0, lip_height])
                          OringVisualizer_Face(rim_seal_d, oring_cs);

                      // Face Seal (Distal End) - if outer thread
                      if (tube_thread_outer) {
                          distal_groove_dia = tube_id - 2.1;
                          groove_depth = oring_cs * 0.8;
                          translate([0,0, groove_depth/2])
                              OringVisualizer_Face(distal_groove_dia, oring_cs);
                      }
                 } else {
                     // Radial Seal
                     translate([0,0, lip_height * 0.75])
                        OringVisualizer(plug_od, oring_cs);
                 }

                 // Cartridge Interface
                 if (cartridge_thread_inner) {
                     // Face Seal (Top of cartridge/Bottom of socket)
                     // If socket thread inner, the seal is usually at the bottom of the hole?
                     // Or at the face?
                     // Code said: translate([0, 0, lip_height]).
                     // But socket is inside.
                     // Usually cartridge presses against base plate.
                     translate([0, 0, lip_height])
                        OringVisualizer_Face(socket_id+2, oring_cs);
                 } else if (!cartridge_thread_outer) {
                     // Radial Seal
                     translate([0,0, cartridge_offset + (cartridge_wall_height * 0.75)])
                        OringVisualizer_ID(socket_id, oring_cs);
                 }
            }
        }
    }
}
