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
    use_colors = true
) {
    // Dimensions
    base_height = 5;
    lip_height = 10;
    segment_h = lip_height / 2;

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
    // Assumption: Mating part has ID = cartridge_od.
    nipple_od = cartridge_od - 0.2;

    // Base Plate Calculation
    // Must be large enough to support the largest outer feature.
    // If Cap enabled, must cover Cap OD.
    // If Plug enabled (threaded), usually has a flange.
    // If neither, usually fits inside tube (no flange, or small lip).

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
            if (use_colors) color("Chartreuse", 1.0) cylinder(d = base_plate_od, h = base_height, $fn=$fn);
            else cylinder(d = base_plate_od, h = base_height, $fn=$fn);

            // Center hole for flow
            translate([0,0,-1]) cylinder(d = barb_id, h = base_height + 2, $fn=$fn);

            // Face Seals (Underside of Base Plate)

            // Tube Interface Seals
            if (tube_thread_outer) {
                // Plug Flange Seal (against Tube Rim)
                // Groove at mean diameter of tube wall
                rim_center = tube_id + tube_wall;
                // Alternatively, closer to ID or OD. Original was base_plate_od - oring_cs.
                // If base_plate_od is huge (due to Cap), this is wrong.
                // It should seal against the tube end face.
                rim_seal_d = tube_id + tube_wall;
                OringGroove_Face_Cutter(rim_seal_d, oring_cs);
            }
            if (tube_thread_inner) {
                // Cap Face Seal (against Tube Rim)
                // Also seals against the tube rim.
                // If both are true, we only need one seal.
                if (!tube_thread_outer) {
                    rim_seal_d = tube_id + tube_wall;
                    OringGroove_Face_Cutter(rim_seal_d, oring_cs);
                }
            }

            // Cartridge Interface Seals (Ceiling of Socket)
            if (cartridge_thread_inner) {
                // Face seal at the bottom of the socket (top of the cartridge)
                OringGroove_Face_Cutter(socket_id + 2, oring_cs); // Slightly larger than hole
            }
        }

        // 3. Interface Lips (Extending Downwards)
        translate([0, 0, -lip_height]) {
            difference() {
                union() {
                    // --- TUBE INTERFACE GEOMETRY ---

                    // A. Plug (Fits inside Tube)
                    if (tube_thread_outer) {
                        // Threaded Plug
                        translate([0,0,segment_h])
                            if (use_colors) color("Orange", 1.0) threaded_rod(d=tube_id, h=lip_height, pitch=1.5, internal=false, $fn=$fn);
                            else threaded_rod(d=tube_id, h=lip_height, pitch=1.5, internal=false, $fn=$fn);
                    } else if (!tube_thread_inner) {
                        // Smooth Plug (Only if no Cap, or can coexist?)
                        // If we want "Plug AND Cap", we generate both.
                        // Standard "Smooth Plug" behavior if no threads requested on tube.
                         translate([0,0,segment_h]) {
                             if (use_colors) color("Orange", 1.0) cylinder(d=plug_od, h=segment_h, $fn=$fn);
                             else cylinder(d=plug_od, h=segment_h, $fn=$fn);
                         }
                         if (use_colors) color("Gold", 1.0) cylinder(d=plug_od, h=segment_h, $fn=$fn);
                         else cylinder(d=plug_od, h=segment_h, $fn=$fn);
                    }

                    // B. Cap (Fits over Tube)
                    if (tube_thread_inner) {
                        // Outer Wall for Cap
                         translate([0,0,segment_h]) {
                            if (use_colors) color("Red", 1.0) cylinder(d=cap_od, h=lip_height, $fn=$fn);
                            else cylinder(d=cap_od, h=lip_height, $fn=$fn);
                         }
                    }

                    // --- CARTRIDGE INTERFACE GEOMETRY ---

                    // C. Nipple (Fits into Cartridge? No, Cartridge screws ONTO Nipple)
                    // Nipple is a male stud.
                    if (cartridge_thread_outer) {
                         translate([0,0,segment_h])
                            if (use_colors) color("Cyan", 1.0) threaded_rod(d=nipple_od, h=lip_height, pitch=1.5, internal=false, $fn=$fn);
                            else threaded_rod(d=nipple_od, h=lip_height, pitch=1.5, internal=false, $fn=$fn);
                    }

                    // D. Socket (Cartridge fits INTO Holder)
                    // We need material to cut the socket into.
                    // Or "Smooth Socket" material.
                    // This material is usually the inner core of the plug.
                    // If Nipple exists, it provides material.
                    // If Plug exists, it provides material.
                    // If neither, we need a core cylinder.

                    core_needed_od = max(
                        cartridge_thread_outer ? 0 : 0,
                        cartridge_thread_inner ? (socket_id + 4) : (cartridge_od + 4)
                    );

                    // If plug is solid, it covers this.
                    // But if plug is hollow or non-existent, we need explicit core.

                    if (!tube_thread_outer && !cartridge_thread_outer) {
                        // Provide core material for socket
                        if (use_colors) color("Purple", 1.0) cylinder(d=core_needed_od, h=lip_height, $fn=$fn);
                        else cylinder(d=core_needed_od, h=lip_height, $fn=$fn);
                    }

                    // Connect everything to base
                    translate([0,0,lip_height-1])
                        cylinder(d=base_plate_od, h=1, $fn=$fn);
                }

                // --- SUBTRACTIONS ---

                // 1. Cap Internal Threads
                if (tube_thread_inner) {
                     translate([0,0,segment_h-1])
                        threaded_rod(d=cap_id, h=lip_height+2, pitch=1.5, internal=true, $fn=$fn);
                }

                // 2. Socket Internal Threads
                if (cartridge_thread_inner) {
                     translate([0,0,segment_h-1])
                        threaded_rod(d=socket_id, h=lip_height+2, pitch=1.5, internal=true, $fn=$fn);
                } else {
                    // Smooth Socket (if not threaded and not Nipple)
                    // If it's a Nipple, we don't bore a socket unless requested.
                    // But we always need flow path.
                }

                // 3. Clear Center Flow Path
                // Must be smaller than barb_id usually, or same.
                translate([0,0,-1]) cylinder(d = barb_id, h = lip_height + 50, $fn=$fn);

                // 4. O-Ring Grooves (Radial)

                // Tube Interface (Radial)
                if (!tube_thread_outer && !tube_thread_inner) {
                    // Smooth Plug Radial Seal
                    translate([0,0,segment_h + segment_h/2])
                        OringGroove_OD_Cutter(plug_od, oring_cs);
                }

                // Cartridge Interface (Radial)
                if (!cartridge_thread_inner && !cartridge_thread_outer) {
                    // Smooth Socket Radial Seal (ID Groove)
                    translate([0,0,segment_h + segment_h/2])
                        OringGroove_ID_Cutter(socket_id, oring_cs);
                }

                // 5. Cleanup / Hollows
                // If Plug is threaded, hollow it out to reduce material,
                // but leave enough for Cartridge interface.
                if (tube_thread_outer) {
                    // ID of the outer plug wall
                    plug_wall_id = tube_id - 4;
                    // OD of the inner cartridge interface (Socket wall or Nipple)
                    cartridge_feature_od = cartridge_thread_outer ? nipple_od : (socket_id + 4);

                    if (plug_wall_id > cartridge_feature_od) {
                        translate([0,0,-1]) difference() {
                            cylinder(d=plug_wall_id, h=lip_height+2, $fn=$fn);
                            cylinder(d=cartridge_feature_od, h=lip_height+3, $fn=$fn);
                        }
                    }
                }
            }

            // --- VISUALIZATION ---
            if (SHOW_O_RINGS) {
                 // Tube Interface
                 if (tube_thread_outer || tube_thread_inner) {
                      // Face Seal
                      rim_seal_d = tube_id + tube_wall;
                      translate([0, 0, lip_height])
                          OringVisualizer_Face(rim_seal_d, oring_cs);
                 } else {
                     // Radial Seal
                     translate([0,0,segment_h + segment_h/2])
                        OringVisualizer(plug_od, oring_cs);
                 }

                 // Cartridge Interface
                 if (cartridge_thread_inner) {
                     // Face Seal
                     translate([0, 0, lip_height])
                        OringVisualizer_Face(socket_id+2, oring_cs);
                 } else if (!cartridge_thread_outer) {
                     // Radial Seal
                     translate([0,0,segment_h + segment_h/2])
                        OringVisualizer_ID(socket_id, oring_cs);
                 }
            }
        }
    }
}
