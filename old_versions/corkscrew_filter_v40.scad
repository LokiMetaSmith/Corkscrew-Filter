// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED and Refactored by Gemini.and by Lawrence
// VERSION DOCUMENTED:
// - Added comprehensive documentation to all sections, parameters, and modules.
// - Included inline comments for complex calculations and logic.
// - The goal is to make the file self-explanatory for ease of use and modification.

// --- OVERVIEW ---
// This OpenSCAD file is a parametric generator for a highly customizable, modular filter system.
// By changing the variables in the "High-Level Control Panel" below, you can generate
// different parts of the filter assembly, enable or disable features, and change dimensions.

// --- HOW TO USE ---
// 1.  Select the part you want to create using the `part_to_generate` variable.
// 2.  Choose an inlet style for the modular filter using `inlet_type`.
// 3.  Toggle other features on or off using the boolean flags (e.g., `ADD_HELICAL_SUPPORT`).
// 4.  Adjust dimensions and tolerances in the "Model Parameters" section as needed.
// 5.  Press F5 to preview and F6 to render the final model.

// =============================================================================
// --- A. High-Level Control Panel ---
// =============================================================================

// --- 1. Model Selection ---
// This variable controls which component is rendered.
part_options = ["modular_filter_assembly", "hex_array_filter", "single_cell_filter", "hose_adapter_cap", "flat_end_screw"];
part_to_generate = part_options[4]; // Change the index (e.g., to part_options[1]) or the string to select a different part.

// --- 2. Feature Flags ---
// These flags toggle optional features on the selected model.

// --- Modular Filter & Flat End Screw Features ---
inlet_options = ["none", "threaded", "pressfit", "barb"];
inlet_type = inlet_options[1];              // Inlet style for the end spacers of the modular filter. ["none", "threaded", "barb"]
GENERATE_CFD_VOLUME = false;     // If true, generates the negative space (fluid volume) for CFD analysis instead of the solid part.
ADD_HELICAL_SUPPORT = true;      // If true, adds a lattice-like support structure between the spacers for rigidity.

// --- Hex/Single Cell Features ---
slit_options = ["none", "simple", "ramped"];
slit_type = slit_options[2];            // Defines the type of slit cut into the helical ramps. ["none", "simple", "ramped"]
ADD_OUTER_O_RINGS = true;        // If true, adds O-Ring grooves to the outer hexagonal casing.

// --- Visual/Debug Options ---
SHOW_O_RINGS = true;             // If true, renders red O-rings in their grooves for visualization.
USE_TRANSLUCENCY = false;        // If true, makes certain parts semi-transparent to see internal geometry.

// =============================================================================
// --- B. Model Parameters ---
// =============================================================================

// --- General & Precision ---
high_res_fn = 150; // Fragment resolution for final renders ($fn). Higher values create smoother curves.
low_res_fn = 30;   // Fragment resolution for previews. Lower values provide faster previews.
$fn = $preview ? low_res_fn : high_res_fn; // OpenSCAD automatically uses the appropriate value.

// --- Tube & Main Assembly Parameters ---
tube_od_mm = 32;                 // The outer diameter of the tube the filter assembly will be inserted into.
tube_wall_mm = 1;                // The wall thickness of the tube. Used to calculate the inner diameter.
insert_length_mm = 350 / 2;      // The total length of the filter insert from end to end.
num_bins = 3;                    // The number of separate helical screw segments in the modular assembly.

// --- Helical Screw Parameters ---
number_of_complete_revolutions = 12; // How many full 360-degree turns the screw makes over its total length.
helix_path_radius_mm = 1.8;      // The radius of the helical path, measured from the central axis to the center of the screw's profile.
helix_profile_radius_mm = 1.8;   // The radius of the circular cross-section of the solid screw itself.
helix_void_profile_radius_mm = 1; // The radius of the circular cross-section of the channel (the void) inside the screw.
helix_profile_scale_ratio = 1.4; // Stretches the screw's circular profile along one axis to create an ellipse, increasing surface area.

// --- Spacer & O-Ring Parameters ---
spacer_height_mm = 5;            // The axial height of each spacer disk.
oring_cross_section_mm = 1.5;    // The diameter of the O-ring cord.

// --- Helical Support Parameters ---
support_rib_thickness_mm = 2.5;  // The diameter of the individual struts that make up the helical support.
support_revolutions = 4;         // The number of revolutions the support struts make. (Note: This is not currently used, twist is derived from the main helix).
support_density = 4;             // The number of support bundles distributed around the circumference.

