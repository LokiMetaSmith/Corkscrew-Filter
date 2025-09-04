// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED and Refactored by Gemini.
// VERSION REFACTORED:
// - Centralized user controls and feature flags for easier configuration.
// - Reorganized parameters into logical, component-based groups.
// - Merged redundant modules to improve maintainability (e.g., Corkscrew, StagedHelicalStructure).
// - Clarified variable names for better readability.
// - Restructured main logic for clarity.
// - Commented out unused/legacy modules.

// =============================================================================
// --- A. High-Level Control Panel ---
// =============================================================================

// --- 1. Model Selection ---
// Select which part of the assembly you want to render.
part_options = ["modular_filter_assembly", "hex_array_filter", "single_cell_filter", "hose_adapter_cap"];
part_to_generate = part_options[1]; // ["modular_filter_assembly", "hex_array_filter", "single_cell_filter", "hose_adapter_cap"]

// --- 2. Feature Flags ---
// These flags toggle optional features on the selected model.

// --- Modular Filter Features ---
GENERATE_CFD_VOLUME = false;     // Set true to generate the internal fluid volume instead of the solid part.
USE_MASTER_HELIX_METHOD = false;  // Use the robust master helix method for assembly. 'false' uses an older method.
ADD_HELICAL_SUPPORT = false;      // Adds a helical support structure between spacers.
THREADED_INLET = false;          // Adds recesses to the end spacers (purpose may vary).

// --- Hex/Single Cell Features ---
ADD_OUTER_O_RINGS = true;        // Adds O-Ring grooves to the outer casing of the hex array.
ADD_SLITS = true;                // Adds simple slits to the helical ramps.

// --- Visual/Debug Options ---
SHOW_O_RINGS = false;             // Renders visual representations of the O-rings.
USE_TRANSLUCENCY = true;        // Makes some parts transparent for better internal viewing.

// =============================================================================
// --- B. Model Parameters ---
// =============================================================================

// --- General & Precision ---
high_res_fn = 150;
low_res_fn = 30;
$fn = $preview ? low_res_fn : high_res_fn;

// --- Tube & Main Assembly Parameters (for Modular Filter) ---
tube_od_mm = 32;
tube_wall_mm = 1;
insert_length_mm = 350 / 2;
num_bins = 2;                     // The number of helical screw segments.

// --- Helical Screw Parameters (for Modular Filter) ---
number_of_complete_revolutions = 12;
helix_path_radius_mm = 1.8;       // The radius of the helical path from the center.
helix_profile_radius_mm = 1.8;    // The radius of the solid screw's circular cross-section.
helix_void_profile_radius_mm = 1; // The radius of the void's circular cross-section.
helix_profile_scale_ratio = 1.4;  // Stretches the circular profile into an ellipse.

// --- Spacer & O-Ring Parameters (for Modular Filter) ---
spacer_height_mm = 5;
oring_cross_section_mm = 1.5;

// --- Helical Support Parameters (for Modular Filter) ---
support_rib_thickness_mm = 2.5;
support_revolutions = 4;
support_density = 2;              // Number of support bundles around the circumference.

// --- Hose Adapter Cap Parameters ---
adapter_hose_id_mm = 30;
flange_od = 20;                   // Outer diameter of the hose adapter flange.
flange_height = 5;                // Height of the hose adapter flange.

// --- Hex Array & Single Cell Filter Parameters ---
cell_diameter = 10;               // OD of the corkscrew in a single cell.
cell_length = 100;                // The total Z-height of a filter cell.
num_helices = 5;                  // Number of interleaved helices (1, 2, or 3).
ramp_width_degrees = 20;          // Angular width of a single helix ramp.
total_revolutions = 8;            // Total turns over the cell_length.
num_stages = 1;                   // [1, 2, 3] Number of axial stages/segments.
hex_array_layers = 1;             // 0=1 cell, 1=7 cells, 2=19 cells, etc.
outer_casing_wall_mm = 3;

// --- Ramped Slit Parameters (Legacy/Unused) ---
slit_ramp_length_mm = 5;
slit_open_length_mm = 10;
slit_width_mm = 2;
slit_depth_mm = 2;

// --- Tolerances & Fit ---
tolerance_tube_fit = 0.2;         // Clearance between spacers and the inner tube wall.
tolerance_socket_fit = 0.4;       // Clearance for screw sockets in spacers.
tolerance_channel = 0.1;          // Extra clearance for the airflow channel to prevent binding.

