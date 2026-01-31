// Threaded Modular Filter & Pipe Configuration
// Configures the modular filter with threaded inlets and standard pipe dimensions.
include <../config.scad>

// Enable Modular Filter
part_to_generate = "modular_filter_assembly";

// Enable Threaded Inlets
inlet_type = "threaded";

// Pipe/Tube Configuration (Matches BOM Standard: 32mm OD / 30mm ID)
tube_od_mm = 32;
tube_wall_mm = 1;

include <../corkscrew.scad>
