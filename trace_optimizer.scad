// trace_optimizer.scad - Parametric Microstrip Optimizer

// --- Parameters ---
trace_offset = 0.0; // [mm] Offset for trace width optimization
substrate_thickness = 1.6; // [mm] Standard FR4 thickness
substrate_width = 20.0;
substrate_length = 100.0;
copper_thickness = 0.035; // [mm] 1oz copper

// Output control
part = "all"; // ["all", "copper", "substrate", "port1", "port2"]

module trace_geometry() {
    offset(delta = trace_offset)
    import("trace.svg");
}

module substrate() {
    color("green", 0.5)
    cube([substrate_length, substrate_width, substrate_thickness]);
}

module copper() {
    color("gold")
    translate([0, 0, substrate_thickness])
    linear_extrude(height = copper_thickness)
    trace_geometry();
}

module port(x_pos) {
    // Ports are defined as small cubes at the ends of the trace.
    // The OpenEMSDriver will use these to find the excitation coordinates.
    translate([x_pos, substrate_width/2 - 2, substrate_thickness])
    cube([1, 4, copper_thickness * 2]);
}

if (part == "all" || part == "copper") {
    copper();
}

if (part == "all" || part == "substrate") {
    substrate();
}

if (part == "port1") {
    port(0);
}

if (part == "port2") {
    port(substrate_length - 1);
}
