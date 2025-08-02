// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED by Gemini.
// VERSION 14: Implemented optional helical supports on the outer rim of the spacers.
//common vacuum hose 1.15ID 1.34od
//tube 1 3/16"(30mm) ID 1 1/4"(32mm) OD 14"(350mm) 
//o-ring 30mm OD 27mm ID 1.5mm Width https://www.amazon.com/dp/B07D24HPPW
//tube Clear 1 3/16"(30mm) ID 1 1/4"(32mm) OD 14"(350mm) https://www.amazon.com/dp/B0DK1CNVDQ
//heat shrink coupling sealer 1-1/2"(40mm) https://www.amazon.com/dp/B0B618769H

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
support_rib_thickness_mm = 1.5; // Thickness of the new helical support
support_revolutions = 0.25;     // How many turns the support makes around the spacer

// --- CONTROL_VARIABLES ---
USE_MODULAR_FILTER    = 1;
USE_HOSE_ADAPTER_CAP  = 0;

// Visual Options
ADD_HELICAL_SUPPORT   = true;  // NEW: Set to true to add helical ribs to the spacers
USE_TRANSLUCENCY      = false;
SHOW_O_RINGS          = true;

// ===============================================================
// === Main Logic ================================================
// ===============================================================

if (USE_MODULAR_FILTER) {
    ModularFilterAssembly(tube_od_mm - (2 * tube_wall_mm), insert_length_mm, num_bins, spacer_height_mm, oring_cross_section_mm);
} else if (USE_HOSE_ADAPTER_CAP) {
    HoseAdapterEndCap(tube_od_mm, adapter_hose_id_mm, oring_cross_section_mm);
}

// ===============================================================
// === Module Definitions ========================================
// ===============================================================

// Assembles the complete filter by stacking corkscrew sections and Capture Spacers.
module ModularFilterAssembly(tube_id, total_length, bin_count, spacer_h, oring_cs) {
    total_spacer_length = (bin_count + 1) * spacer_h;
    total_screw_length = total_length - total_spacer_length;
    bin_length = total_screw_length / bin_count;

    translate([0, 0, -total_length/2]) {
        // Bottom-most spacer (solid base)
        CaptureSpacer(tube_id, spacer_h,bin_length, oring_cs, is_base = true);
        
        for (i = [0 : bin_count - 1]) {
            z_pos_screw = spacer_h + i * (bin_length + spacer_h);
            z_pos_spacer = z_pos_screw + bin_length;

            // Place the corkscrew section
            translate([0, 0, z_pos_screw + bin_length/2])
                FlatEndScrew(bin_length, number_of_complete_revolutions / bin_count);
            
            // Place the Capture Spacer on top of it
            translate([0, 0, z_pos_spacer])
                CaptureSpacer(tube_id, spacer_h,bin_length, oring_cs, is_top = (i==bin_count-1) );
        }
    }
}

// Creates a bulkhead that captures the end of a screw section.
module CaptureSpacer(tube_id, height, support_height, oring_cs, is_base=false, is_top=false) {
    module BaseSpacer() {
        spacer_od = tube_id - 0.2;
        screw_tunnel_id = screw_ID_mm * 2;
        screw_flight_od = 4 * screw_OD_mm;
        socket_depth = height / 2;

        difference() {
            // 1. Main body
            cylinder(d = spacer_od, h = height);
            
            // 2. Cutters
            // O-ring groove on the outside
            translate([0,0,height/2])
                OringGroove_OD_Cutter(spacer_od, oring_cs);
            
            // Center airflow tunnel
            cylinder(d = screw_tunnel_id + 0.2, h = height + 0.2, center=true);
            
            // Socket for the screw head
            if (!is_base) {
                translate([0, 0, -0.1])
                    cylinder(d = screw_flight_od + 0.4, h = socket_depth + 0.1);
            }
        }
    }

