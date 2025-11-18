// Thirsty Corkscrew - Default Configuration File
//
// To create a new configuration, copy this file, rename it,
// and change the `config_file` variable in `corkscrew filter.scad`
// to point to your new file.

// --- Main Parameters ---
num_bins = 1;
// number_of_complete_revolutions = 3;
// screw_OD_mm = 1.8;
// screw_ID_mm = 1;
// scale_ratio = 1.4;

// --- NEW PARAMETERS for Tube Filter ---
tube_od_mm = 32;
tube_wall_mm = 1;


// Case 1
insert_length_mm = (350/2)/6;
screw_OD_mm = 2.0;
screw_ID_mm = 1.0;

// Case 2
//insert_length_mm = 100;
//screw_OD_mm = 5;
//screw_ID_mm = 3.5;

num_hex = 1;
hex_spacing = 5;


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


// Rob's variables. These have not been coordinated with Lawrence's above yet.



// use <BarbGenerator-v3.scad>;


// Params (mm), degrees 
number_of_complete_revolutions = 1*num_bins;
filter_height_mm = num_bins*40/3;
// WARNING! Trying to reduce this to one bin seemed to make the slit go away

filter_twist_degrees = 360*number_of_complete_revolutions;

// screw_OD_mm = 4.5;
// screw_ID_mm = 3.5;
cell_wall_mm = 1.4;
barb_input_diameter = 2;
barb_output_diameter = 5;
barb_wall_thickness = 1;

// The slit_axial_open_length_mm is the "length",
// in an axial sense of the 
slit_axial_open_length_mm = 1;
slit_axial_length_mm = cell_wall_mm + slit_axial_open_length_mm;

// The "slit_knife" is "radial" in the since that it cuts
// a pie-slice shaped slit into the wall of the helix.
// The wider the angle, the greater the slit. 180 would
// be half the slit. I suggest this be limited to 45 degrees.
slit_knife_angle = 45;
hex_cell_diam_mm = 10;
FN_RES = 60;
bin_height_z_mm = 10;
num_screws = 3;

screw_center_separation_mm = 3;
bin_breadth_x_mm = (num_screws -1) * screw_center_separation_mm + screw_center_separation_mm*2;

pitch_mm = filter_height_mm / number_of_complete_revolutions;

scale_ratio = 1.4; // This is used to acheive a more circular air path

bin_wall_thickness_mm = 1;
