// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED by Gemini.
// VERSION 21: Corrected spacer alignment, helical void concentricity, and support visibility.

// --- Model Precision ---
high_res_fn = 200;
low_res_fn = 30;
$fn = $preview ? low_res_fn : high_res_fn;

// --- Main Parameters ---
//num_bins = 1; 
//number_of_complete_revolutions = 2;
//screw_OD_mm = 1.8;
//screw_ID_mm = 1;
//scale_ratio = 1.4;

// --- NEW PARAMETERS for Tube Filter ---
// tube_od_mm = 32;
//tube_wall_mm = 1;
// insert_length_mm = 50/2;
// oring_cross_section_mm = 1.5;
// spacer_height_mm = 5;
// adapter_hose_id_mm = 30;
// support_rib_thickness_mm = 2.5;
support_revolutions = 5;
// support_density = 4; // NEW: Number of support bundles around the circumference
// flange_od = 20;           // Outer diameter of the hose adapter flange
// flange_height = 5;        // Height of the hose adapter flange

// --- Tolerances & Fit ---
// Adjust these values based on your printer's calibration
// tolerance_tube_fit = 0.2;   // Clearance between the spacers and the inner wall of the tube
// tolerance_socket_fit = 0.4; // Clearance between the screw and the spacer socket
// tolerance_channel = 0.1;  // Extra clearance for the airflow channel to prevent binding

// --- Config File ---
// Include a configuration file to override the default parameters below.
include <parameters/One_Corkscrew_param.scad>
//include <parameters/Three_Corkscrews_param.scad>
//include <parameters/TwentyOne_Corkscrews_param.scad>
//include <parameters/default_param.scad>
//include <your_awesome_parameter_variations.scad>

// --- CONTROL_VARIABLES ---
GENERATE_CFD_VOLUME   = false; // NEW: Set to true to generate the internal fluid volume for CFD analysis
USE_MASTER_HELIX_METHOD = true; // NEW: Switch between assembly strategies
USE_MODULAR_FILTER    = 1;
USE_HOSE_ADAPTER_CAP  = 0;
THREADED_INLET        = false ;
GENERATE_SLICE          = false; // <-- MODIFIED: Set to true to slice the model
// Visual Options
ADD_HELICAL_SUPPORT   = true;
USE_TRANSLUCENCY      = false;
SHOW_O_RINGS          = false;

// --- Slice Parameters (Active if GENERATE_SLICE is true) ---
slice_count             = 1;  // Your "number of slices"
slice_offset_mm         = 5;   // Your "offset for the slice" (interpreted as the gap between slices)
slice_thickness_mm      = 5;   // The thickness/height of each slice

// ===============================================================
// === Main Logic ================================================
// ===============================================================

calculated_diameter = num_screws*scale_ratio * screw_ID_mm * (num_hex +1)

