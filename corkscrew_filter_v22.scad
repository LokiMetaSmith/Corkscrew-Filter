// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED by Gemini.
// VERSION 34: Added debris exit channels through the main hexagonal frame.

// --- Model Precision ---
high_res_fn = 150;
low_res_fn = 30;
$fn = $preview ? low_res_fn : high_res_fn;

// --- Main Filter Parameters ---
cell_diameter = 10;
cell_length = 100;
num_helices = 3;
ramp_width_degrees = 20;
total_revolutions = 8;

// --- Staging Parameters ---
num_stages = 3;

// --- Slit & Channel Parameters ---
ADD_SLITS = true;
slit_width_mm = 1.5;
slit_depth_mm = 2;

// --- Array & Casing Parameters ---
hex_array_layers = 1;
outer_casing_wall_mm = 3;
ADD_OUTER_O_RINGS = true;

// --- CONTROL_VARIABLES ---
USE_HEX_ARRAY_FILTER    = 1;
USE_SINGLE_CELL_FILTER  = 0;

// ===============================================================
// === Main Logic ================================================
// ===============================================================

if (USE_HEX_ARRAY_FILTER) {
    HexFilterArray(hex_array_layers);
} else if (USE_SINGLE_CELL_FILTER) {
    SingleCellFilter();
}

// ===============================================================
// === Module Definitions ========================================
// ===============================================================

module HexFilterArray(layers) {
    inner_tube_wall_mm = 1;
    spacing = cell_diameter + inner_tube_wall_mm*2 + 2;
    hex_core_radius = layers * spacing + spacing/2;
    casing_od = hex_core_radius * 2 + outer_casing_wall_mm * 2;
    
    // Final Assembly
    union() {
        // 1. The outer casing with O-ring grooves
//        difference() {
//            cylinder(d = casing_od, h = cell_length, center = true);
//            cylinder(d = casing_od - 2*outer_casing_wall_mm, h = cell_length + 2, center = true);
//            if (ADD_OUTER_O_RINGS) {
//                oring_cs = 2.5;
//                translate([0,0, cell_length/2 - oring_cs*2]) OringGroove_OD_Cutter(casing_od, oring_cs);
//                translate([0,0, -cell_length/2 + oring_cs*2]) OringGroove_OD_Cutter(casing_od, oring_cs);
//            }
//        }
        
        // 2. The filter block with cores inserted
        union() {
            // The solid frame, now with exit channels cut into it
            difference() {
                cylinder(r = hex_core_radius, h = cell_length, center=true, $fn=6);
                
                // Drill the center holes for each cell
                HexArrayLayout(layers, spacing) {
                    cylinder(d = cell_diameter, h = cell_length + 2, center=true);
                }
                
                // NEW: Subtract the exit channels for the slits
                if (ADD_SLITS) {
                    HexArrayLayout(layers, spacing) {
                        StagedExitChannelCutter(cell_length, cell_diameter, num_helices, num_stages);
                    }
                }
            }

            // The filter cores (helices)
            HexArrayLayout(layers, spacing) {
                StagedCorkscrew(cell_length, cell_diameter, num_helices, num_stages);
            }
        }
    }
}

// Lays out children in a hexagonal pattern.
module HexArrayLayout(layers, spacing) {
    children();
    if (layers > 0) for (l = [1 : layers]) for (a = [0 : 5]) for (s = [0 : l - 1]) {
        angle1 = a * 60; angle2 = (a+1) * 60;
        pos = (l * spacing) * [ (1-s/l)*cos(angle1) + (s/l)*cos(angle2), (1-s/l)*sin(angle1) + (s/l)*sin(angle2) ];
        translate(pos) children();
    }
}

// Generates the staged helical ramps.
module StagedCorkscrew(total_h, dia, helices, stages) {
    stage_defs = [ [[0, 0.85]], [[0, 0.35], [0.45, 0.85]], [[0, 0.25], [0.30, 0.58], [0.63, 0.92]] ];
    stages_to_build = stage_defs[stages-1];
    for (stage = stages_to_build) {
        start_z = stage[0] * total_h; end_z = stage[1] * total_h;
        stage_h = end_z - start_z;
        center_z = start_z + stage_h/2 - total_h/2;
        revolutions = total_revolutions * (stage_h / total_h);
        translate([0,0,center_z]) 
            MultiHelixRamp(stage_h, 360 * revolutions, dia, helices);
    }
}

// NEW: This module mimics StagedCorkscrew to create the exit channels.
module StagedExitChannelCutter(total_h, dia, helices, stages) {
    stage_defs = [ [[0, 0.85]], [[0, 0.35], [0.45, 0.85]], [[0, 0.25], [0.30, 0.58], [0.63, 0.92]] ];
    stages_to_build = stage_defs[stages-1];
    for (stage = stages_to_build) {
        start_z = stage[0] * total_h; end_z = stage[1] * total_h;
        stage_h = end_z - start_z;
        center_z = start_z + stage_h/2 - total_h/2;
        revolutions = total_revolutions * (stage_h / total_h);
        translate([0,0,center_z]) 
            HelicalChannelCutter(stage_h, 360 * revolutions, dia, helices);
    }
}


// Creates the multi-helix ramps with slits.
module MultiHelixRamp(h, twist, dia, helices) {
    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices)]) {
            difference() {
                linear_extrude(height = h, twist = twist, center=true, slices = h > 0 ? h*2:1) 
                    polygon(points=[[0,0], [dia/2, 0], [dia/2*cos(ramp_width_degrees), dia/2*sin(ramp_width_degrees)]]);
                if (ADD_SLITS) 
                    linear_extrude(height = h, twist = twist, center=true, slices = h > 0 ? h*2:1) 
                        translate([dia/2 - slit_depth_mm/2, 0]) square([slit_depth_mm + 0.1, slit_width_mm + 0.1], center=true);
            }
        }
    }
}

// NEW: This module creates the helical cutting tool for a single channel.
module HelicalChannelCutter(h, twist, dia, helices) {
     for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices)]) {
            linear_extrude(height = h, twist = twist, center=true, slices = h > 0 ? h*2:1) {
                // This cutter starts at the ramp and extends outwards
                translate([dia/2 + dia, 0]) {
                    square([dia*2, slit_width_mm], center=true);
                }
            }
        }
    }
}

// ... (Helper modules like OringGroove_OD_Cutter are unchanged) ...
module OringGroove_OD_Cutter(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    difference() {
        cylinder(d = object_dia + 0.2, h = groove_width, center = true);
        cylinder(d = object_dia - 2 * groove_depth, h = groove_width + 0.2, center = true);
    }
}