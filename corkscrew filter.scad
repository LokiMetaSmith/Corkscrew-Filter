// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED by Gemini.
// VERSION 21: Corrected spacer alignment, helical void concentricity, and support visibility.

// --- Model Precision ---
high_res_fn = 150;
low_res_fn = 30;
$fn = $preview ? low_res_fn : high_res_fn;

// --- Main Parameters ---
num_bins = 3; 
number_of_complete_revolutions = 12;
screw_OD_mm = 1.8;
screw_ID_mm = 1;
scale_ratio = 1.4;

// --- NEW PARAMETERS for Tube Filter ---
tube_od_mm = 32;
tube_wall_mm = 1;
insert_length_mm = 350/2;
oring_cross_section_mm = 1.5;
spacer_height_mm = 5;
adapter_hose_id_mm = 30;
support_rib_thickness_mm = 1.5;
support_revolutions = 0.25;
support_density = 4; // NEW: Number of support bundles around the circumference

// --- CONTROL_VARIABLES ---
USE_MASTER_HELIX_METHOD = true; // NEW: Switch between assembly strategies
USE_MODULAR_FILTER    = 1;
USE_HOSE_ADAPTER_CAP  = 0;

// Visual Options
ADD_HELICAL_SUPPORT   = true;
USE_TRANSLUCENCY      = false;
SHOW_O_RINGS          = true;

// ===============================================================
// === Main Logic ================================================
// ===============================================================

if (USE_MODULAR_FILTER) {
    if (USE_MASTER_HELIX_METHOD) {
        // New, more robust assembly method
        ModularFilterAssembly(tube_od_mm - (2 * tube_wall_mm), insert_length_mm, num_bins, spacer_height_mm, oring_cross_section_mm);
    } else {
        // Old method kept for debugging
        ModularFilterAssembly_Rotational(tube_od_mm - (2 * tube_wall_mm), insert_length_mm, num_bins, spacer_height_mm, oring_cross_section_mm);
    }
} else if (USE_HOSE_ADAPTER_CAP) {
    HoseAdapterEndCap(tube_od_mm, adapter_hose_id_mm, oring_cross_section_mm);
}

// ===============================================================
// === Module Definitions ========================================
// ===============================================================

// Creates the helical cutting tool for the void.
module CorkscrewVoid(h, twist) {
    linear_extrude(height = h, center = true, convexity = 10, twist = twist) {
        translate([screw_OD_mm, 0, 0]) {
            scale([1, scale_ratio]) {
                circle(r = screw_ID_mm);
            }
        }
    }
}

// This module creates the solid part of the helical screw.
module CorkscrewSolid(h, twist) {
    linear_extrude(height = h, center = true, convexity = 10, twist = twist) {
        translate([screw_OD_mm, 0, 0]) {
            scale([1, scale_ratio]) {
                circle(r = screw_OD_mm);
            }
        }
    }
}

// Assembles the complete filter using the "Master Helix" method for robust alignment.
module ModularFilterAssembly(tube_id, total_length, bin_count, spacer_h, oring_cs) {
    total_spacer_length = (bin_count + 1) * spacer_h;
    total_screw_length = total_length - total_spacer_length;
    bin_length = total_screw_length / bin_count;
    total_twist = 360 * number_of_complete_revolutions;

    // --- Define Master Helices ---
    // These are the "master tools" from which the entire filter will be carved.
    module MasterSolidHelix() {
        // The master helix needs to be slightly longer for cutting operations
        CorkscrewSolid(total_length + 2, total_twist);
    }
    module MasterVoidHelix() {
        CorkscrewVoid(total_length + 2, total_twist);
    }

    // --- Main Assembly ---
    difference() {
        // 1. Union all the solid parts together
        union() {
            // 2. Create the screw segments by intersecting the Master Helix
            // with cylinders at each bin location.
            for (i = [0 : bin_count - 1]) {
                z_pos = -total_length/2 + spacer_h + i * (bin_length + spacer_h) + bin_length/2;
                translate([0, 0, z_pos]) {
                    intersection() {
                        MasterSolidHelix();
                        cylinder(h = bin_length, d = tube_id * 2, center=true); // d is arbitrary, just needs to be large
                    }
                }
            }

            // 3. Create the spacers, which are complex parts, at each spacer location.
            for (i = [0 : bin_count]) { // Note: loop to bin_count to include the top spacer
                z_pos = -total_length/2 + i * (bin_length + spacer_h) + spacer_h/2;
                is_base = (i == 0);
                is_top = (i == bin_count);

                translate([0, 0, z_pos]) {
                    // Use a module for clarity
                    Spacer(tube_id, spacer_h, bin_length, is_base, is_top, MasterSolidHelix);
                }
            }
        } // End of solid union

        // 4. Subtract the Master Void from the entire solid assembly.
        MasterVoidHelix();
    }
}