// --- Hose Adapter Cap Parameters ---
adapter_hose_id_mm = 30;         // The inner diameter of the hose that will connect to the end cap adapter.
flange_od = 20;                  // The outer diameter of the flange on the hose adapter.
flange_height = 5;               // The height of the flange on the hose adapter.

// --- Inlet Parameters (for Modular Filter) ---
// Threaded Inlet
threaded_inlet_id_mm = 4;        // The outer diameter of the threaded portion of the inlet.
threaded_inlet_flange_od = threaded_inlet_id_mm + 4; // The diameter of the flange at the base of the threaded inlet.
threaded_inlet_height = 10;      // The height of the threaded inlet.
// Barb Inlet
barb_inlet_id_mm = 4;            // The inner diameter of the hose barb.
barb_inlet_count = 3;            // The number of individual barbs on the fitting.
barb_inlet_flange_od = barb_inlet_id_mm + 4; // The diameter of the flange at the base of the barb inlet.

// --- Hex Array & Single Cell Filter Parameters ---
cell_diameter = 10;              // The outer diameter of the helical filter within a single cell.
cell_length = 100;               // The total Z-height (length) of a filter cell.
num_helices = 1;                 // The number of interleaved helical ramps (e.g., like a multi-start thread).
ramp_width_degrees = 20;         // The angular width of a single helical ramp.
total_revolutions = 8;           // The number of full turns a helix makes over the `cell_length`.
num_stages = 3;                  // The number of stacked, separated helical segments within a single cell. [1, 2, or 3]
hex_array_layers = 1;            // The number of hexagonal rings around the central cell (0=1 cell, 1=7 cells, 2=19 cells).
outer_casing_wall_mm = 3;        // The wall thickness of the hexagonal casing for the array.

// --- Slit Parameters ---
slit_ramp_length_mm = 5;         // The length of the ramped portion of a slit (for "ramped" `slit_type`).
slit_open_length_mm = 10;        // The length of the fully open portion of a slit.
slit_width_mm = 2;               // The width of the slit opening.
slit_depth_mm = 2;               // The depth of the slit cut into the ramp.

// --- Tolerances & Fit ---
tolerance_tube_fit = 0.2;        // Clearance between the spacers and the inner wall of the main tube.
tolerance_socket_fit = 0.4;      // Clearance for sockets and recesses, like for the inlet flange.
tolerance_channel = 0.1;         // Extra clearance for the helical void to prevent binding during assembly.

// --- Config File (Optional Override) ---
// To use, create a file named "filter_config.scad" with parameter overrides.
// Example: `num_bins = 5;`
// include <filter_config.scad>

// =============================================================================
// --- C. Main Logic ---
// =============================================================================

// This block acts as the main program, calling the correct top-level module
// based on the `part_to_generate` variable set in the control panel.
if (part_to_generate == "modular_filter_assembly") {
    tube_id = tube_od_mm - (2 * tube_wall_mm);
    if (GENERATE_CFD_VOLUME) {
        difference() {
            cylinder(d = tube_id, h = insert_length_mm, center = true);
            ModularFilterAssembly(tube_id, insert_length_mm);
        }
    } else {
        ModularFilterAssembly(tube_id, insert_length_mm);
    }
} else if (part_to_generate == "hex_array_filter") {
    HexFilterArray(hex_array_layers);
} else if (part_to_generate == "single_cell_filter") {
    SingleCellFilter();
} else if (part_to_generate == "hose_adapter_cap") {
    HoseAdapterEndCap(tube_od_mm, adapter_hose_id_mm, oring_cross_section_mm);
} else if (part_to_generate == "flat_end_screw") {
    total_twist = 360 * number_of_complete_revolutions;
    FlatEndScrew(insert_length_mm, total_twist, num_bins);
}

// =============================================================================
// --- D. Module Definitions ---
// =============================================================================

