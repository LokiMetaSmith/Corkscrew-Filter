// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED by Gemini.
// VERSION 8: Added o-ring visualization.

// --- Model Precision ---
high_res_fn = 150;
low_res_fn = 30;
$fn = $preview ? low_res_fn : high_res_fn;

// --- Main Parameters (mm, degrees) ---
filter_height_mm = 50;
number_of_complete_revolutions = 6;
screw_OD_mm = 2;
screw_ID_mm = 1;
cell_wall_mm = 1;
slit_axial_open_length_mm = 0.5;
hex_cell_diam_mm = 10;
bin_height_z_mm = 30;
num_screws = 1;
num_bins = 3;
screw_center_separation_mm = 10;
scale_ratio = 1.4;
bin_wall_thickness_mm = 1;


// --- NEW PARAMETERS for Tube Filter Insert ---
tube_od_mm = 15;
tube_wall_mm = 1;
insert_length_mm = 40;//406.4;
insert_wall_thickness_mm = 1.5;
oring_cross_section_mm = 1.5;
adapter_hose_id_mm = 9.525;

// --- CONTROL_VARIABLES ---
USE_FILTER_INSERT     = 1;
USE_HOSE_ADAPTER_CAP  = 1;
USE_ORIGINAL_DESIGN   = 0;

// Visual Options
USE_TRANSLUCENCY      = true;   // Set to true for a see-through effect on shells.
SHOW_INSERT_SHELL     = true;   // Set to false to hide the outer tube of the insert.
SHOW_TUBE             = false;   // Set to false to hide the outer tube
SHOW_O_RINGS          = false;   // NEW: Set to true to visualize the o-rings in their grooves.

// --- Conditional Parameter Overwrite ---
if (USE_FILTER_INSERT) {
    screw_OD_mm = 1.675;
    screw_ID_mm = 0.75;
    number_of_complete_revolutions = 16;
}

// ... (Calculated variables remain the same)
filter_twist_degrees = 360*number_of_complete_revolutions;
slit_axial_length_mm = cell_wall_mm + slit_axial_open_length_mm;
bin_breadth_x_mm = (num_screws -1) * screw_center_separation_mm + screw_center_separation_mm*2;
pitch_mm = (USE_FILTER_INSERT ? insert_length_mm : filter_height_mm) / number_of_complete_revolutions;


// ===============================================================
// === Main Logic ================================================
// ===============================================================

if (USE_FILTER_INSERT) {
    FilterInsert(tube_od_mm - (2 * tube_wall_mm), insert_length_mm, insert_wall_thickness_mm, oring_cross_section_mm);
} else if (USE_HOSE_ADAPTER_CAP) {
    HoseAdapterEndCap(tube_od_mm, adapter_hose_id_mm, oring_cross_section_mm);
} else if (USE_ORIGINAL_DESIGN) {
    BinsWithScrew(num_screws, num_bins);
} 


// ===============================================================
// === Module Definitions ========================================
// ===============================================================

module FilterInsert(tube_id, filter_length, insert_wall, oring_cs) {
    insert_od = tube_id - 0.2;
    corkscrew_chamber_id = insert_od - 2 * insert_wall;

    union() {
        // 1. The outer shell (optional and translucent)
        if (SHOW_TUBE) {
            color(USE_TRANSLUCENCY ? [0.8, 0.8, 1.0, 0.4] : "LightSteelBlue")
            difference() {
                // Main body
                cylinder(r = insert_od / 2, h = filter_length, center = true);
                // Hollow center
                cylinder(r = corkscrew_chamber_id / 2, h = filter_length + 2, center = true);
            }
        }
        if (SHOW_INSERT_SHELL) {
        difference(){
            color(USE_TRANSLUCENCY ? [0.8, 0.8, 1.0, 0.4] : "LightSteelBlue")
            union(){
                // Cut grooves for o-rings
                translate([0, 0, filter_length/2 - oring_cs * 2])
 
                    OringGroove_OD_Cutter(insert_od, oring_cs);
                  
                
                translate([0, 0, -filter_length/2 + oring_cs * 2])
                 
                    OringGroove_OD_Cutter(insert_od, oring_cs);
          }
          rotate([0,0,180])CorkscrewWithoutVoid(filter_length,screw_OD_mm-2);
          }
        }
        
