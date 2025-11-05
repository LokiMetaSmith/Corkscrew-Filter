// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED by Gemini.
// VERSION 34: Added debris exit channels through the main hexagonal frame.

// --- Model Precision ---
high_res_fn = 150;
low_res_fn = 30;
$fn = $preview ? low_res_fn : high_res_fn;


cell_diameter = 10;                     // OD of the corkscrew in a single cell.
cell_length = 15;                      // The total Z-height of a filter cell.
num_helices = 6;                        // Number of interleaved helices (1, 2, or 3).
ramp_width_degrees = 10;                // Angular width of a single helix ramp.
total_revolutions = 0.5;                  // Total turns over the cell_length.

// --- Staging Parameters ---
// Controls the number of stages and gaps, based on your notes.
num_stages = 1; // [1, 2, 3]

// --- Slit & Channel Parameters ---
ADD_SLITS = true;
slit_width_mm = 1.5;
slit_depth_mm = 2;

// --- Array & Casing Parameters ---
hex_array_layers = 1; // 0=1 cell, 1=7 cells, 2=19 cells, etc.
outer_casing_wall_mm = 3;
ADD_OUTER_O_RINGS = true;


// --- CONTROL_VARIABLES ---
USE_HEX_ARRAY_FILTER    = 1;
USE_SINGLE_CELL_FILTER  = 1;

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
       //     HexArrayLayout(layers, spacing) {
       //         StagedCorkscrew(cell_length, cell_diameter, num_helices, num_stages);
      //      }
       }

    // Create the main hexagonal block and cut empty cells
    difference() {
        cylinder(h = cell_length, d = hex_radius, center=true, $fn=6);
        //HexArrayLayout(layers,spacing);
        //HexArrayLayout(layers, spacing) {
            cylinder(d = cell_diameter + 0.4, h = cell_length + 2, center=true); // Cutter
        }
    }
}
// Creates a filled hexagonal grid
// layers: The "radius" of the grid in number of hexes from the center
// size: The radius of a single hexagon (distance from center to a point)
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



// Lays out children in a hexagonal pattern.
// --- EXAMPLE USAGE ---
// Use $fn=6 to make the cylinders into hexagons
//HexGrid(layers = 4, size = 10) {
//    cylinder(r = 10, h = 2, $fn = 6);
//}

// --- Core Geometry Modules ---

// Arranges children on the perimeters of concentric hexagons.
module HexArrayLayout(layers, spacing) {
    children();
 //   if (layers > 0) for (l = [1 : layers]) for (a = [0 : 5]) for (s = [0 : l - 1]) {
//        angle1 = a * 60; angle2 = (a+1) * 60;
//        pos = (l * spacing) * [ (1-s/l)*cos(angle1) + (s/l)*cos(angle2), (1-s/l)*sin(angle1) + (s/l)*sin(angle2) ];
//        translate(pos) children();
//    }
//}

// Generates the staged helical ramps.

    
    // Rings of cells
    for (l = [1 : layers]) {
        for (a = [0: 5]) {
            for (s = [0: l-1]) {
                
                angle1 = a * 60;
                angle2 = (a+1) * 60;
                
                // Calculate the X and Y components first
                x_comp = (1-s/l)*cos(angle1) + (s/l)*cos(angle2);
                y_comp = (1-s/l)*sin(angle1) + (s/l)*sin(angle2);
                
                // Define the position vector [x, y]
                // and multiply it by the scalar (l * spacing)
                pos = (l * spacing) * [x_comp, y_comp];
                                     
                translate(pos) children();
            }
        }
    }
}

// Example of how to use it:
//HexArrayLayout(layers = 4, spacing = 20) {
//    cylinder(r=5, h=2);
//}

// Creates the staged corkscrew based on the diagrams.

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
// Creates a cutting tool for a ramped slit.
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
    cube([slit_width_mm, slit_width_mm, slit_open_length_mm]);

    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices) + ramp_width_degrees/2]) {
            // Apply the same helical transformation as the ramp itself
            linear_extrude(height=h, twist=twist, center=true, slices=h*2) {
                 // Place the ramp and slit cutters in the 2D space
                 // This is a simplified placement and may require further tuning.
                 translate([dia/2 - slit_width_mm, 0, -h/2 + slit_ramp_length_mm/2])
                    polyhedron(points=cutter_shape_points, faces=cutter_shape_faces);

                 translate([dia/2 - slit_width_mm, 0, -h/2 + slit_ramp_length_mm + slit_open_length_mm/2])
                    cube([slit_width_mm, slit_width_mm, slit_open_length_mm], center=true);
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