// --- Core Component Modules ---

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
 * Description: A wrapper for `HelicalShape` that creates either the solid part of the screw
 * or the void (the internal channel, used as a cutting tool).
 * Arguments:
 * h:     The height of the corkscrew.
 * twist: The total twist angle in degrees.
 * void:  (boolean) If false, generates the solid screw. If true, generates the larger void for cutting.
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
    // These modules define full-length "template" helices. Slices of these templates are
    // used to build the final parts. This ensures perfect continuity and alignment.
    module MasterSolidHelix() { Corkscrew(total_length + 2, twist_rate * (total_length + 2), void = false); }
    module MasterVoidHelix() { Corkscrew(total_length + 2, twist_rate * (total_length + 2), void = true); }

    difference() {
        union() {
            // --- Create the screw segments (bins) ---
            for (i = [0 : num_bins - 1]) {
                // Calculate the Z-position and required rotation for this segment.
                z_pos = -total_length / 2 + spacer_height_mm + i * (bin_length + spacer_height_mm) + bin_length / 2;
                rot = twist_rate * z_pos; // Rotation ensures the helix phase is correct at this height.
                
                // Move to the calculated position and apply rotation.
                translate([0, 0, z_pos]) rotate([0, 0, rot]) {
                    // Isolate a segment of the Master Helix.
                    intersection() {
                        // "Un-transform" the master helix back to the origin. This clever trick allows us
                        // to use a single master shape for all segments.
                        rotate([0, 0, -rot]) translate([0, 0, -z_pos]) MasterSolidHelix();
                        // The cylinder defines the length of this specific segment.
                        cylinder(h = bin_length + 0.1, d = tube_id * 2, center = true);
                    }
                }
            }
            
            // --- Create the spacers ---
            for (i = [0 : num_bins]) {
                // Calculate position and rotation for each spacer.
                z_pos = -total_length / 2 + i * (bin_length + spacer_height_mm) + spacer_height_mm / 2;
                rot = twist_rate * z_pos;
                is_base = (i == 0);
                is_top = (i == num_bins);
                spacer_od = tube_id - tolerance_tube_fit;
                
                // Move to the calculated position and apply rotation.
                translate([0, 0, z_pos]) rotate([0, 0, rot]) {
                    union() {
                        // --- Create the main spacer body ---
                        difference() {
                            cylinder(d = spacer_od, h = spacer_height_mm, center = true); // Solid spacer disk.
                            rotate([0, 0, -rot]) translate([0, 0, -z_pos]) MasterSolidHelix(); // Cut the helical profile through it.
                            union(){
                            OringGroove_OD_Cutter(spacer_od, oring_cross_section_mm); // Cut the O-ring groove.
                            
                            // Cut a recess for the selected inlet type's flange.
                            if ((is_top || is_base) && inlet_type != "none") {
                                
                                recess_d =(inlet_type == "threaded")
                                    ? threaded_inlet_flange_od + tolerance_socket_fit
                                    : (inlet_type == "pressfit")
                                    ? threaded_inlet_flange_od + tolerance_socket_fit
                                    : barb_inlet_flange_od - tolerance_socket_fit;
                                if (is_top) {
                                translate([0, 0,   0.1])
                                     cylinder(d = recess_d,  h = spacer_height_mm/2);
                                } else { // is_base
                                     translate([0, 0, -spacer_height_mm / 2-0.1]) cylinder(d = recess_d, h = spacer_height_mm/2);
                                }
                            }
                        }
                        }
                        // --- Add optional components to the spacer ---
                        // Add the selected inlet part to the top and bottom spacers.
                        if (is_top || is_base) {
                            if (inlet_type == "pressfit") {
                                translate([0, 0, is_top ? spacer_height_mm / 2 : -spacer_height_mm / 2]) 
                                    mirror([0, 0, is_top ? 0 : 1]) 
                                        ThreadedInlet();
                            } else if (inlet_type == "barb") {
                                translate([0, 0, is_top ? (spacer_height_mm / 2)-.2 : -spacer_height_mm / 2]) 
                                    mirror([0, 0, is_top ? 0 : 1]) 
                                        BarbInlet();
                            }
                        }
                        
                        if (SHOW_O_RINGS) { OringVisualizer(spacer_od, oring_cross_section_mm); }
                        if (ADD_HELICAL_SUPPORT && !is_top) { translate([0, 0, spacer_height_mm / 2]) HelicalOuterSupport(spacer_od, bin_length, support_rib_thickness_mm, twist_rate * bin_length); }
                    }
                }
            }
        }
        // Finally, subtract the master void from the entire assembly to create the internal channel.
        MasterVoidHelix();
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
    screw_outer_dia = 2 * (helix_path_radius_mm + helix_profile_radius_mm) * 2;
    intersection() {
        difference() {
            Corkscrew(h + 0.5, twist, void = false);
            CorkscrewSlitKnife(twist, h, num_bins);
        }
        cylinder(d = screw_outer_dia + 2, h = h, center = true);
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
    difference() {
        cylinder(h = cell_length, d = hex_casing_radius, center = true, $fn = 6);
        cylinder(h = cell_length + 2, d = hex_casing_radius - 2 * outer_casing_wall_mm, center = true, $fn = 6);
        if (ADD_OUTER_O_RINGS) {
            for (a = [0:5]) {
                rotate([0, 0, a * 60 + 30]) {
                    translate([hex_casing_radius / 2, 0, cell_length / 4]) OringGroove_OD_Cutter(hex_casing_radius, oring_cross_section_mm, flat = true);
                    translate([hex_casing_radius / 2, 0, -cell_length / 4]) OringGroove_OD_Cutter(hex_casing_radius, oring_cross_section_mm, flat = true);
                }
            }
        }
    }
    HexArrayLayout(layers, spacing) {
        StagedHelicalStructure(cell_length, cell_diameter, num_helices, num_stages);
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
            cylinder(d = cap_outer_dia, h = cap_sleeve_height);
            translate([0, 0, cap_sleeve_height]) cylinder(d = cap_outer_dia, h = cap_end_plate_thick);
            translate([0, 0, cap_sleeve_height + cap_end_plate_thick]) cylinder(d = flange_od, h = flange_height);
        }
        translate([0, 0, -1]) cylinder(d = cap_inner_dia, h = cap_sleeve_height + 2);
        translate([0, 0, cap_sleeve_height / 2]) OringGroove_ID_Cutter(cap_inner_dia, oring_cs);
        translate([0, 0, cap_sleeve_height]) cylinder(d = hose_id, h = cap_end_plate_thick + flange_height + 2);
    }
    translate([0, 0, cap_sleeve_height + cap_end_plate_thick + flange_height]) barb(hose_id, 4);
}