if (GENERATE_CFD_VOLUME) {
    tube_id = tube_od_mm - (2 * tube_wall_mm);
    difference() {
        // 1. Start with a solid cylinder representing the inner volume of the tube
        cylinder(d = tube_id, h = insert_length_mm, center = true);
        
        // 2. Subtract the entire filter assembly
        ModularFilterAssembly(tube_id, insert_length_mm, num_bins, spacer_height_mm, oring_cross_section_mm);
    }
    
} else if (GENERATE_SLICE) { // <-- NEW BLOCK FOR SLICING

    // --- SLICE LOGIC ---
    // Use intersection() to cut the full model with a slicing "comb"
    intersection() {
        
        // --- Block 1: Generate the full model ---
        // This is the same logic as the original 'else' block.
        // The full model is generated here...
        if (USE_MODULAR_FILTER) {
            if (USE_MASTER_HELIX_METHOD) {
                ModularFilterAssembly(tube_od_mm - (2 * tube_wall_mm), insert_length_mm, num_bins, spacer_height_mm, oring_cross_section_mm);
            } else {
                ModularFilterAssembly_Rotational(tube_od_mm - (2 * tube_wall_mm), insert_length_mm, num_bins, spacer_height_mm, oring_cross_section_mm);
            }
        } else if (USE_HOSE_ADAPTER_CAP) {
            HoseAdapterEndCap(tube_od_mm, adapter_hose_id_mm, oring_cross_section_mm);
        }
        
        // --- Block 2: Generate the slicing "comb" ---
        // ...and this 'union' creates a series of cubes
        // that act as the 'knife' to slice the model.
        union() {
            // Calculate total height of the slice block to center it at Z=0
            total_slice_block_height = (slice_count * slice_thickness_mm) + (max(0, slice_count - 1) * slice_offset_mm);
            // Find the Z center of the first (bottom) slice
            start_z_center = -total_slice_block_height / 2 + slice_thickness_mm / 2;
            // Calculate distance between the centers of two slices
            slice_pitch = slice_thickness_mm + slice_offset_mm;
            
            for (i = [0 : slice_count - 1]) {
                // Calculate the center Z position for the current slice
                z_pos = start_z_center + (i * slice_pitch);
                
                // Create a large, flat cube centered at the slice's Z position
                translate([0, 0, z_pos]) {
                    // Cube is centered on X/Y/Z. Size 500 is arbitrary
                    // but large enough to cut the entire model.
                    cube([500, 500, slice_thickness_mm], center = true);
                }
            }
        }
    }
    // --- END SLICE LOGIC ---    
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

// ===== Rob's definitions ======

// coordinate system: Gravity points in the -Z direction. +Z is up.abs
// The left-right dimentions is considered X. Air flow is in the positive Y
// direction. The is a right-handed coordinate system.

module Corkscrew(h,twist) {
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm+cell_wall_mm, 0, 0])
    scale([1,scale_ratio])
    circle(r = screw_OD_mm);
}

//module CorkscrewSlitKnife(twist,depth,num_bins) {
//    de = depth/num_bins;
//    yrot = 360*(1 / pitch_mm)*de;
//    
//    // Note: The computation of the slit angle 
//    // is a complicated. We create a triangle that 
//    // we linearly extruide (in the "polygon" state below.)
//    D = 5*screw_OD_mm;
//    W = D * tan(slit_knife_angle);
// //   translate([10,0,0])
////    polygon(points = [[0,0],[D,-W],[D,W]]);   
//    echo("twist",twist);
//    echo("W",W);
//    echo("yrot",yrot);
//    echo("de",de);
//    echo("slit_axial_length_mm",slit_axial_length_mm);
//    echo("screw_OD_mm",screw_OD_mm);
//    echo("num_bins",num_bins);
//    echo("depth",depth);
//    echo("FN_RES",FN_RES);
//    rotate([90,270,0])
//    for(i = [0:num_bins -1]) {
//        translate([0,0,-de])
//        rotate([0,0,-yrot*(i+1)])
//        translate([0,0,(i+1)*de])
//        difference() {
//            linear_extrude(height = depth, center = true, convexity = 10, twist = twist, $fn = FN_RES)
//            translate([screw_OD_mm,0,0])
//            rotate([0,0,0])
//            polygon(points = [[0,0],[D,-W],[D,W]]);   
//            color("blue",0.3)
//            translate([0,0,slit_axial_length_mm])
//            cylinder(d=screw_ID_mm*8,h=depth,center=true);
//        }
//    }
//    
//}
module CorkscrewSlitKnife(twist,depth,num_bins) {
    de = depth/num_bins;
    yrot = 360*(1 / pitch_mm)*de;
    