    union() {
        BaseSpacer();
        if (SHOW_O_RINGS) {
            spacer_od = tube_id - 0.2;
            translate([0,0,height/2])
                OringVisualizer(spacer_od, oring_cs);
        }
        // Add the helical support to the spacer
        if (ADD_HELICAL_SUPPORT && !is_top) {
        echo("hello world",support_height);
            spacer_od = tube_id - 0.2;
            translate([0,0,height])
            HelicalOuterSupport(spacer_od, support_height, support_rib_thickness_mm, support_revolutions);
        }
    }
}

// NEW: Creates a helical rib on the outside of a cylinder.
module HelicalOuterSupport(target_dia, target_height, rib_thickness, revolutions) {
    twist_angle = 360 * revolutions;
     for( i = [0:1:4]){
rotate([0,0,i*90])union(){ 
linear_extrude(	height = target_height, center = false, convexity = 7.2,
		twist = -360)rotate([0,0,0])translate([target_dia / 2 - rib_thickness,0,0])circle(d=rib_thickness);
linear_extrude(		height = target_height, center = false, convexity = 7.2,
		twist =360)rotate([0,0,120])translate([target_dia / 2 - rib_thickness,0,0])circle(d=rib_thickness);
linear_extrude(	height = target_height, center = false, convexity = 7.2,
		twist = 0)rotate([0,0,240])translate([target_dia / 2 - rib_thickness,0,0])circle(d=rib_thickness);
}
}}

// Creates a corkscrew with perfectly flat ends.
module FlatEndScrew(h, revs) {
    twist = 360 * revs;
    screw_outer_dia = 4 * screw_OD_mm;
    
    intersection() {
        difference() {
            CorkscrewWithVoid(h, twist);
            CorkscrewSlitKnife(twist, h, 3);
        }
        cylinder(d = screw_outer_dia + 2, h = h, center = true);
    }
}

// Creates the cutting tool for an external O-ring groove.
module OringGroove_OD_Cutter(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    
    difference() {
        cylinder(d = object_dia + 0.2, h = groove_width, center = true);
        cylinder(d = object_dia - 2 * groove_depth, h = groove_width + 0.2, center = true);
    }
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

// Draws a torus to represent an o-ring.
module OringVisualizer(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    torus_radius = object_dia/2 - groove_depth/2;
    echo(2*(torus_radius+oring_cs/2))
    echo(2*(torus_radius-oring_cs/2));
    color("IndianRed")
    rotate_extrude(convexity=10)
        translate([torus_radius, 0, 0])
        circle(r = oring_cs /2);
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

// ===============================================================
// === Core Geometry Modules =====================================
// ===============================================================

module Support( thickness, radius, height, iterations ) {
translate([0,0,-50])
{
 for( i = [0:1:4]){
rotate([0,0,i*90]){ 
linear_extrude(		height = 50, center = false, convexity = 7.2,
		twist = -360)rotate([0,0,0])translate([10,0,0])circle(d=1);
linear_extrude(		height = 50, center = false, convexity = 7.2,
		twist =360)rotate([0,0,120])translate([10,0,0])circle(d=1);
linear_extrude(	height = 50, center = false, convexity = 7.2,
		twist = 0)rotate([0,0,240])translate([10,0,0])circle(d=1);
}}
}}

module Screws(num_screws, num_bins, depth) {
    d = (num_screws-1)*10;
    twist = 360 * number_of_complete_revolutions;
    union() {
        for (i = [0:num_screws-1]) {
            x =  -d/2 + i * 10;
            translate([x,0,0])
                CorkscrewWithSlit(depth, num_bins, twist);
        }
    }
}

module CorkscrewWithSlit(depth, numbins, twist) {
    difference() {
        CorkscrewWithVoid(depth, twist);
        CorkscrewSlitKnife(twist, depth, numbins);
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

module CorkscrewSlitKnife(twist,depth,num_bins) {
    pitch_mm = depth / (twist / 360);
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