        // 2. The inner corkscrew mechanism
        Screws(1, num_bins, filter_length); // Using num_bins=3 for slit generation
        
        // 3. O-Ring Visualizers (optional)
        if (SHOW_O_RINGS) {
            translate([0, 0, filter_length/2 - oring_cs * 2])
                OringVisualizer(insert_od, oring_cs);
            translate([0, 0, -filter_length/2 + oring_cs * 2])
                OringVisualizer(insert_od, oring_cs);
        }
    }
}

// NEW MODULE to draw the o-rings for visualization purposes
module OringVisualizer(object_dia, oring_cs) {
    // The o-ring sits in the groove. This calculates its position.
    groove_depth = oring_cs * 0.8;
    torus_radius = object_dia/2 - groove_depth/2;

    color("IndianRed") // A rubber-like color
    rotate_extrude(convexity=10)
        translate([torus_radius, 0, 0])
        circle(r = oring_cs / 2);
}

module HoseAdapterEndCap(tube_od, hose_id, oring_cs) {
    cap_inner_dia = tube_od + 0.2;
    cap_wall = 3;
    cap_outer_dia = cap_inner_dia + 2 * cap_wall;
    cap_sleeve_height = 20;
    cap_end_plate_thick = 3;

    // 1. Main body of the cap (optionally translucent)
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
    
    // 2. Add hose barb to the end plate (always opaque)
    translate([0, 0, cap_sleeve_height + cap_end_plate_thick])
        barb(hose_id, 4);
}

module OringGroove_OD_Cutter(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    union() {
    rotate_extrude(convexity=10) {
        translate([object_dia/2 - groove_depth, 0, 0])
        difference(){
            square([groove_depth, groove_width], center=true);
            translate([oring_cs/2,0,0])
            circle(r=insert_od);
        }
    }
    cylinder(d=object_dia- 2*groove_depth-oring_cs/2,h=oring_cs, center=true);
}
}

module OringGroove_ID_Cutter(object_id, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    rotate_extrude(convexity=10) {
        translate([object_id/2 + groove_depth, 0, 0])
            square([groove_depth, groove_width], center=true);
    }
}

// ===============================================================
// === ORIGINAL CODEBASE (with corrections) ======================
// ===============================================================

module Corkscrew(h,twist) {
    linear_extrude(height = h, center = true, convexity = 10, twist = twist)
    translate([screw_OD_mm, 0, 0])
    scale([1,scale_ratio])
    circle(r = screw_OD_mm);
}

module CorkscrewSlitKnife(twist,depth,num_bins) {
    de = depth/num_bins;
    yrot = 360*(1 / pitch_mm)*de;
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

module CorkscrewWithVoid(h,twist) {
    linear_extrude(height = h, center = true, convexity = 10, twist = twist)
    translate([screw_OD_mm, 0, 0])
    difference() {
        scale([1,scale_ratio])
        circle(r = screw_OD_mm);
        scale([1,scale_ratio])
        circle(r = screw_ID_mm);
    }
}

module CorkscrewWithoutVoid(h,twist) {
    linear_extrude(height = h, center = true, convexity = 10, twist = twist)
    translate([screw_OD_mm, 0, 0])
    scale([1,scale_ratio])
    circle(r = screw_OD_mm);
}

module CorkscrewWithSlit(depth,numbins) {
      difference() {
        CorkscrewWithVoid(depth,filter_twist_degrees);
        CorkscrewSlitKnife(filter_twist_degrees,depth,numbins);
    }
}

module Screws(num_screws,num_bins,depth) {
    d = (num_screws-1)*screw_center_separation_mm;
    union() {
        for (i = [0:num_screws-1]) {
            x =  -d/2+ i * screw_center_separation_mm;
            translate([x,0,0])
            CorkscrewWithSlit(depth,num_bins);
        }
    }
}


// --- Barb library modules ---

module barbnotch( inside_diameter ) {
    // CORRECTED barb geometry by swapping r1 and r2.
    // r1 is the base (lip) of the barb, r2 is the top (ramp).
    // The hose slides on from the top, so r2 must be smaller than r1.
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