// --- Config File (Optional Override) ---
// To use, create a file named "filter_config.scad" with parameter overrides.
// Example: `num_bins = 5;`
// include <filter_config.scad>

// =============================================================================
// --- C. Main Logic ---
// =============================================================================

if (part_to_generate == "modular_filter_assembly") {
    tube_id = tube_od_mm - (2 * tube_wall_mm);
    if (GENERATE_CFD_VOLUME) {
        difference() {
            // Start with a solid cylinder representing the inner volume of the tube
            cylinder(d = tube_id, h = insert_length_mm, center = true);
            // Subtract the entire filter assembly to leave only the fluid volume
            ModularFilterAssembly(tube_id, insert_length_mm);
        }
    } else {
        // Generate the solid parts for printing
        ModularFilterAssembly(tube_id, insert_length_mm);
    }
} else if (part_to_generate == "hex_array_filter") {
    HexFilterArray(hex_array_layers);
} else if (part_to_generate == "single_cell_filter") {
    SingleCellFilter();
} else if (part_to_generate == "hose_adapter_cap") {
    HoseAdapterEndCap(tube_od_mm, adapter_hose_id_mm, oring_cross_section_mm);
}

// =============================================================================
// --- D. Module Definitions ---
// =============================================================================

// --- Core Component Modules ---

/**
 * Module: HelicalShape
 * Description: Generates a helical shape by extruding a scaled circle (ellipse).
 * This is the fundamental building block for the modular filter's screw.
 * Arguments:
 * - h: The height of the extrusion.
 * - twist: The total twist angle in degrees over the height.
 * - path_r: The radius of the helical path.
 * - profile_r: The radius of the circular profile before scaling.
 */
module HelicalShape(h, twist, path_r, profile_r) {
    linear_extrude(height = h, center = true, convexity = 10, twist = twist) {
        translate([path_r, 0, 0]) {
            scale([1, helix_profile_scale_ratio]) {
                circle(r = profile_r);
            }
        }
    }
}

/**
 * Module: Corkscrew
 * Description: Creates either the solid or the void (cutter) part of the helical screw.
 * This module replaces the previous `CorkscrewSolid` and `CorkscrewVoid`.
 * Arguments:
 * - h: The height of the corkscrew.
 * - twist: The total twist angle in degrees.
 * - void: If true, generates the void (cutter); otherwise, generates the solid.
 */
module Corkscrew(h, twist, void = false) {
    profile_r = void
        ? helix_void_profile_radius_mm + tolerance_channel
        : helix_profile_radius_mm;
    HelicalShape(h, twist, helix_path_radius_mm, profile_r);
}

// --- Top-Level Assembly Modules ---

/**
 * Module: ModularFilterAssembly
 * Description: Assembles the complete modular filter with spacers and helical screws.
 * Uses a robust "Master Helix" method to ensure perfect alignment of all components.
 */
module ModularFilterAssembly(tube_id, total_length) {
    total_spacer_length = (num_bins + 1) * spacer_height_mm;
    total_screw_length = total_length - total_spacer_length;
    bin_length = total_screw_length / num_bins;
    twist_rate = (360 * number_of_complete_revolutions) / total_length; // degrees per mm

    // --- Define Master Helices (used as templates) ---
    module MasterSolidHelix() {
        Corkscrew(total_length + 2, twist_rate * (total_length + 2), void = false);
    }
    module MasterVoidHelix() {
        Corkscrew(total_length + 2, twist_rate * (total_length + 2), void = true);
    }

