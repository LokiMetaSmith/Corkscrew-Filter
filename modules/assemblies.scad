// =============================================================================
// --- Assembly Modules ---
// =============================================================================
// This file contains the top-level modules that assemble complete,
// printable parts.

// Helper function: Cumulative sum of a list.
// Returns a list where list[i] is the sum of v[0]...v[i-1].
// The result has length len(v) + 1.
function accumulate_sum(v, i=0, current=0) =
    (i >= len(v)) ? [current] :
    concat([current], accumulate_sum(v, i+1, current + v[i]));


/**
 * Module: ModularFilterAssembly
 * Description: Assembles the complete modular filter, including screw segments, spacers,
 * and optional inlets and supports.
 * Arguments:
 * tube_id:      The inner diameter of the tube this assembly will fit into.
 * total_length: The total desired length of the filter assembly.
 */
module ModularFilterAssembly(tube_id, total_length) {
    // Calculate dimensions for the individual components based on the total length and number of bins.
    total_spacer_length = (num_bins + 1) * spacer_height_mm;
    total_screw_length = total_length - total_spacer_length;
    bin_length = total_screw_length / num_bins;

    // --- Parse Revolutions (Scalar or Array) ---
    // Calculate twist rates (degrees per mm) for each bin.
    // If array: Interpreted as revolutions PER BIN (e.g. 1 means 1 full turn in that bin).
    // If scalar: Interpreted as revolutions OVER TOTAL LENGTH .
    _rates = is_list(number_of_complete_revolutions)
        ? [for (r = number_of_complete_revolutions) 360 * r / bin_length]
        : [for (i=[0:num_bins-1]) 360 * number_of_complete_revolutions / total_length];

    // --- Component Sequence Definition ---
    // We treat the assembly as a stack of components: Spacers and Bins.
    // Sequence: S0, B0, S1, B1, ..., Sn-1, Bn-1, Sn
    // Total components: 2 * num_bins + 1
    component_count = 2 * num_bins + 1;

    // Component Heights
    // Even indices are Spacers, Odd indices are Bins.
    _comp_heights = [for (k=[0:component_count-1]) (k % 2 == 0) ? spacer_height_mm : bin_length];

    // Component Twist Rates
    // Spacer k (index 2k) uses rate[k] (except last spacer uses rate[last])
    // Bin k (index 2k+1) uses rate[k]
    // Mapping component index k to bin index for rate lookup:
    function get_rate_index(k) = min(floor(k/2), num_bins-1);
    _comp_rates = [for (k=[0:component_count-1]) _rates[get_rate_index(k)]];

    // Calculate Z-positions (cumulative heights)
    // _z_starts[k] is the Z position of the bottom of component k relative to the bottom of the stack.
    _z_offsets = accumulate_sum(_comp_heights);
    z_bottom = -total_length / 2;

    // Calculate Rotation Phases (cumulative rotations)
    // We integrate twist_rate * height along the stack.
    _rot_increments = [for (k=[0:component_count-1]) _comp_rates[k] * _comp_heights[k]];
    _rot_starts = accumulate_sum(_rot_increments);