    // Note: The computation of the slit angle 
    // is a complicated. We create a triangle that 
    // we linearly extruide (in the "polygon" state below.)
    D = 20;
    W = D * tan(slit_knife_angle); 
    echo("twist",twist);
    echo("W",W);
    echo("yrot",yrot);
    echo("de",de);
    echo("slit_axial_length_mm",slit_axial_length_mm);
    echo("screw_OD_mm",screw_OD_mm);
    echo("num_bins",num_bins);
    echo("depth",depth);
    echo("FN_RES",FN_RES);
    echo("pitch_mm",pitch_mm);
    // This should be the position of the helix at the "end"
    // where we need to start the slit.
    angle_of_knife_at_end = depth * 360 / pitch_mm;
    echo("angle_of_knife_at_end",angle_of_knife_at_end);
    rotate([90,0,0])
    for(i = [0:num_bins -1]) {
        translate([0,0,-de])
        rotate([0,0,-yrot*(i+1)])
        translate([0,0,(i+1)*de])
        difference() {
            linear_extrude(height = depth, center = true, convexity = 10, twist = twist, $fn = $fn)
            rotate([0,0,angle_of_knife_at_end])
            translate([screw_OD_mm+cell_wall_mm,0,0])
            polygon(points = [[0,0],[D,-W],[D,W]]);   
            color("blue",0.3)
            translate([0,0,slit_axial_length_mm])
            cube([150,150,depth+1],center=true);
        }
    }
    
}


module CorkscrewWithVoid(h,twist) {
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm+cell_wall_mm, 0, 0])
    difference() {
        scale([1,scale_ratio])
        circle(r = screw_OD_mm);
        scale([1,scale_ratio])
        circle(r = screw_ID_mm);
    }
}
module CorkscrewVoid(h,twist) {
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm+cell_wall_mm, 0, 0])
    scale([1,scale_ratio])
    circle(r = screw_ID_mm);
}

module CorkscrewWithoutVoid(h,twist) {
    echo("CorkscrewWithoutTwist");
    echo(scale_ratio);
    rotate([90,0,0])
    linear_extrude(height = h, center = true, convexity = 10, twist = twist, $fn = FN_RES)
    translate([screw_OD_mm+cell_wall_mm, 0, 0])
    scale([1,scale_ratio])
    circle(r = screw_OD_mm);
}

module CorkscrewWithoutVoidExcess(h,twist) {
    CorkscrewWithoutVoid(h*2,twist*2);
}
module CorkscrewInnerVoidVoidExcess(h,twist) {
    CorkscrewVoid(h*2,twist*2);
}


module CorkscrewWithSlit(depth,numbins) {
    echo("Filter_twist_degrees",filter_twist_degrees);
      difference() {
       CorkscrewWithVoid(depth,filter_twist_degrees);
        CorkscrewSlitKnife(filter_twist_degrees,depth,numbins);
    }
}




// ===============================================================
// === Module Definitions ========================================
// ===============================================================

