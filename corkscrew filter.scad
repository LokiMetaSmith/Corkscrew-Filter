// This file is Copyright Robert L. Read 2025.
// Although Public Invention does everything open source, this file is an
// exception.

// MODIFIED by Gemini.
// VERSION 13: Corrected the OringGroove_OD_Cutter module to properly create an external groove.

// --- Model Precision ---
high_res_fn = 150;
low_res_fn = 30;
$fn = $preview ? low_res_fn : high_res_fn;

// --- Main Parameters ---
num_bins = 3; 
number_of_complete_revolutions = 6;
screw_OD_mm = 1.8;
screw_ID_mm = 1;

// --- NEW PARAMETERS for Tube Filter ---
tube_od_mm = 15;
tube_wall_mm = 1;
insert_length_mm = 90;
oring_cross_section_mm = 1.5;
spacer_height_mm = 5; 

// --- CONTROL_VARIABLES ---
USE_MODULAR_FILTER    = 1;
USE_HOSE_ADAPTER_CAP  = 0;

// Visual Options
USE_TRANSLUCENCY      = false;
SHOW_O_RINGS          = false; 

// ===============================================================
// === Main Logic ================================================
// ===============================================================

if (USE_MODULAR_FILTER) {
    ModularFilterAssembly(tube_od_mm - (2 * tube_wall_mm), insert_length_mm, num_bins, spacer_height_mm, oring_cross_section_mm);
} else if (USE_HOSE_ADAPTER_CAP) {
    HoseAdapterEndCap(tube_od_mm, 9.525, oring_cross_section_mm);
}

// ===============================================================
// === Module Definitions ========================================
// ===============================================================

module ModularFilterAssembly(tube_id, total_length, bin_count, spacer_h, oring_cs) {
    total_spacer_length = (bin_count + 1) * spacer_h;
    total_screw_length = total_length - total_spacer_length;
    bin_length = total_screw_length / bin_count;

    translate([0, 0, -total_length/2]) {
        CaptureSpacer(tube_id, spacer_h, oring_cs, is_base = true);
        
        for (i = [0 : bin_count - 1]) {
            z_pos_screw = spacer_h + i * (bin_length + spacer_h);
            z_pos_spacer = z_pos_screw + bin_length;

            translate([0, 0, z_pos_screw + bin_length/2])
                FlatEndScrew(bin_length, number_of_complete_revolutions / bin_count);
            
            translate([0, 0, z_pos_spacer])
                CaptureSpacer(tube_id, spacer_h, oring_cs);
        }
    }
}

module CaptureSpacer(tube_id, height, oring_cs, is_base=false) {
    module BaseSpacer() {
        spacer_od = tube_id - 0.2;
        screw_tunnel_id = screw_ID_mm * 2;
        screw_flight_od = 4 * screw_OD_mm;
        socket_depth = height / 2;

        difference() {
            cylinder(d = spacer_od, h = height);
            
            translate([0,0,height/2])
                OringGroove_OD_Cutter(spacer_od, oring_cs);
            
            cylinder(d = screw_tunnel_id + 0.2, h = height + 0.2, center=true);
            
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
    }
}

// COMPLETELY REWRITTEN to correctly generate a ring-shaped cutting tool.
module OringGroove_OD_Cutter(object_dia, oring_cs) {
    groove_depth = oring_cs * 0.8;
    groove_width = oring_cs * 1.1;
    
    // This creates a hollow tube (a ring) that will be subtracted.
    // Its height determines the width of the groove.
    difference() {
        // Outer wall of the cutter
        cylinder(d = object_dia + 0.2, h = groove_width, center = true);
        // Inner wall of the cutter (this defines the bottom of the groove)
        cylinder(d = object_dia - 2 * groove_depth, h = groove_width + 0.2, center = true);
    }
}

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

// ... (Rest of modules are unchanged) ...