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
include <modules/custom_couplings.scad> // Added for legacy support
include <modules/filter_holder.scad>

// =============================================================================
// --- 2. Main Logic ---
// =============================================================================

// This block acts as the main program, calling the correct top-level assembly module
// based on the `part_to_generate` variable set in `config.scad`.

module GenerateSelectedPart() {
    target_part = is_undef(part_to_generate) ? default_part_to_generate : part_to_generate;

    if (target_part == "modular_filter_assembly") {
        tube_id = tube_od_mm - (2 * tube_wall_mm);
        if (GENERATE_CFD_VOLUME) {
            difference() {
                cylinder(d = tube_id, h = insert_length_mm, center = true);
                ModularFilterAssembly(tube_id, insert_length_mm);
            }
        } else {
            ModularFilterAssembly(tube_id, insert_length_mm);
        }
    } else if (target_part == "hex_array_filter") {
        HexFilterArray(hex_array_layers);
    } else if (target_part == "single_cell_filter") {
        SingleCellFilter();
    } else if (target_part == "hose_adapter_cap") {
        HoseAdapterEndCap(tube_od_mm, adapter_hose_id_mm, oring_cross_section_mm, tube_wall_mm, ADAPTER_AXIAL_SEAL);
    } else if (target_part == "flat_end_screw") {
        total_twist = 360 * number_of_complete_revolutions;
        FlatEndScrew(insert_length_mm, total_twist, num_bins);
    } else if (target_part == "custom_coupling") {
        CustomCoupling();
    } else if (target_part == "filter_holder") {
        FilterHolder(
            tube_id = tube_od_mm - (2 * tube_wall_mm),
            cartridge_od = filter_holder_cartridge_od,
            barb_od = barb_inlet_id_mm + 1.5, // reuse barb inlet param or add specific one
            barb_id = barb_inlet_id_mm,
            thread_inner = filter_holder_thread_inner,
            thread_outer = filter_holder_thread_outer,
            oring_cs = oring_cross_section_mm,
            tube_wall = tube_wall_mm
        );
    } else {
        echo("Error: `part_to_generate` variable is not set to a valid option.");
        echo("Please check `config.scad` and choose from the `part_options` list.");
    }
}

if (CUT_FOR_VISIBILITY) {
    difference() {
        GenerateSelectedPart();
        // Cut away the front half (positive Y)
        translate([-500, 0, -500]) cube([1000, 1000, 1000]);
    }
} else {
    GenerateSelectedPart();
}