// --- Helper & Utility Modules ---

/**
 * Module: StagedHelicalStructure
 * Description: Generates the helical filter core for the Hex Array and Single Cell filters.
 * It creates stacked helical stages with gaps between them and applies the selected slit cutter.
 * Arguments:
 * total_h: The total height of the cell.
 * dia:     The outer diameter of the helical structure.
 * helices: The number of interleaved helices.
 * stages:  The number of stages to build (1, 2, or 3).
 */
module StagedHelicalStructure(total_h, dia, helices, stages) {
    stage_defs = [ [[0, 0.85]], [[0, 0.35], [0.45, 0.85]], [[0, 0.25], [0.30, 0.58], [0.63, 0.92]] ];
    stages_to_build = stage_defs[stages - 1];

    for (stage = stages_to_build) {
        start_z_frac = stage[0];
        end_z_frac = stage[1];
        stage_h = (end_z_frac - start_z_frac) * total_h;
        center_z = (start_z_frac + end_z_frac) / 2 * total_h - total_h / 2;
        revolutions = total_revolutions * (stage_h / total_h);
        twist = 360 * revolutions;

        translate([0, 0, center_z]) {
            difference() {
                MultiHelixRamp(stage_h, twist, dia, helices);
                if (slit_type == "simple") {
#                    SimpleSlitCutter(stage_h, twist, dia, helices);
                } else if (slit_type == "ramped") {
                    RampedSlitKnife(stage_h, twist, dia, helices);
                }
            }
        }
    }
}

/**
 * Module: MultiHelixRamp
 * Description: Creates the solid, interleaved helical ramps (like a parking garage ramp).
 * Arguments:
 * h:       The height of the ramp.
 * twist:   The total twist angle in degrees.
 * dia:     The outer diameter of the ramp.
 * helices: The number of interleaved ramps to create.
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
            if (slit_type != "none") { // this needs to be unified with the slip_type global variable
                 // Note: This is a simple implementation of a slit. The more complex
                 // `RampedSlitKnife` module was unused and has been commented out.
                 rotate([0, 0, ramp_width_degrees / 2])
                 linear_extrude(height = h, twist = twist, center=true, slices = h > 0 ? h*2:1)
                    translate([dia/2 - slit_depth_mm/2, 0])
                        square([slit_depth_mm, slit_width_mm], center=true);
            }
            else{
                polygon(points = [ [0, 0], [dia / 2, 0], [dia / 2 * cos(ramp_width_degrees), dia / 2 * sin(ramp_width_degrees)] ]);

            }
        }
    }
}

/**
 * Module: HelicalOuterSupport
 * Description: Creates a lattice-like helical support structure that connects spacers in
 * the modular assembly, adding rigidity.
 * Arguments:
 * target_dia:      The outer diameter that the support structure should conform to.
 * target_height:   The height of the support structure (i.e., the length of a screw segment).
 * rib_thickness:   The diameter of the individual support struts.
 * total_twist:     The total twist angle over the height, ensuring it matches the main screw.
 */
