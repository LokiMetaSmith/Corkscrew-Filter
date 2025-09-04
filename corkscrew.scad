// =============================================================================
// --- Parametric Corkscrew Filter - Main File ---
// =============================================================================
// This is the main entry point for the OpenSCAD model.
// It includes the configuration and all module libraries, then renders the
// selected part based on the `part_to_generate` variable.

// --- 1. Include Configuration & Modules ---
include <config.scad>
include <modules/primitives.scad>
include <modules/core.scad>
include <modules/cutters.scad>
include <modules/helpers.scad>
include <modules/inlets.scad>
include <modules/assemblies.scad>

// =============================================================================
// --- 2. Main Logic ---
// =============================================================================

// This block acts as the main program, calling the correct top-level assembly module
// based on the `part_to_generate` variable set in `config.scad`.

if (part_to_generate == "modular_filter_assembly") {
    tube_id = tube_od_mm - (2 * tube_wall_mm);
    if (GENERATE_CFD_VOLUME) {
        difference() {
            cylinder(d = tube_id, h = insert_length_mm, center = true);
            ModularFilterAssembly(tube_id, insert_length_mm);
        }
    } else {
        ModularFilterAssembly(tube_id, insert_length_mm);
    }
} else if (part_to_generate == "hex_array_filter") {
    HexFilterArray(hex_array_layers);
} else if (part_to_generate == "single_cell_filter") {
    SingleCellFilter();
} else if (part_to_generate == "hose_adapter_cap") {
    HoseAdapterEndCap(tube_od_mm, adapter_hose_id_mm, oring_cross_section_mm);
} else if (part_to_generate == "flat_end_screw") {
    total_twist = 360 * number_of_complete_revolutions;
    FlatEndScrew(insert_length_mm, total_twist, num_bins);
} else {
    echo("Error: `part_to_generate` variable is not set to a valid option.");
    echo("Please check `config.scad` and choose from the `part_options` list.");
}
