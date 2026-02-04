// =============================================================================
// --- Assembly Modules ---
// =============================================================================
// This file contains the top-level modules that assemble complete,
// printable parts.

/**
 * Module: ModularFilterAssembly
 * Description: Assembles the complete modular filter, including screw segments, spacers,
 * and optional inlets and supports. It uses a robust "Master Helix" method
 * to ensure perfect alignment of all components, avoiding floating-point errors.
 * Arguments:
 * tube_id:      The inner diameter of the tube this assembly will fit into.
 * total_length: The total desired length of the filter assembly.
 */
module ModularFilterAssembly(tube_id, total_length) {
    // Calculate dimensions for the individual components based on the total length and number of bins.
    total_spacer_length = (num_bins + 1) * spacer_height_mm;
    total_screw_length = total_length - total_spacer_length;
    bin_length = total_screw_length / num_bins;
    twist_rate = (360 * number_of_complete_revolutions) / total_length; // degrees per mm

    // --- Master Helix Definitions ---
    module MasterSolidHelix() { Corkscrew(total_length + 2, twist_rate * (total_length + 2), void = false); }
    module MasterHollowHelix() {
        HollowHelicalShape(
            total_length + 2,
            twist_rate * (total_length + 2),
            helix_path_radius_mm,
            helix_profile_radius_mm,
            helix_void_profile_radius_mm + tolerance_channel
        );
    }
    // --- Optimized Generation (Local Segments) ---
    // Instead of generating a global MasterHelix and intersecting/differencing it (O(N^2) complexity),
    // we generate local segments for each bin and spacer with the correct phase alignment.
    // This reduces complexity to O(N) and avoids massive boolean operations.

    union() {
        // --- Create the screw segments (bins) ---
        for (i = [0 : num_bins - 1]) {
            z_pos = -total_length / 2 + spacer_height_mm + i * (bin_length + spacer_height_mm) + bin_length / 2;
            rot = twist_rate * z_pos;

            #translate([0, 0, z_pos]) rotate([0, 0, rot]) {
                intersection() {
                    rotate([0, 0, -rot]) translate([0, 0, -z_pos]) MasterHollowHelix();
                    cylinder(h = bin_length + 0.1, d = tube_id * 2, center = true);
                }
            }
            // Generate hollow segment directly with slight overlap for continuity
            local_h = bin_length + 0.02;
            local_twist = twist_rate * local_h;

            translate([0, 0, z_pos]) rotate([0, 0, rot - local_twist / 2]) {
                 HollowHelicalShape(local_h, local_twist, helix_path_radius_mm, helix_profile_radius_mm, helix_void_profile_radius_mm + tolerance_channel);
            }
        }

        // --- Create the spacers ---
        for (i = [0 : num_bins]) {
            z_pos = -total_length / 2 + i * (bin_length + spacer_height_mm) + spacer_height_mm / 2;
            rot = twist_rate * z_pos;
            is_base = (i == 0);
            is_top = (i == num_bins);
            spacer_od = tube_id - tolerance_tube_fit;

            // Generate cutter for spacer hole
            cut_h = spacer_height_mm + 0.02;
            cut_twist = twist_rate * cut_h;

            translate([0, 0, z_pos]) rotate([0, 0, rot]) {
                union() {
                    difference() {
                        cylinder(d = spacer_od, h = spacer_height_mm, center = true);
                        // Cut with local solid helix segment
                        rotate([0, 0, -cut_twist / 2])
                        HelicalShape(cut_h, cut_twist, helix_path_radius_mm, helix_profile_radius_mm);
                        union(){
                            OringGroove_OD_Cutter(spacer_od, oring_cross_section_mm);
                            if ((is_top || is_base) && inlet_type != "none") {
                                recess_d = (inlet_type == "threaded" || inlet_type == "pressfit")
                                    ? threaded_inlet_flange_od + tolerance_socket_fit
                                    : barb_inlet_flange_od + tolerance_socket_fit;

                                if (inlet_type == "barb") {
                                    // Align recess with the helix interface
                                    z_interface = is_top ? (spacer_height_mm / 2 - 1) : (-spacer_height_mm / 2 + 2);
                                    z_recess_pos = is_top ? (spacer_height_mm / 2 - 1) : (-spacer_height_mm / 2);
                                    ra = twist_rate * z_interface;

                                    rotate([0, 0, ra]) translate([helix_path_radius_mm, 0, z_recess_pos]) cylinder(d = recess_d, h = 2);
                                } else {
                                    // Standard centered recess for threaded/pressfit
                                    z_recess_pos = is_top ? (spacer_height_mm / 2 - 1) : (-spacer_height_mm / 2);
                                    translate([0, 0, z_recess_pos]) cylinder(d = recess_d, h = 2);
                                }
                            }
                        }
                    }

                    if ((is_top || is_base) && inlet_type != "none") {
                        mirror_vec = [0, 0, is_top ? 0 : 1];
                        if (inlet_type == "threaded" || inlet_type == "pressfit") {
                            z_shift = is_top ? spacer_height_mm / 2 : -spacer_height_mm / 2;
                            translate([0, 0, z_shift]) mirror(mirror_vec) ThreadedInlet();
                        } else if (inlet_type == "barb") {
                            z_local = is_top ? (spacer_height_mm / 2 - 1) : (-spacer_height_mm / 2 + 2);
                            ra = twist_rate * z_local;
                            rotate([0, 0, ra]) translate([helix_path_radius_mm, 0, z_local]) mirror(mirror_vec) BarbInlet();
                        }
                    }

                    if (SHOW_O_RINGS) { OringVisualizer(spacer_od, oring_cross_section_mm); }
                    // Disable support generation during CFD volume creation to prevent timeouts due to CSG complexity
                    if (ADD_HELICAL_SUPPORT && !GENERATE_CFD_VOLUME && !is_top) {
                        translate([0, 0, spacer_height_mm / 2])
                            rotate([0, 0, twist_rate * spacer_height_mm / 2])
                            HelicalOuterSupport(spacer_od, bin_length, support_rib_thickness_mm, twist_rate);
                    }
                }
            }
        }
    }
}