    color(USE_TRANSLUCENCY ? [0.9, 0.9, 0.9, 0.5] : "Gainsboro")
    union() {
        // Loop through all components
        for (k = [0 : component_count - 1]) {
            is_bin = (k % 2 != 0);
            bin_idx = floor(k / 2); // For bins: 0..num_bins-1. For spacers: 0..num_bins.

            // Dimensions and Properties
            h = _comp_heights[k];
            rate = _comp_rates[k];

            // Position and Rotation
            z_start = z_bottom + _z_offsets[k];
            z_center = z_start + h / 2;

            rot_start = _rot_starts[k];
            rot_center = rot_start + (rate * h / 2); // Rotation at the center of the component

            translate([0, 0, z_center]) rotate([0, 0, rot_center]) {
                if (is_bin) {
                    // --- Generate Bin ---
                    // Enforce safety margin: profile radius must be strictly less than path radius
                    safe_profile_radius = min(helix_profile_radius_mm, helix_path_radius_mm - 0.5);

                    difference() {
                        // Solid Screw Segment
                        HollowHelicalShape(
                            h + 0.02, // Add overlap for robust union
                            rate * (h + 0.02),
                            helix_path_radius_mm + 0.01, // Add tiny offset to prevent singularity at axis
                            safe_profile_radius,
                            helix_void_profile_radius_mm + tolerance_channel
                        );

                        // Slits
                        if (slit_type == "simple") {
                            SimpleSlitCutter(h + 0.02, rate * (h + 0.02), 2 * (helix_path_radius_mm + safe_profile_radius), 1, offset_angle=0);
                        } else if (slit_type == "ramped") {
                            RampedSlitKnife(h + 0.02, rate * (h + 0.02), 2 * (helix_path_radius_mm + safe_profile_radius), 1, offset_angle=0);
                        }
                    }
                } else {
                    // --- Generate Spacer ---
                    spacer_idx = bin_idx; // 0..num_bins
                    is_base = (spacer_idx == 0);
                    is_top = (spacer_idx == num_bins);
                    spacer_od = tube_id - tolerance_tube_fit;

                    union() {
                        difference() {
                            cylinder(d = spacer_od, h = h + 0.02, center = true); // Add overlap

                            // Cut the helical void
                            Corkscrew(h + 0.04, rate * (h + 0.04), void = true);

                            union(){
                                OringGroove_OD_Cutter(spacer_od, oring_cross_section_mm);

                                // Inlet/Outlet Recess
                                if ((is_top || is_base) && inlet_type != "none") {
                                    recess_d = (inlet_type == "threaded" || inlet_type == "pressfit")
                                        ? threaded_inlet_flange_od + tolerance_socket_fit
                                        : barb_inlet_flange_od + tolerance_socket_fit;

                                    // Align recess with the helix interface
                                    // Interface is at z_center +/- h/2.
                                    // But we are in local coordinates centered at 0.
                                    // Top spacer: Interface is at bottom (-h/2). Recess at -h/2.
                                    // Base spacer: Interface is at top (h/2). Recess at h/2.
                                    // Wait, original logic:
                                    // z_interface = is_top ? (h / 2 - 1) : (-h / 2 + 2); -- Original values were hardcoded/relative.

                                    // Let's replicate original placement logic carefully.
                                    // Original:
                                    // z_recess_pos = is_top ? (spacer_height_mm / 2 - 1) : (-spacer_height_mm / 2);
                                    // We are centered.

                                    z_recess_pos = is_top ? (h / 2 - 1) : (-h / 2);

                                    // Rotation at recess:
                                    // We need to match the rotation at that Z height.
                                    // Local Z = z_recess_pos.
                                    // Local Rot = rate * z_recess_pos.
                                    // Note: `rotate([0, 0, rot_center])` is already applied to the parent.
                                    // So we just need local rotation relative to center?
                                    // Yes.

                                    ra = rate * z_recess_pos;

                                    rotate([0, 0, ra]) translate([helix_path_radius_mm, 0, z_recess_pos]) cylinder(d = recess_d, h = 2);
                                }
                            }
                        }

                        // Inlet/Outlet Attachments
                        if ((is_top || is_base) && inlet_type != "none") {
                            mirror_vec = [0, 0, is_top ? 0 : 1];
                            // Original: z_local = is_top ? (spacer_height_mm / 2 - 1) : (-spacer_height_mm / 2 + 2);
                            z_local = is_top ? (h / 2 - 1) : (-h / 2 + 2);
                            ra = rate * z_local;

                            rotate([0, 0, ra]) translate([helix_path_radius_mm, 0, z_local]) mirror(mirror_vec) {
                                if (inlet_type == "threaded" || inlet_type == "pressfit") {
                                    ThreadedInlet();
                                } else if (inlet_type == "barb") {
                                    BarbInlet();
                                }
                            }
                        }

                        if (SHOW_O_RINGS) { OringVisualizer(spacer_od, oring_cross_section_mm); }

                        // Supports
                        // Only add support if it's below a bin (not top spacer)
                        if (ADD_HELICAL_SUPPORT && !GENERATE_CFD_VOLUME && !is_top) {
                            // Support covers the bin above this spacer.
                            // The support module generates geometry of height `bin_length`.
                            // We need to position it correctly.
                            // Original: translate([0, 0, spacer_height_mm / 2]) rotate(...) HelicalOuterSupport(...)
                            // It starts from the top of the spacer.

                            translate([0, 0, h / 2])
                                rotate([0, 0, rate * h / 2])
                                HelicalOuterSupport(spacer_od, bin_length, support_rib_thickness_mm, rate);
                        }
                    }
                }
            }
        }

        if (SHOW_TUBE) {
            visual_tube_len = (tube_length_override > total_length) ? tube_length_override : total_length;
            // tube_id is passed as arg, which corresponds to the inner diameter of the tube.
            // We reconstruct the OD using the global tube_wall_mm.
            TubeVisualizer(tube_id + 2 * tube_wall_mm, tube_wall_mm, visual_tube_len, center = true);
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

        if (SHOW_TUBE) {
            visual_tube_len = (tube_length_override > 0) ? tube_length_override : (cap_sleeve_height + 50);
            translate([0, 0, cap_sleeve_height - visual_tube_len / 2])
                TubeVisualizer(tube_od, tube_wall, visual_tube_len, center = true);
        }

        translate([0, 0, cap_sleeve_height + cap_end_plate_thick + flange_height])
            Barb(hose_id = hose_id, hose_od = hose_id + 1.5, barb_count = 4);

    } else {
        // --- Radial Seal Geometry ---

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

        if (SHOW_TUBE) {
            visual_tube_len = (tube_length_override > 0) ? tube_length_override : (cap_sleeve_height + 50);
            translate([0, 0, cap_sleeve_height - visual_tube_len / 2])
                TubeVisualizer(tube_od, tube_wall, visual_tube_len, center = true);
        }

        translate([0, 0, cap_sleeve_height + cap_end_plate_thick + flange_height])
            Barb(hose_id = hose_id, hose_od = hose_id + 1.5, barb_count = 4);
    }
}
