// =============================================================================
// --- Parametric Corkscrew Filter Configuration ---
// =============================================================================
// This file contains all the user-configurable parameters for the filter.
// Modify the values here to change the generated model.

// =============================================================================
// --- A. High-Level Control Panel ---
// =============================================================================

// --- 1. Model Selection ---
// This variable controls which component is rendered.
part_options = ["modular_filter_assembly", "hex_array_filter", "single_cell_filter", "hose_adapter_cap", "flat_end_screw", "filter_holder", "custom_coupling"];
// We use is_undef to prevent overwriting if this file is included after variables are set.
part_to_generate = is_undef(part_to_generate) ? part_options[5] : part_to_generate;

// --- 2. Feature Flags ---
// These flags toggle optional features on the selected model.

// --- Modular Filter & Flat End Screw Features ---
inlet_options = ["none", "threaded", "pressfit", "barb"];
inlet_type = inlet_options[0];              // Inlet style for the end spacers of the modular filter. ["none", "threaded", "barb"]
GENERATE_CFD_VOLUME = false;     // If true, generates the negative space (fluid volume) for CFD analysis instead of the solid part.
ADD_HELICAL_SUPPORT = true;      // If true, adds a lattice-like support structure between the spacers for rigidity.

// --- Hex/Single Cell Features ---
slit_options = ["none", "simple", "ramped"];
slit_type = slit_options[2];            // Defines the type of slit cut into the helical ramps. ["none", "simple", "ramped"]
ADD_OUTER_O_RINGS = true;        // If true, adds O-Ring grooves to the outer hexagonal casing.
ADD_DEBRIS_EXIT_CHANNELS = false; // NEW: If true, cuts channels for debris to exit the hex array frame.

// --- Visual/Debug Options ---
SHOW_O_RINGS = true;             // If true, renders red O-rings in their grooves for visualization.
USE_TRANSLUCENCY = false;        // If true, makes certain parts semi-transparent to see internal geometry.
CUT_FOR_VISIBILITY = true;      // If true, cuts the model in half (removes Y>0) to allow inspection of internal geometry.

// =============================================================================
// --- B. Model Parameters ---
// =============================================================================

// --- General & Precision ---
high_res_fn = is_undef(high_res_fn) ? 200 : high_res_fn; // Fragment resolution for final renders ($fn). Higher values create smoother curves.
low_res_fn = is_undef(low_res_fn) ? 10 : low_res_fn;   // Fragment resolution for previews. Lower values provide faster previews.
$fn = $preview ? low_res_fn : high_res_fn; // OpenSCAD automatically uses the appropriate value.

// --- Tube & Main Assembly Parameters ---
tube_od_mm = 32;                 // The outer diameter of the tube the filter assembly will be inserted into.
tube_wall_mm = 1;                // The wall thickness of the tube. Used to calculate the inner diameter.
insert_length_mm = 350 / 2;      // The total length of the filter insert from end to end.
num_bins = 1;                    // The number of separate helical screw segments in the modular assembly.

// --- Helical Screw Parameters ---
number_of_complete_revolutions = 12; // How many full 360-degree turns the screw makes over its total length.
helix_path_radius_mm = 1.8;      // The radius of the helical path, measured from the central axis to the center of the screw's profile.
helix_profile_radius_mm = 1.8;   // The radius of the circular cross-section of the solid screw itself.
helix_void_profile_radius_mm = 1; // The radius of the circular cross-section of the channel (the void) inside the screw.
helix_profile_scale_ratio = 1.4; // Stretches the screw's circular profile along one axis to create an ellipse, increasing surface area.

// --- Spacer & O-Ring Parameters ---
spacer_height_mm = 5;            // The axial height of each spacer disk.
oring_cross_section_mm = 1.5;    // The diameter of the O-ring cord.