    // --- Main Assembly ---
    difference() {
        // 1. Union all solid parts
        union() {
            // 2. Create the screw segments (bins)
            for (i = [0 : num_bins - 1]) {
                z_pos = -total_length / 2 + spacer_height_mm + i * (bin_length + spacer_height_mm) + bin_length / 2;
                rot = twist_rate * z_pos;

                translate([0, 0, z_pos]) rotate([0, 0, rot]) {
                    intersection() {
                        // "Un-transform" the master helix back to the origin to intersect with the local cylinder
                        rotate([0, 0, -rot]) translate([0, 0, -z_pos]) MasterSolidHelix();
                        // This cylinder defines the bin's axial extent
                        cylinder(h = bin_length + 0.1, d = tube_id * 2, center = true);
                    }
                }
            }

            // 3. Create the spacers
            for (i = [0 : num_bins]) {
                z_pos = -total_length / 2 + i * (bin_length + spacer_height_mm) + spacer_height_mm / 2;
                rot = twist_rate * z_pos;
                is_base = (i == 0);
                is_top = (i == num_bins);
                spacer_od = tube_id - tolerance_tube_fit;

                translate([0, 0, z_pos]) rotate([0, 0, rot]) {
                    union() {
                        difference() {
                            cylinder(d = spacer_od, h = spacer_height_mm, center = true);
                            // Cut the helical profile through the spacer
                            rotate([0, 0, -rot]) translate([0, 0, -z_pos]) MasterSolidHelix();
                            // Cut O-ring groove
                            OringGroove_OD_Cutter(spacer_od, oring_cross_section_mm);
                            // Cut sockets if threading is enabled
                            if (THREADED_INLET) {
                                if (is_top) {
                                    translate([0, 0, spacer_height_mm / 2])
                                        cylinder(d = 4 * helix_profile_radius_mm + tolerance_socket_fit, h = spacer_height_mm / 2 + 0.1);
                                }
                                if (is_base) {
                                    translate([0, 0, -spacer_height_mm / 2])
                                        cylinder(d = 4 * helix_profile_radius_mm + tolerance_socket_fit, h = spacer_height_mm / 2 + 0.1);
                                }
                            }
                        }
                        if (SHOW_O_RINGS) {
                            OringVisualizer(spacer_od, oring_cross_section_mm);
                        }
                        if (ADD_HELICAL_SUPPORT && !is_top) {
                            translate([0, 0, spacer_height_mm / 2])
                                HelicalOuterSupport(spacer_od, bin_length, support_rib_thickness_mm, twist_rate * bin_length);
                        }
                    }
                }
            }
        } // End of solid union

        // 4. Subtract the Master Void from the entire solid assembly.
        MasterVoidHelix();
    }
}


/**
 * Module: SingleCellFilter
 * Description: Creates a single filter cell inside a containing cylinder.
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
 * Description: Creates a hexagonal array of filter cells within a hexagonal casing.
 */
module HexFilterArray(layers) {
    spacing = cell_diameter + 2; // Distance between cell centers
    hex_casing_radius = sqrt(3) * spacing * (layers + 0.5);

    difference() {
        // Create the main hexagonal casing
        cylinder(h = cell_length, d = hex_casing_radius, center = true, $fn = 6);
        // Cut the inside of the casing wall
        cylinder(h = cell_length + 2, d = hex_casing_radius - 2 * outer_casing_wall_mm, center = true, $fn = 6);

        if (ADD_OUTER_O_RINGS) {
            // Add O-ring grooves to the outside flats of the hex casing
            for (a = [0:5]) {
                rotate([0, 0, a * 60 + 30]) {
                    translate([hex_casing_radius / 2, 0, cell_length / 4]) OringGroove_OD_Cutter(hex_casing_radius, oring_cross_section_mm, flat=true);
                    translate([hex_casing_radius / 2, 0, -cell_length / 4]) OringGroove_OD_Cutter(hex_casing_radius, oring_cross_section_mm, flat=true);
                }
            }
        }
    }

    // Place the filter cores into each cell location
    HexArrayLayout(layers, spacing) {
        StagedHelicalStructure(cell_length, cell_diameter, num_helices, num_stages);
    }
}


/**
 * Module: HoseAdapterEndCap
 * Description: Creates a cap for the main tube with a hose barb fitting.
 */
module HoseAdapterEndCap(tube_od, hose_id, oring_cs) {
    cap_inner_dia = tube_od - 2 * tube_wall_mm + tolerance_tube_fit;
    cap_wall = 3;
    cap_outer_dia = cap_inner_dia + 2 * cap_wall;
    cap_sleeve_height = 20;
    cap_end_plate_thick = 3;

    color(USE_TRANSLUCENCY ? [0.9, 0.9, 0.9, 0.5] : "Gainsboro")
    difference() {
        union() {
            // Main sleeve
            cylinder(d = cap_outer_dia, h = cap_sleeve_height);
            // End plate
            translate([0, 0, cap_sleeve_height])
                cylinder(d = cap_outer_dia, h = cap_end_plate_thick);
            // Hose adapter flange
            translate([0, 0, cap_sleeve_height + cap_end_plate_thick])
                cylinder(d = flange_od, h = flange_height);
        }
        // Hollow out the sleeve
        translate([0, 0, -1])
            cylinder(d = cap_inner_dia, h = cap_sleeve_height + 2);
        // Cut internal O-ring groove
        translate([0, 0, cap_sleeve_height / 2])
            OringGroove_ID_Cutter(cap_inner_dia, oring_cs);
        // Cut hole for hose
        translate([0, 0, cap_sleeve_height])
            cylinder(d = hose_id, h = cap_end_plate_thick + flange_height + 2);
    }