// This is a new helper module for the Master Helix method to create the spacers.
module Spacer(tube_id, height, bin_length, is_base, is_top, Cutter) {
    spacer_od = tube_id - 0.2;
    screw_flight_od = 4 * screw_OD_mm;

    // Union the visual/support parts with the main body
    union() {
        // Create the main spacer body with all necessary cuts
        difference() {
            // Start with the solid cylinder
            cylinder(d = spacer_od, h = height, center=true);

            // Cut the master helix profile
            Cutter();

            // Cut the O-ring groove
            OringGroove_OD_Cutter(spacer_od, oring_cross_section_mm);

            // Cut the screw socket if needed
            if (!is_base && !is_top) {
                translate([0, 0, -height/2])
                    cylinder(d = screw_flight_od + 0.4, h = height/2 + 0.1);
            }
        }

        // Add the visual-only O-ring
        if (SHOW_O_RINGS) {
            OringVisualizer(spacer_od, oring_cross_section_mm);
        }

        // Add the helical supports
        if (ADD_HELICAL_SUPPORT && !is_top) {
            translate([0,0,height/2])
                HelicalOuterSupport(spacer_od, bin_length, support_rib_thickness_mm, support_revolutions);
        }
    }
}


// Assembles the complete filter by stacking corkscrew sections and Capture Spacers.
module ModularFilterAssembly_Rotational(tube_id, total_length, bin_count, spacer_h, oring_cs) {
    total_spacer_length = (bin_count + 1) * spacer_h;
    total_screw_length = total_length - total_spacer_length;
    bin_length = total_screw_length / bin_count;
    // The twist is now continuous over the entire length of the assembly.
    twist_rate = (360 * number_of_complete_revolutions) / total_length;

    // Center the whole assembly vertically
    translate([0, 0, -total_length/2]) {

        // Initial spacer at the bottom.
        z_pos_base_spacer = spacer_h/2;
        translate([0,0,z_pos_base_spacer])
            rotate([0,0, twist_rate * z_pos_base_spacer])
                CaptureSpacer(tube_id, spacer_h, oring_cs, bin_length, twist_rate, is_base = true);

        // Loop to stack SOLID screw bins and spacers
        for (i = [0 : bin_count - 1]) {
            // Calculate Z position for the screw segment
            z_pos_screw = spacer_h + i * (bin_length + spacer_h) + bin_length/2;

            // The rotation of the screw is determined by its Z position.
            screw_rot = twist_rate * z_pos_screw;
            // The twist of the screw segment itself is based on its own height.
            screw_twist = twist_rate * bin_length;

            // Translate to position, then rotate.
            translate([0, 0, z_pos_screw])
                rotate([0,0,screw_rot])
                    FlatEndScrew(h = bin_length, twist = screw_twist, num_bins = bin_count);

            // Z position for the spacer that sits on TOP of the screw
            z_pos_spacer = z_pos_screw + bin_length/2 + spacer_h/2;

            // The spacer must also be rotated to match the helix at its Z-position.
            spacer_rot = twist_rate * z_pos_spacer;

            translate([0, 0, z_pos_spacer])
                rotate([0,0,spacer_rot])
                    CaptureSpacer(tube_id, spacer_h, oring_cs, bin_length, twist_rate, is_top = (i == bin_count-1), is_base = false);
        }
    }
}


// Creates a bulkhead that captures the end of a screw section.
// It now accepts a twist_rate to cut the helical profile through itself.
module CaptureSpacer(tube_id, height, oring_cs, bin_length, twist_rate, is_base=false, is_top=false) {
    spacer_od = tube_id - 0.2;
    screw_flight_od = 4 * screw_OD_mm;
    socket_depth = height / 2;