module HelicalOuterSupport(target_dia, target_height, rib_thickness, twist_rate) {
    twist_angle = twist_rate * target_height;
    radius = target_dia / 2 - rib_thickness;

    // The for-loop creates rotational symmetry based on support_density
    for( i = [0:1:support_density-1]){
        rotate([0,0,i*(360/support_density)]) {
            // This union creates a bundle of 3 struts at different angles
            union() {
                // Left-handed helix
                linear_extrude(height = target_height, center = false, convexity = 10, twist = -twist_angle)
                    rotate([0,0,0])
                        translate([radius,0,0])
                            circle(d=rib_thickness);
                // Right-handed helix
                linear_extrude(height = target_height, center = false, convexity = 10, twist = twist_angle)
                    rotate([0,0,120])
                        translate([radius,0,0])
                            circle(d=rib_thickness);
                // Straight strut
                linear_extrude(height = target_height, center = false, convexity = 10, twist = 0)
                    rotate([0,0,240])
                        translate([radius,0,0])
                            circle(d=rib_thickness);
            }
        }
    }
}
/**
 * Module: HexArrayLayout
 * Description: A powerful utility module that arranges any child elements into a hexagonal grid.
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

// --- Inlet Component Modules ---

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

// --- Slit Cutter Modules ---

/**
 * Module: SimpleSlitCutter
 * Description: Creates a simple rectangular helical cutting tool for making slits.
 * Arguments: (Same as MultiHelixRamp)
 */
module SimpleSlitCutter(h, twist, dia, helices) {
    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices) + ramp_width_degrees / 2])
        linear_extrude(height = h, twist = twist, center = true, slices = h > 0 ? h * 2 : 1)
            translate([dia +0.1 - slit_depth_mm / 2, 0])
                square([slit_depth_mm, slit_width_mm], center = true);
    }
}

/**
 * Module: RampedSlitKnife
 * Description: Creates a more complex cutting tool for making slits with a ramped lead-in.
 * Arguments: (Same as MultiHelixRamp)
 */
module RampedSlitKnife(h, twist, dia, helices) {
    // Define the 3D shape of the cutting tool using a polyhedron
    // This creates a single ramped cutter.
    cutter_shape_points = [
        // Bottom face (thin start of ramp)
        [dia/2, -slit_width_mm/2, 0],                // 0
        [dia/2,  slit_width_mm/2, 0],                // 1
        [dia/2-0.1,  slit_width_mm/2, 0],            // 2
        [dia/2-0.1, -slit_width_mm/2, 0],            // 3
        // Top face (full size end of ramp)
        [dia/2, -slit_width_mm/2, slit_ramp_length_mm], // 4
        [dia/2,  slit_width_mm/2, slit_ramp_length_mm], // 5
        [dia/2-slit_width_mm,  slit_width_mm/2, slit_ramp_length_mm], // 6
        [dia/2-slit_width_mm, -slit_width_mm/2, slit_ramp_length_mm], // 7
    ];
    cutter_shape_faces = [
        [0,1,2,3], [4,5,6,7], [0,1,5,4], [1,2,6,5], [2,3,7,6], [3,0,4,7]
    ];

    // Main open part of the slit
    //cube([slit_width_mm, slit_width_mm, slit_open_length_mm]);

    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices) + ramp_width_degrees/2]) {
            // Apply the same helical transformation as the ramp itself
            linear_extrude(height=h, twist=twist, center=true, slices=h*2) {
                 // Place the ramp and slit cutters in the 2D space
                 // This is a simplified placement and may require further tuning.
                 translate([dia/2 - slit_width_mm, 0, -h/2 + slit_ramp_length_mm/2])
                            polyhedron(points = cutter_shape_points, faces = cutter_shape_faces);

                 translate([dia/2 - slit_width_mm, 0, -h/2 + slit_ramp_length_mm + slit_open_length_mm/2])
                    cube([slit_width_mm, slit_width_mm, slit_open_length_mm], center=true);
            }
        }
    }
}