/**
 * Module: FlatEndScrew
 * Description: Creates a single, monolithic screw with perfectly flat ends (achieved via
 * an intersection with a cylinder) and slits separating the bins.
 * Arguments:
 * h:        The height of the screw.
 * twist:    The total twist angle in degrees.
 * num_bins: The number of bins to be separated by slits.
 */
module FlatEndScrew(h, twist, num_bins) {
    screw_outer_dia = 2 * (helix_path_radius_mm + helix_profile_radius_mm) * 1.2;
    intersection() {
        difference() {
            Corkscrew(h + 0.5, twist, void = false);
            CorkscrewSlitKnife(twist, h, num_bins);
        }
        cylinder(d = screw_outer_dia, h = h, center = true);
    }
}

/**
 * Module: SingleCellFilter
 * Description: Creates a single helical filter cell housed within its own simple cylindrical tube.
 */
module SingleCellFilter() {
    tube_od = cell_diameter + 10;
    tube_wall = 1.5;
    difference() {
        cylinder(d = tube_od, h = cell_length, center = true);
        cylinder(d = tube_od - 2 * tube_wall, h = cell_length + 2, center = true);
    }
    StagedHelicalStructure(cell_length, cell_diameter, num_helices, num_stages);
}

/**
 * Module: HexFilterArray
 * Description: Creates an array of filter cells arranged in a hexagonal pattern, all
 * contained within a single hexagonal block.
 * Arguments:
 * layers: The number of rings of cells around the center (0=1, 1=7, 2=19).
 */
module HexFilterArray(layers) {
    spacing = cell_diameter + 2;
    hex_casing_radius = sqrt(3) * spacing * (layers + 0.5);

    union() {
        // First, create the main block with all the holes and channels cut out.
        difference() {
            // Start with a solid hex block
            cylinder(h = cell_length, r = hex_casing_radius, center = true, $fn = 6);

            // Union all the things to be subtracted
            union() {
                // Hollow out the inside
                cylinder(h = cell_length + 2, r = hex_casing_radius - outer_casing_wall_mm, center = true, $fn = 6);

                // O-Ring Grooves on flat faces
                if (ADD_OUTER_O_RINGS) {
                    for (a = [0:5]) {
                        rotate([0, 0, a * 60 + 30]) {
                            translate([hex_casing_radius / 2, 0, cell_length / 4])
                                OringGroove_OD_Cutter(hex_casing_radius, oring_cross_section_mm, flat = true);
                            translate([hex_casing_radius / 2, 0, -cell_length / 4])
                                OringGroove_OD_Cutter(hex_casing_radius, oring_cross_section_mm, flat = true);
                        }
                    }
                }

                // Debris exit channels
                if (ADD_DEBRIS_EXIT_CHANNELS) {
                    HexArrayLayout(layers, spacing) {
                        StagedExitChannelCutter(cell_length, cell_diameter, num_helices, num_stages);
                    }
                }
            }
        }

        // Finally, add the filter cores into the space that was hollowed out.
        // This union happens "outside" the difference, so the cores are not cut.
        HexArrayLayout(layers, spacing) {
            StagedHelicalStructure(cell_length, cell_diameter, num_helices, num_stages);
        }

        if (ADD_OUTER_O_RINGS && SHOW_O_RINGS) {
            for (a = [0:5]) {
                rotate([0, 0, a * 60 + 30]) {
                    translate([hex_casing_radius / 2, 0, cell_length / 4])
                        OringVisualizer_Linear(hex_casing_radius, oring_cross_section_mm);
                    translate([hex_casing_radius / 2, 0, -cell_length / 4])
                        OringVisualizer_Linear(hex_casing_radius, oring_cross_section_mm);
                }
            }
        }
    }
}