    difference() {
        // Main spacer body
        cylinder(d = spacer_od, h = height, center = true);

        // Cut the helical profile for the screw flights to pass through.
        // We use CorkscrewSolid as the cutting tool.
        CorkscrewSolid(h + 0.2, twist_rate * (height + 0.2));

        // O-ring groove on the outside
        OringGroove_OD_Cutter(spacer_od, oring_cs);

        // Socket for the screw head, cut from the bottom of the spacer.
        if (!is_base && !is_top) {
            translate([0, 0, -height/2])
                cylinder(d = screw_flight_od + 0.4, h = socket_depth + 0.1);
        }
    }

    // These parts are not differenced.
    union() {
        if (SHOW_O_RINGS) {
            OringVisualizer(spacer_od, oring_cs);
        }
        if (ADD_HELICAL_SUPPORT && !is_top) {
            translate([0,0,height/2])
                HelicalOuterSupport(spacer_od, bin_length, support_rib_thickness_mm, support_revolutions);
        }
    }
}

// Creates a corkscrew with perfectly flat ends.
// It now takes a pre-calculated twist and the number of bins.
module FlatEndScrew(h, twist, num_bins) {
    screw_outer_dia = 4 * screw_OD_mm;
    
    intersection() {
        difference() {
            // Create the main helical body, add a small tolerance
            CorkscrewSolid(h + 0.5, twist);
            // Cut slits into the helix to separate the bins
            CorkscrewSlitKnife(twist, h, num_bins);
        }
        // Use a cylinder intersection to ensure the ends are perfectly flat
        cylinder(d = screw_outer_dia + 2, h = h, center = true);
    }
}

// ... (Rest of modules are unchanged and included for completeness) ...
// This module creates the helical support structure between spacers.
// It is now fully parameterized based on the main filter settings.
module HelicalOuterSupport(target_dia, target_height, rib_thickness, revolutions) {
    twist_angle = 360 * revolutions;
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

module OringGroove_OD_Cutter(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    difference() {
        cylinder(d = object_dia + 0.2, h = groove_width, center = true);
        cylinder(d = object_dia - 2 * groove_depth, h = groove_width + 0.2, center = true);
    }
}

module OringVisualizer(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    torus_radius = object_dia/2 - groove_depth/2;
    color("IndianRed")
    rotate_extrude(convexity=10)
        translate([torus_radius, 0, 0])
        circle(r = oring_cs / 2);
}

// Creates the cutting tool for an internal O-ring groove.
module OringGroove_ID_Cutter(object_id, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    rotate_extrude(convexity=10) {
        translate([object_id/2 + groove_depth, 0, 0])
            square([groove_depth, groove_width], center=true);
    }
}

// Creates a hose adapter that caps the end of the tube.
module HoseAdapterEndCap(tube_od, hose_id, oring_cs) {
    cap_inner_dia = tube_od + 0.2;
    cap_wall = 3;
    cap_outer_dia = cap_inner_dia + 2 * cap_wall;
    cap_sleeve_height = 20;
    cap_end_plate_thick = 3;

    color(USE_TRANSLUCENCY ? [0.9, 0.9, 0.9, 0.5] : "Gainsboro")
    difference() {
        union() {
            cylinder(r = cap_outer_dia / 2, h = cap_sleeve_height);
            translate([0,0,cap_sleeve_height])
                cylinder(r = cap_outer_dia/2, h = cap_end_plate_thick);
        }
        translate([0, 0, -1])
            cylinder(r = cap_inner_dia / 2, h = cap_sleeve_height + 2);
        translate([0, 0, cap_sleeve_height / 2])
            OringGroove_ID_Cutter(cap_inner_dia, oring_cs);
        translate([0, 0, cap_sleeve_height])
            cylinder(r = hose_id / 2, h = cap_end_plate_thick + 2);
    }
    
    translate([0, 0, cap_sleeve_height + cap_end_plate_thick])
        barb(hose_id, 4);
}

module CorkscrewSlitKnife(twist,depth,num_bins) {
    pitch_mm = twist == 0 ? 1e9 : depth / (twist / 360);
    de = depth/num_bins;
    yrot = 360*(1 / pitch_mm)*de;
    slit_axial_length_mm = 1 + 0.5;

    for(i = [0:num_bins -1]) {
        j = -(num_bins-1)/2 + i;
        rotate([0,0,-yrot*(j+1)])
        translate([0,0,(j+1)*de])
        difference() {
            linear_extrude(height = depth, center = true, convexity = 10, twist = twist)
                translate([screw_OD_mm,0,0])
                polygon(points = [[0,0],[4,-2],[4,2]]);
            translate([0,0,slit_axial_length_mm])
                cube([15,15,depth],center=true);
        }
    }
}

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