    // Add the hose barb
    translate([0, 0, cap_sleeve_height + cap_end_plate_thick + flange_height])
        barb(hose_id, 4);
}

// --- Helper & Utility Modules ---

/**
 * Module: StagedHelicalStructure
 * Description: Generates staged helical ramps based on stage definitions. Replaces
 * `StagedCorkscrew` and `StagedExitChannelCutter`.
 */
module StagedHelicalStructure(total_h, dia, helices, stages) {
    stage_defs = [
        [[0, 0.85]],
        [[0, 0.35], [0.45, 0.85]],
        [[0, 0.25], [0.30, 0.58], [0.63, 0.92]]
    ];
    stages_to_build = stage_defs[stages - 1];

    for (stage = stages_to_build) {
        start_z_frac = stage[0];
        end_z_frac = stage[1];
        stage_h = (end_z_frac - start_z_frac) * total_h;
        center_z = (start_z_frac + end_z_frac) / 2 * total_h - total_h / 2;
        revolutions = total_revolutions * (stage_h / total_h);

        translate([0, 0, center_z])
            MultiHelixRamp(stage_h, 360 * revolutions, dia, helices);
    }
}

/**
 * Module: MultiHelixRamp
 * Description: Creates interleaved helical ramps ("Parking Garage" style).
 */
module MultiHelixRamp(h, twist, dia, helices) {
    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices)]) {
            linear_extrude(height = h, twist = twist, center = true, slices = h * 2) {
                // 2D cross-section of a single flat ramp
                polygon(points = [
                    [0, 0],
                    [dia / 2, 0],
                    [dia / 2 * cos(ramp_width_degrees), dia / 2 * sin(ramp_width_degrees)]
                ]);
            }
            if (ADD_SLITS) {
                 // Note: This is a simple implementation of a slit. The more complex
                 // `RampedSlitKnife` module was unused and has been commented out.
                 rotate([0, 0, ramp_width_degrees / 2])
                 linear_extrude(height = h, twist = twist, center=true, slices = h > 0 ? h*2:1)
                    translate([dia/2 - slit_depth_mm/2, 0])
                        square([slit_depth_mm, slit_width_mm], center=true);
            }
        }
    }
}

/**
 * Module: HelicalOuterSupport
 * Description: Creates a lattice-like helical support structure between spacers.
 */
module HelicalOuterSupport(target_dia, target_height, rib_thickness, total_twist) {
    radius = target_dia / 2 - rib_thickness;
    for (i = [0:1:support_density - 1]) {
        rotate([0, 0, i * (360 / support_density)]) {
            union() {
                // Left-handed helix
                linear_extrude(height = target_height, twist = -total_twist)
                    translate([radius, 0, 0]) circle(d = rib_thickness);
                // Right-handed helix
                linear_extrude(height = target_height, twist = total_twist)
                    translate([radius, 0, 0]) circle(d = rib_thickness);
            }
        }
    }
}

/**
 * Module: HexArrayLayout
 * Description: A utility that arranges its children in a hexagonal grid.
 */
module HexArrayLayout(layers, spacing) {
    children(); // Center element
    if (layers > 0) {
        for (l = [1 : layers]) {
            for (a = [0 : 5]) {
                for (s = [0 : l - 1]) {
                    angle1 = a * 60;
                    angle2 = (a + 1) * 60;
                    pos = (l * spacing) * [(1 - s / l) * cos(angle1) + (s / l) * cos(angle2), (1 - s / l) * sin(angle1) + (s / l) * sin(angle2)];
                    translate(pos) children();
                }
            }
        }
    }
}

// --- O-Ring & Barb Modules ---

module OringGroove_OD_Cutter(object_dia, oring_cs, flat=false) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    cutter_dia = object_dia - 2 * groove_depth;
    
    // For cutting a groove into a flat face vs a cylindrical one
    if (flat) {
         translate([-object_dia, -groove_width/2, 0])
            cube([object_dia*2, groove_width, groove_depth]);
    } else {
        difference() {
            cylinder(d = object_dia + 0.2, h = groove_width, center = true);
            cylinder(d = cutter_dia, h = groove_width + 0.2, center = true);
        }
    }
}