/**
 * Module: CorkscrewSlitKnife
 * Description: Creates cutting tools to separate bins on the `FlatEndScrew` model.
 * Arguments: (Same as FlatEndScrew)
 */
module CorkscrewSlitKnife(twist, depth, num_bins) {
    pitch_mm = twist == 0 ? 1e9 : depth / (twist / 360);
    de = depth / num_bins;
    yrot = 360 * (1 / pitch_mm) * de;
    slit_axial_length_mm = 1.5;

    for (i = [1:num_bins-1]) {
        j = -num_bins/2 + i;
        rotate([0, 0, -yrot * j])
        translate([0, 0, j * de])
            linear_extrude(height = slit_axial_length_mm, center = true, twist = twist / depth * slit_axial_length_mm)
                translate([helix_path_radius_mm, 0, 0])
                    polygon(points = [[0, 0], [helix_profile_radius_mm*2, -helix_profile_radius_mm*2], [helix_profile_radius_mm*2, helix_profile_radius_mm*2]]);
    }
}

// --- O-Ring & Barb Primitives ---

/**
 * Module: OringGroove_OD_Cutter
 * Description: Creates a cutting tool for an O-ring groove on an outer cylindrical or flat surface.
 * Arguments:
 * object_dia: The diameter of the object to cut the groove into.
 * oring_cs:   The cross-section diameter of the O-ring.
 * flat:       (boolean) If true, creates a straight cutter for a flat face instead of a toroidal one.
 */
module OringGroove_OD_Cutter(object_dia, oring_cs, flat = false) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    cutter_dia = object_dia - 2 * groove_depth;
    if (flat) { translate([-object_dia, -groove_width / 2, 0]) cube([object_dia * 2, groove_width, groove_depth]); }
    else { difference() { cylinder(d = object_dia + 0.2, h = groove_width, center = true); cylinder(d = cutter_dia, h = groove_width + 0.2, center = true); } }
}

/**
 * Module: OringVisualizer
 * Description: Renders a torus shape to represent an O-ring for visualization purposes.
 * Arguments:
 * object_dia: The diameter of the object the O-ring sits on.
 * oring_cs:   The cross-section diameter of the O-ring.
 */
module OringVisualizer(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    torus_radius = object_dia / 2 - groove_depth / 2;
    color("IndianRed") rotate_extrude(convexity = 10) translate([torus_radius, 0, 0]) circle(r = oring_cs / 2);
}

/**
 * Module: OringGroove_ID_Cutter
 * Description: Creates a cutting tool for an O-ring groove on an inner cylindrical surface.
 * Arguments:
 * object_id: The inner diameter of the object to cut the groove into.
 * oring_cs:  The cross-section diameter of the O-ring.
 */
module OringGroove_ID_Cutter(object_id, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    rotate_extrude(convexity = 10) translate([object_id / 2 + groove_depth / 2, 0, 0]) square([groove_depth, groove_width], center = true);
}

/**
 * Barb library modules by Thingiverse user "jsc" (CC-BY-SA)
 * Description: A set of primitive modules for creating standard hose barbs.
 */
// --- Barb library modules ---
module barbnotch( inside_diameter ) {
    cylinder(
        h = inside_diameter * 1.0,
        r1 = inside_diameter * 1.16 / 2, // Lip of the barb (wider)
        r2 = inside_diameter * 0.85 / 2, // Ramp of the barb (narrower)
        $fa = $preview ? 10 : 2,
        $fs = $preview ? 2 : 0.5
    );
}

module solidbarbstack( inside_diameter, count ) {
    union() {
        barbnotch( inside_diameter );
        for (i=[2:count]) {
            translate([0,0,(i-1) * inside_diameter * 0.9]) barbnotch( inside_diameter );
        }
    }
}

module barb( inside_diameter, count ) {
    difference() {
        solidbarbstack( inside_diameter, count );
        translate([0,0,-0.3]) cylinder(
            h = inside_diameter * (count + 1),
            r = inside_diameter * 0.75 / 2,
            $fa = $preview ? 10 : 2,
            $fs = $preview ? 2 : 0.5
        );
    }
}