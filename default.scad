// Thirsty Corkscrew - Default Configuration File
//
// To create a new configuration, copy this file, rename it,
// and change the `config_file` variable in `corkscrew filter.scad`
// to point to your new file.

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
support_density = 4;
flange_od = 20;
flange_height = 5;

// --- Tolerances & Fit ---
tolerance_tube_fit = 0.2;
tolerance_socket_fit = 0.4;
tolerance_channel = 0.1;