module OringVisualizer(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    torus_radius = object_dia / 2 - groove_depth / 2;
    color("IndianRed")
    rotate_extrude(convexity = 10)
        translate([torus_radius, 0, 0])
        circle(r = oring_cs / 2);
}

module OringGroove_ID_Cutter(object_id, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    rotate_extrude(convexity = 10) {
        translate([object_id / 2 + groove_depth / 2, 0, 0])
            square([groove_depth, groove_width], center = true);
    }
}

// Barb library modules by Thingiverse user "jsc" (CC-BY-SA)
module barbnotch(inside_diameter) {
    cylinder(h = inside_diameter * 1.0, r1 = inside_diameter * 1.16 / 2, r2 = inside_diameter * 0.85 / 2);
}
module solidbarbstack(inside_diameter, count) {
    union() {
        barbnotch(inside_diameter);
        for (i = [2:count]) {
            translate([0, 0, (i - 1) * inside_diameter * 0.9]) barbnotch(inside_diameter);
        }
    }
}
module barb(inside_diameter, count) {
    difference() {
        solidbarbstack(inside_diameter, count);
        translate([0, 0, -0.3]) cylinder(h = inside_diameter * (count + 1), r = inside_diameter * 0.75 / 2);
    }
}


// =============================================================================
// --- E. Legacy / Unused Modules ---
// =============================================================================
/*
// NOTE: The following modules were present in the original code but appear to be
// unused by the main logic. They are preserved here for reference.

// This module seems to create a ramped cutting tool for slits, but was not
// called anywhere. The `ADD_SLITS` flag uses a simpler square profile instead.
module RampedSlitKnife(h, twist, dia, helices) {
    cutter_shape_points = [
        [dia / 2, -slit_width_mm / 2, 0], // 0
        [dia / 2, slit_width_mm / 2, 0], // 1
        [dia / 2 - 0.1, slit_width_mm / 2, 0], // 2
        [dia / 2 - 0.1, -slit_width_mm / 2, 0], // 3
        [dia / 2, -slit_width_mm / 2, slit_ramp_length_mm], // 4
        [dia / 2, slit_width_mm / 2, slit_ramp_length_mm], // 5
        [dia / 2 - slit_width_mm, slit_width_mm / 2, slit_ramp_length_mm], // 6
        [dia / 2 - slit_width_mm, -slit_width_mm / 2, slit_ramp_length_mm], // 7
    ];
    cutter_shape_faces = [
        [0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]
    ];
    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices) + ramp_width_degrees / 2]) {
            linear_extrude(height = h, twist = twist, center = true, slices = h * 2) {
                translate([dia / 2 - slit_width_mm, 0, -h / 2 + slit_ramp_length_mm / 2])
                    polyhedron(points = cutter_shape_points, faces = cutter_shape_faces);
                translate([dia / 2 - slit_width_mm, 0, -h / 2 + slit_ramp_length_mm + slit_open_length_mm / 2])
                    cube([slit_width_mm, slit_width_mm, slit_open_length_mm], center = true);
            }
        }
    }
}

// This module was not called anywhere in the main logic. It appears to be an
// alternative to the `ModularFilterAssembly` that does not use the Master Helix method.
module FlatEndScrew(h, twist, num_bins) {
    screw_outer_dia = 4 * helix_profile_radius_mm;
    intersection() {
        difference() {
            Corkscrew(h + 0.5, twist, void=false);
            CorkscrewSlitKnife(twist, h, num_bins);
        }
        cylinder(d = screw_outer_dia + 2, h = h, center = true);
    }
}

// This module was only used by the unused `FlatEndScrew` module.
module CorkscrewSlitKnife(twist, depth, num_bins) {
    pitch_mm = twist == 0 ? 1e9 : depth / (twist / 360);
    de = depth / num_bins;
    yrot = 360 * (1 / pitch_mm) * de;
    slit_axial_length_mm = 1 + 0.5;
    for (i = [0:0]) { // Original comment: "The user wants only one slit per segment..."
        j = -(num_bins - 1) / 2 + i;
        rotate([0, 0, -yrot * (j + 1)])
        translate([0, 0, (j + 1) * de])
        difference() {
            linear_extrude(height = depth, center = true, convexity = 10, twist = twist)
                translate([helix_path_radius_mm, 0, 0])
                    polygon(points = [[0, 0], [4, -2], [4, 2]]);
            translate([0, 0, slit_axial_length_mm])
                cube([15, 15, depth], center = true);
        }
    }
}
*/