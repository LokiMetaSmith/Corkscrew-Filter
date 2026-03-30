// =============================================================================
// --- Parametric Cyclone Filter ---
// =============================================================================
// OpenSCAD model for a traditional tangential cyclone separator.

// --- Parameters ---
// (Defaults; can be overridden via -D from command line)
cyclone_diameter = 100.0;
cylinder_height = 100.0;
cone_height = 150.0;
inlet_width = 25.0;
inlet_height = 50.0;
vortex_finder_diameter = 50.0;
vortex_finder_length = 75.0;
dust_outlet_diameter = 25.0;
wall_thickness = 2.0;

// High resolution for rendering
$fn = is_undef(high_res_fn) ? 60 : high_res_fn;

// Simulation flags
GENERATE_CFD_VOLUME = is_undef(GENERATE_CFD_VOLUME) ? false : GENERATE_CFD_VOLUME;
part_to_generate = is_undef(part_to_generate) ? "solid" : part_to_generate;
CUT_FOR_VISIBILITY = is_undef(CUT_FOR_VISIBILITY) ? false : CUT_FOR_VISIBILITY;

// --- Calculated Geometry ---
cyclone_radius = cyclone_diameter / 2;
vortex_finder_radius = vortex_finder_diameter / 2;
dust_outlet_radius = dust_outlet_diameter / 2;

// --- Anchor for snappyHexMesh ---
if (GENERATE_CFD_VOLUME) {
    // A point guaranteed to be inside the fluid volume (e.g. inside the main cylinder)
    echo(str("MESH_ANCHOR=[0, 0, ", cylinder_height / 2, "]"));
}

module TangentialInlet(solid = true) {
    // The inlet is tangential to the cylinder wall at the top
    translate([cyclone_radius - inlet_width/2, 0, cylinder_height - inlet_height/2]) {
        if (solid) {
             cube([inlet_width, cyclone_diameter + 10, inlet_height], center=true);
        } else {
             cube([inlet_width - 2*wall_thickness, cyclone_diameter + 10, inlet_height - 2*wall_thickness], center=true);
        }
    }
}

module CycloneFluidVolume() {
    union() {
        // Main cylinder
        cylinder(r=cyclone_radius, h=cylinder_height, center=false);

        // Cone
        translate([0, 0, -cone_height])
        cylinder(r1=dust_outlet_radius, r2=cyclone_radius, h=cone_height, center=false);

        // Dust outlet pipe
        translate([0, 0, -cone_height - 25])
        cylinder(r=dust_outlet_radius, h=25, center=false);

        // Tangential inlet fluid
        // Extend slightly to make sure it intersects
        translate([cyclone_radius - inlet_width/2, 0, cylinder_height - inlet_height/2]) {
             // We extend in Y to act as the inlet pipe
             translate([0, cyclone_radius, 0])
             cube([inlet_width, cyclone_diameter, inlet_height], center=true);
        }
    }
}

module VortexFinder(solid = true) {
    // The pipe going down the center
    translate([0, 0, cylinder_height - vortex_finder_length]) {
        if (solid) {
             cylinder(r=vortex_finder_radius, h=vortex_finder_length + 25, center=false);
        } else {
             cylinder(r=vortex_finder_radius - wall_thickness, h=vortex_finder_length + 26, center=false); // Inner hole
        }
    }
}

module ActualFluidVolume() {
    union() {
        difference() {
            CycloneFluidVolume();
            // Subtract the vortex finder pipe that protrudes *into* the fluid
            VortexFinder(solid=true);
        }
        // Add the fluid inside the vortex finder which goes out the top
        VortexFinder(solid=false);
    }
}

module CycloneSolid() {
    difference() {
        // Outer shell
        union() {
            cylinder(r=cyclone_radius + wall_thickness, h=cylinder_height, center=false);

            translate([0, 0, -cone_height])
            cylinder(r1=dust_outlet_radius + wall_thickness, r2=cyclone_radius + wall_thickness, h=cone_height, center=false);

            translate([0, 0, -cone_height - 25])
            cylinder(r=dust_outlet_radius + wall_thickness, h=25, center=false);

            // Outer inlet pipe
            translate([cyclone_radius - inlet_width/2, cyclone_radius, cylinder_height - inlet_height/2])
            cube([inlet_width + 2*wall_thickness, cyclone_diameter, inlet_height + 2*wall_thickness], center=true);

            // Outer vortex finder
            VortexFinder(solid=true);

            // Top plate
            translate([0, 0, cylinder_height])
            cylinder(r=cyclone_radius + wall_thickness, h=wall_thickness, center=false);
        }

        // Subtract actual fluid volume
        ActualFluidVolume();
    }
}

module GeneratePart() {
    if (part_to_generate == "solid") {
        CycloneSolid();
    } else if (part_to_generate == "fluid_volume" || part_to_generate == "corkscrew_fluid") { // alias for compatibility
        ActualFluidVolume();
    } else if (part_to_generate == "inlet") {
        // A patch at the end of the inlet pipe
        translate([cyclone_radius - inlet_width/2, cyclone_diameter, cylinder_height - inlet_height/2])
        cube([inlet_width, 1, inlet_height], center=true);
    } else if (part_to_generate == "clean_outlet" || part_to_generate == "outlet") {
        // A patch at the top of the vortex finder
        translate([0, 0, cylinder_height + 25])
        cylinder(r=vortex_finder_radius - wall_thickness, h=1, center=true);
    } else if (part_to_generate == "dust_outlet") {
        // A patch at the bottom of the cone
        translate([0, 0, -cone_height - 25])
        cylinder(r=dust_outlet_radius, h=1, center=true);
    } else if (part_to_generate == "cfd_wall") {
        // The CFD wall is technically the fluid volume hull minus the inlet/outlets.
        // For snappyHexMesh, we often just provide the solid boundaries, but `corkscrewFilter`
        // workflow generates an explicit `wall.stl`.
        difference() {
             ActualFluidVolume();
             // Subtracting a bit of the caps so they aren't part of the wall
             // This is an approximation for STL generation; OpenFOAM topoSet handles exact boundaries usually
        }
    }
}

if (CUT_FOR_VISIBILITY) {
    difference() {
        GeneratePart();
        // Cut front half
        translate([-500, 0, -500]) cube([1000, 1000, 1000]);
    }
} else {
    GeneratePart();
}
