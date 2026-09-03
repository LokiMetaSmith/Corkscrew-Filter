// =============================================================================
// --- Cartridge Coupling Configuration ---
// =============================================================================

// 1. Load Defaults
include <../config.scad>

// 2. Override Parameters
part_to_generate = "custom_coupling";
custom_coupling_type = "cartridge";

// --- Barb Parameters ---
barb_input_diameter = 5;
barb_output_diameter = 6.5;
barb_wall_thickness = 1;
barb_length = 2;
barb_count = 4;
barb_swell = 1;

// --- Coupling Geometry ---
coupling_lip_height = 2.4;
coupling_lip_width = 16.9;
coupling_outer_coupling_od = 14.91;
coupling_outer_coupling_height = 10;
coupling_inset_height = 23.5;
coupling_inset_width = 30.3126; // approx 30.312598673823808020208399115883
coupling_inner_inlet = 29;
coupling_inner_height = 2.37;
coupling_inner_outlet = 5.2;

// 3. Generate Model
include <../corkscrew.scad>