// Unified module to generate a helical shape with a given radius.
// This ensures the solid and void helices are generated with identical logic.
module HelicalShape(h, twist, r) {

//    echo(str("Generating HelicalShape: r=", r, ", center=[", screw_OD_mm, ", 0, 0]"));
    linear_extrude(height = h, center = true, convexity = 10, twist = twist) {
        translate([screw_OD_mm+cell_wall_mm, 0, 0]) {
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
// NOTE: This no longer works with a bin_count
module ModularFilterAssembly(tube_id, total_length, bin_count, spacer_h, oring_cs) {
    echo("BIN_COUNT:");
    echo(bin_count);
    if (bin_count != 1) {
        echo("INTERNAL ERROR! THIS CODE NOW REQURIES BIN_COUNT = 1 AND IT IS NOT!");
    }

    if (num_screws > 3) {
        echo("INTERNAL ERROR! WE SUPPORT AT MOST 3 SCREWS!");
    }

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

    echo("NUM_SCREWS",num_screws);
    difference() {
        union() {
            for(i = [0:1]) {
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
                       // rotate([0,0,-rot]) translate([0,0,-z_pos]) MasterSolidHelix();
                        
                        DovetailGroove_Cutter(spacer_od, oring_cross_section_mm, is_inner=true);
                        if (is_top && THREADED_INLET) {
                            translate([0, 0, spacer_h/2])
                                cylinder(d = 4*screw_OD_mm + tolerance_socket_fit, h = spacer_h/2 + 0.1);
                        }
                        if (is_base && THREADED_INLET) {
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
                            HelicalOuterSupport(spacer_od, bin_length, support_rib_thickness_mm, support_revolutions);
                    }
                }
                }
            }
        
        HexGrid(layers = num_hex, size = hex_spacing)
        for(j = [0:num_screws -1]) {
        rotate([0,0,(360/num_screws)*j])
            // 1. Union all the solid parts together
            union() {
                // 2. Create the screw segments
                i = 0;
                    z_pos = -total_length/2 + spacer_h + i * (bin_length + spacer_h) + bin_length/2;
                    rot = twist_rate * z_pos;
                    
                    // Create the part at the origin, then move it into place.
                    translate([0, 0, z_pos]) rotate([0,0,180+rot]) {
                        intersection() {
                            // To use the master helix, we must "un-transform" it back to the origin.
                           rotate([90,0,0]) 
                           CorkscrewWithSlit(bin_length,bin_count);
    //                        // This cylinder is at the origin and defines the bin's extent.
                            cylinder(h = bin_length + 0.1, d = tube_id * 2, center=true);
                        }
                    }
                }
            }
        }               
        // this part is subtracted. 
    HexGrid(layers = num_hex, size = hex_spacing)
    union() {
       for(j = [0:num_screws -1]) {
        rotate([0,0,120*j])
        CorkscrewInnerVoidVoidExcess(bin_length,filter_twist_degrees);
        }
        }
    } // end of union   
 
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

module HexGrid(layers, size) {
    
    // Pre-calculate square root of 3
    sqrt3 = sqrt(3);

    // Loop through the 'q' coordinate (column)
    for (q = [-layers : layers]) {
        
        // Calculate the range for the 'r' coordinate (row)
        // This math ensures the grid has a hexagonal boundary
        r_min = max(-layers, -q - layers);
        r_max = min(layers, -q + layers);
        
        for (r = [r_min : r_max]) {
            
            // Convert axial (q, r) coords to cartesian (x, y)
            // This is for "pointy top" hexagons
            x_pos = size * sqrt3 * (q + r/2);
            y_pos = size * 3/2 * r;
            
            translate([x_pos, y_pos]) {
                children();
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
// ===============================================================
// Parker O-Ring Handbook – Dovetail Groove Cutter (Combined)
// Static Seal (Section 2.2.3, Table 2.5, 24° included angle)
// ===============================================================

groove_params = [
    [1.78, 1.25, 1.40, 24, 0.5],
    [2.62, 2.05, 2.10, 24, 0.7],
    [3.53, 2.80, 2.85, 24, 0.9],
    [5.33, 4.55, 4.35, 24, 1.15],
    [6.99, 5.85, 5.85, 24, 1.45]
];

// Utility function: find closest match
function search_closest(x, arr) =
    let(d = [for (a = arr) abs(a - x)])
    search(min(d), d)[0];

// ---------------------------------------------------------------
// Combined groove cutter (inner or outer based on flag)
// ---------------------------------------------------------------
module DovetailGroove_Cutter(object_dia, oring_cs, is_inner=true) {
    idx = search_closest(oring_cs, [for (g = groove_params) g[0]]);
    params = groove_params[idx];
    h = params[1];
    b = params[2];
    angle = params[3];
    r2 = params[4];

    half_angle = angle / 2;
    base_width = b - 2 * h * tan(half_angle);
    //points = [[0, -0.434304], [-1.25, -0.7], [-1.25, 0.7], [0, 0.434304]]; //inner
    //points = [[0, 0.434304], [1.25, 0.7], [1.25, -0.7], [0, -0.434304]];
    points = (!is_inner) ?
                    //[ [0, -b/2],
                    //  [h, -base_width/2],
                    //  [h,  base_width/2],
                    //  [0,  b/2] ]
                    [ [0, base_width/2],
                      [h, b/2],
                      [h, -b/2],
                      [0,  -base_width/2] ]
                :
                    [ [0, -base_width/2],
                      [-h, -b/2],
                      [-h,  b/2],
                      [0,  base_width/2] ];
                  
    echo(points);
    rotate_extrude(convexity=10)
        translate([object_dia/2 + (is_inner ? 0 : -h)+0.01, 0, 0])
            polygon(points             
            );
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