/**
 * Module: HoseAdapterEndCap
 * Description: Creates a printable cap that fits over the main tube and provides a
 * hose barb connection.
 * Arguments:
 * tube_od:   The outer diameter of the tube this cap will fit onto.
 * hose_id:   The inner diameter of the hose that will connect to the barb.
 * oring_cs:  The cross-section diameter of the O-ring for sealing.
 * tube_wall: The wall thickness of the tube (used for axial seal calculation).
 * axial_seal: If true, creates a face seal (axial) instead of a radial seal.
 */
module HoseAdapterEndCap(tube_od, hose_id, oring_cs, tube_wall = tube_wall_mm, axial_seal = false) {
    // Common settings
    cap_wall = 3;
    cap_sleeve_height = 20;
    cap_end_plate_thick = 3;

    if (axial_seal) {
        // --- Axial Seal Geometry (Cup + Face Seal) ---
        socket_od = tube_od + tolerance_tube_fit;
        socket_id = tube_od - 2 * tube_wall - tolerance_tube_fit;

        // The cup needs to be large enough to contain the socket OD
        cap_outer_dia = socket_od + 2 * cap_wall;

        color(USE_TRANSLUCENCY ? [0.9, 0.9, 0.9, 0.5] : "Gainsboro")
        difference() {
            union() {
                // Main body block
                cylinder(d = cap_outer_dia, h = cap_sleeve_height);
                // End plate
                translate([0, 0, cap_sleeve_height]) cylinder(d = cap_outer_dia, h = cap_end_plate_thick);
                // Flange
                translate([0, 0, cap_sleeve_height + cap_end_plate_thick]) cylinder(d = flange_od, h = flange_height);
            }

            // Cut the annular socket for the tube
            translate([0,0,-1]) difference() {
                 cylinder(d = socket_od, h = cap_sleeve_height + 1); // Outer slot boundary
                 cylinder(d = socket_id, h = cap_sleeve_height + 2); // Inner slot boundary (island)
            }

            // Cut the central hole for flow
             translate([0, 0, -1]) cylinder(d = hose_id, h = cap_sleeve_height + cap_end_plate_thick + flange_height + 2);

            // Cut the O-ring groove on the face (bottom of the socket)
            // The bottom of the socket is at Z=cap_sleeve_height (against the end plate).
            // Shift down by half the groove depth to cut fully into the surface.
            groove_depth = oring_cs * 0.8;
            groove_center_dia = (socket_od + socket_id) / 2;
            translate([0, 0, cap_sleeve_height - groove_depth / 2]) OringGroove_Face_Cutter(groove_center_dia, oring_cs);
        }

        if (SHOW_O_RINGS) {
            groove_depth = oring_cs * 0.8;
            groove_center_dia = (socket_od + socket_id) / 2;
            translate([0, 0, cap_sleeve_height - groove_depth / 2]) OringVisualizer_Face(groove_center_dia, oring_cs);
        }

        translate([0, 0, cap_sleeve_height + cap_end_plate_thick + flange_height])
            Barb(hose_id = hose_id, hose_od = hose_id + 1.5, barb_count = 4);

    } else {
        // --- Legacy Radial Seal Geometry ---

        cap_inner_dia = tube_od - 2 * tube_wall + tolerance_tube_fit;
        cap_outer_dia = cap_inner_dia + 2 * cap_wall;

        color(USE_TRANSLUCENCY ? [0.9, 0.9, 0.9, 0.5] : "Gainsboro")
        difference() {
            union() {
                cylinder(d = cap_outer_dia, h = cap_sleeve_height);
                translate([0, 0, cap_sleeve_height]) cylinder(d = cap_outer_dia, h = cap_end_plate_thick);
                translate([0, 0, cap_sleeve_height + cap_end_plate_thick]) cylinder(d = flange_od, h = flange_height);
            }
            translate([0, 0, -1]) cylinder(d = cap_inner_dia, h = cap_sleeve_height + 2);
            translate([0, 0, cap_sleeve_height / 2]) OringGroove_ID_Cutter(cap_inner_dia, oring_cs);
            translate([0, 0, cap_sleeve_height]) cylinder(d = hose_id, h = cap_end_plate_thick + flange_height + 2);
        }

        if (SHOW_O_RINGS) {
            translate([0, 0, cap_sleeve_height / 2]) OringVisualizer_ID(cap_inner_dia, oring_cs);
        }

        translate([0, 0, cap_sleeve_height + cap_end_plate_thick + flange_height])
            Barb(hose_id = hose_id, hose_od = hose_id + 1.5, barb_count = 4);
    }
}
