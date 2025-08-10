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
support_density = 4; // NEW: Number of support bundles around the circumference
flange_od = 20;           // Outer diameter of the hose adapter flange
flange_height = 5;        // Height of the hose adapter flange

// --- Tolerances & Fit ---
// Adjust these values based on your printer's calibration
tolerance_tube_fit = 0.2;   // Clearance between the spacers and the inner wall of the tube
tolerance_socket_fit = 0.4; // Clearance between the screw and the spacer socket
tolerance_channel = 0.1;  // Extra clearance for the airflow channel to prevent binding

// --- CONTROL_VARIABLES ---
GENERATE_CFD_VOLUME   = false; // NEW: Set to true to generate the internal fluid volume for CFD analysis
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

if (GENERATE_CFD_VOLUME) {
    tube_id = tube_od_mm - (2 * tube_wall_mm);
    difference() {
        // 1. Start with a solid cylinder representing the inner volume of the tube
        cylinder(d = tube_id, h = insert_length_mm, center = true);

        // 2. Subtract the entire filter assembly
        ModularFilterAssembly(tube_id, insert_length_mm, num_bins, spacer_height_mm, oring_cross_section_mm);
    }
} else {
    // Logic to generate the solid parts for printing
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
}

// ===============================================================
// === Module Definitions ========================================
// ===============================================================

// Unified module to generate a helical shape with a given radius.
// This ensures the solid and void helices are generated with identical logic.
module HelicalShape(h, twist, r) {
    echo(str("Generating HelicalShape: r=", r, ", center=[", screw_OD_mm, ", 0, 0]"));
    linear_extrude(height = h, center = true, convexity = 10, twist = twist) {
        translate([screw_OD_mm, 0, 0]) {
            scale([1, scale_ratio]) {
                circle(r = r);
            }
        }
    }
}

// Creates the helical cutting tool for the void.
module CorkscrewVoid(h, twist) {
    HelicalShape(h, twist, screw_ID_mm + tolerance_channel);
}

// This module creates the solid part of the helical screw.
module CorkscrewSolid(h, twist) {
    HelicalShape(h, twist, screw_OD_mm);
}

// Assembles the complete filter using the "Master Helix" method for robust alignment.
module ModularFilterAssembly(tube_id, total_length, bin_count, spacer_h, oring_cs) {
    total_spacer_length = (bin_count + 1) * spacer_h;
    total_screw_length = total_length - total_spacer_length;
    bin_length = total_screw_length / bin_count;
    twist_rate = (360 * number_of_complete_revolutions) / total_length;

    // --- Define Master Helices ---
    module MasterSolidHelix() {
        CorkscrewSolid(total_length + 2, twist_rate * (total_length + 2));
    }
    module MasterVoidHelix() {
        CorkscrewVoid(total_length + 2, twist_rate * (total_length + 2));
    }

    // --- Main Assembly ---
    difference() {
        // 1. Union all the solid parts together
        union() {
            // 2. Create the screw segments
            for (i = [0 : bin_count - 1]) {
                z_pos = -total_length/2 + spacer_h + i * (bin_length + spacer_h) + bin_length/2;
                rot = twist_rate * z_pos;

                // Create the part at the origin, then move it into place.
                translate([0, 0, z_pos]) rotate([0,0,rot]) {
                    intersection() {
                        // To use the master helix, we must "un-transform" it back to the origin.
                        rotate([0,0,-rot]) translate([0,0,-z_pos]) MasterSolidHelix();
                        // This cylinder is at the origin and defines the bin's extent.
                        cylinder(h = bin_length + 0.1, d = tube_id * 2, center=true);
                    }
                }
            }

            // 3. Create the spacers
            for (i = [0 : bin_count]) {
                z_pos = -total_length/2 + i * (bin_length + spacer_h) + spacer_h/2;
                rot = twist_rate * z_pos;
                is_base = (i == 0);
                is_top = (i == bin_count);
                spacer_od = tube_id - tolerance_tube_fit;

                // Create the part at the origin, then move it into place.
                translate([0, 0, z_pos]) rotate([0,0,rot]) {
                    union() {
                        difference() {
                            cylinder(d = spacer_od, h = spacer_h, center=true);
                            // Un-transform the master helix to align with the cylinder at the origin
                            rotate([0,0,-rot]) translate([0,0,-z_pos]) MasterSolidHelix();
                            OringGroove_OD_Cutter(spacer_od, oring_cross_section_mm);
                            if (!is_base && !is_top) {
                                translate([0, 0, -spacer_h/2])
                                    cylinder(d = 4*screw_OD_mm + tolerance_socket_fit, h = spacer_h/2 + 0.1);
                            }
                        }
                        if (SHOW_O_RINGS) {
                            OringVisualizer(spacer_od, oring_cross_section_mm);
                        }
                        if (ADD_HELICAL_SUPPORT && !is_top) {
                            // The support doesn't need to be rotated because the whole spacer is now rotated.
                            translate([0,0,spacer_h/2])
                                HelicalOuterSupport(spacer_od, bin_length, support_rib_thickness_mm, twist_rate);
                        }
                    }
                }
            }
        } // End of solid union

        // 4. Subtract the Master Void from the entire solid assembly.
        MasterVoidHelix();
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
// It now uses the master twist_rate to ensure its pitch matches the main helix.
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
    cap_inner_dia = tube_od + tolerance_tube_fit;
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
            // Add the new flange for the hose barb
            translate([0,0,cap_sleeve_height + cap_end_plate_thick])
                cylinder(d = flange_od, h = flange_height);
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

    // The user wants only one slit per segment, so we will just run the loop once.
    for(i = [0:0]) {
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