// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED by Gemini.
// VERSION 22: Major rewrite implementing a parametric multi-helix, hexagonal array, and ramped slits.

// --- Model Precision ---
high_res_fn = 150;
low_res_fn = 30;
$fn = $preview ? low_res_fn : high_res_fn;

// --- Main Filter Parameters ---
cell_diameter = 10;                     // OD of the corkscrew in a single cell.
cell_length = 100;                      // The total Z-height of a filter cell.
num_helices = 3;                        // Number of interleaved helices (1, 2, or 3).
ramp_width_degrees = 20;                // Angular width of a single helix ramp.
total_revolutions = 8;                  // Total turns over the cell_length.

// --- Staging Parameters ---
// Controls the number of stages and gaps, based on your notes.
num_stages = 3; // [1, 2, 3]

// --- Ramped Slit Parameters ---
ADD_SLITS = true;                       // Master toggle for adding slits.
slit_ramp_length_mm = 5;                // The length of the ramp leading to the slit opening.
slit_open_length_mm = 10;               // The length of the fully open part of the slit.
slit_width_mm = 2;                      // The width of the slit opening.

// --- Array Parameters ---
hex_array_layers = 1; // 0=1 cell, 1=7 cells, 2=19 cells, etc.

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

// --- Top-Level Assembly Modules ---

// Creates a single filter cell inside a cylinder.
module SingleCellFilter() {
    // Outer tube for the single cell
    tube_od = cell_diameter + 10;
    tube_wall = 1.5;
    difference() {
        cylinder(d = tube_od, h = cell_length, center = true);
        cylinder(d = tube_od - 2*tube_wall, h = cell_length + 2, center = true);
    }

    // The filter core
    StagedCorkscrew(cell_length, cell_diameter, num_helices, num_stages);
}

// Creates a hexagonal array of filter cells.
module HexFilterArray(layers) {
    spacing = cell_diameter + 2; // Distance between cell centers
    hex_radius = layers * spacing + cell_diameter;

    // Create the main hexagonal block and cut empty cells
    difference() {
        cylinder(h = cell_length, d = hex_radius, center=true, $fn=6);
        HexArrayLayout(layers, spacing) {
            cylinder(d = cell_diameter + 0.4, h = cell_length + 2, center=true); // Cutter
        }
    }

    // Place the filter core into each empty cell
    HexArrayLayout(layers, spacing) {
        StagedCorkscrew(cell_length, cell_diameter, num_helices, num_stages);
    }
}


// --- Core Geometry Modules ---

// Arranges children in a hexagonal pattern.
module HexArrayLayout(layers, spacing) {
    // Center cell
    children();
    // Rings of cells
    for (l = [1 : layers]) {
        for (a = [0 : 5]) {
            for (s = [0 : l - 1]) {
                angle1 = a * 60;
                angle2 = (a+1) * 60;
                pos = l * spacing * [(1-s/l)*cos(angle1) + (s/l)*cos(angle2),
                                     (1-s/l)*sin(angle1) + (s/l)*sin(angle2)];
                translate(pos) children();
            }
        }
    }
}

// Creates the staged corkscrew based on the diagrams.
module StagedCorkscrew(total_h, dia, helices, stages) {
    stage_defs = [
        // num_stages = 1
        [[0, 0.85]],
        // num_stages = 2
        [[0, 0.35], [0.45, 0.85]],
        // num_stages = 3
        [[0, 0.25], [0.30, 0.58], [0.63, 0.92]]
    ];

    stages_to_build = stage_defs[stages-1];

    for (stage = stages_to_build) {
        start_z = stage[0] * total_h;
        end_z = stage[1] * total_h;
        stage_h = end_z - start_z;
        center_z = start_z + stage_h/2 - total_h/2;
        revolutions = total_revolutions * (stage_h / total_h);

        translate([0,0,center_z]) {
            difference() {
                MultiHelixRamp(stage_h, 360 * revolutions, dia, helices);
                if (ADD_SLITS) {
                    RampedSlitKnife(stage_h, 360*revolutions, dia, helices);
                }
            }
        }
    }
}

// Creates the "Parking Garage" style multi-helix ramp.
module MultiHelixRamp(h, twist, dia, helices) {
    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices)]) {
            linear_extrude(height = h, twist = twist, center=true, slices = h*2) {
                // 2D cross-section of a single flat ramp
                polygon(points=[
                    [0,0],
                    [dia/2, 0],
                    [dia/2 * cos(ramp_width_degrees), dia/2 * sin(ramp_width_degrees)]
                ]);
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
    open_slit_cutter = cube([slit_width_mm, slit_width_mm, slit_open_length_mm]);

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