// --- Helical Support Parameters ---
support_rib_thickness_mm = 2.5;  // The diameter of the individual struts that make up the helical support.
support_revolutions = 4;         // The number of revolutions the support struts make. (Note: This is not currently used, twist is derived from the main helix).
support_density = 4;             // The number of support bundles distributed around the circumference.

// --- Hose Adapter Cap Parameters ---
adapter_hose_id_mm = 30;         // The inner diameter of the hose that will connect to the end cap adapter.
flange_od = 20;                  // The outer diameter of the flange on the hose adapter.
flange_height = 5;               // The height of the flange on the hose adapter.
ADAPTER_AXIAL_SEAL = true;      // If true, uses an axial (face) seal with a cup for the tube. If false, uses a radial seal.

// --- Inlet Parameters (for Modular Filter) ---
// Threaded Inlet
threaded_inlet_id_mm = 4;        // The outer diameter of the threaded portion of the inlet.
threaded_inlet_flange_od = threaded_inlet_id_mm + 4; // The diameter of the flange at the base of the threaded inlet.
threaded_inlet_height = 10;      // The height of the threaded inlet.
// Barb Inlet
barb_inlet_id_mm = 4;            // The inner diameter of the hose barb.
barb_inlet_count = 3;            // The number of individual barbs on the fitting.
barb_inlet_flange_od = barb_inlet_id_mm + 4; // The diameter of the flange at the base of the barb inlet.

// --- Filter Holder Parameters ---
filter_holder_cartridge_od = 10;
filter_holder_thread_inner = false;
filter_holder_thread_outer = true;

// --- Custom Coupling Parameters ---
// These are defaults, usually overridden by including a specific config file.
custom_coupling_type = is_undef(custom_coupling_type) ? "none" : custom_coupling_type;
barb_input_diameter = 5;
barb_output_diameter = 6.5;
barb_wall_thickness = 1;
barb_length = 2;
barb_count = 4;
barb_swell = 1;
coupling_lip_height = 2.4;
coupling_lip_width = 16.9;
coupling_outer_coupling_od = 14.91;
coupling_outer_coupling_height = 10;
coupling_inset_height = 23.5;
coupling_inset_width = 30.3;
coupling_inner_inlet = 29;
coupling_inner_height = 2.37;
coupling_inner_outlet = 5.2;


// --- Hex Array & Single Cell Filter Parameters ---
cell_diameter = 10;              // The outer diameter of the helical filter within a single cell.
cell_length = 100;               // The total Z-height (length) of a filter cell.
num_helices = 1;                 // The number of interleaved helical ramps (e.g., like a multi-start thread).
ramp_width_degrees = 20;         // The angular width of a single helical ramp.
total_revolutions = 8;           // The number of full turns a helix makes over the `cell_length`.
num_stages = 3;                  // The number of stacked, separated helical segments within a single cell. [1, 2, or 3]
hex_array_layers = 1;            // The number of hexagonal rings around the central cell (0=1 cell, 1=7 cells, 2=19 cells).
outer_casing_wall_mm = 3;        // The wall thickness of the hexagonal casing for the array.

// --- Slit Parameters ---
slit_ramp_length_mm = 5;         // The length of the ramped portion of a slit (for "ramped" `slit_type`).
slit_open_length_mm = 10;        // The length of the fully open portion of a slit.
slit_width_mm = 2;               // The width of the slit opening.
slit_depth_mm = 2;               // The depth of the slit cut into the ramp.
slit_axial_length_mm = 1.5;      // The height (Z-axis) of the slit cut for CorkscrewSlitKnife.
slit_chamfer_height = 0.5;       // The height of the chamfer on the leading edge of the slit knife.

// --- Tolerances & Fit ---
tolerance_tube_fit = 0.2;        // Clearance between the spacers and the inner wall of the main tube.
tolerance_socket_fit = 0.4;      // Clearance for sockets and recesses, like for the inlet flange.
tolerance_channel = 0.1;         // Extra clearance for the helical void to prevent binding during assembly.
