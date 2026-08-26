// trace_optimizer.scad - Parametric Microstrip Optimizer with Multi-Layer Support

// --- Parameters ---
trace_offset = 0.0;
substrate_thickness = 1.6;
substrate_width = 20.0;
substrate_length = 100.0;
copper_thickness = 0.035;
num_layers = 2; // [2, 4]

// Output control
part = "all"; // ["all", "copper", "substrate", "port1", "port2", "ground", "inner1", "inner2"]

module trace_geometry() {
    offset(delta = trace_offset)
    import("trace.svg");
}

module layer(z_pos, h) {
    translate([0, 0, z_pos])
    cube([substrate_length, substrate_width, h]);
}

module substrate() {
    color("green", 0.5)
    layer(0, substrate_thickness);
}

module ground() {
    color("silver")
    layer(-copper_thickness, copper_thickness);
}

module copper() {
    color("gold")
    translate([0, 0, substrate_thickness])
    linear_extrude(height = copper_thickness)
    trace_geometry();
}

module inner_plane(z_pos) {
    color("silver", 0.8)
    layer(z_pos, copper_thickness);
}

module port(x_pos) {
    translate([x_pos, substrate_width/2 - 2, 0])
    cube([0.5, 4, substrate_thickness]);
}

if (part == "all" || part == "copper") copper();
if (part == "all" || part == "substrate") substrate();
if (part == "all" || part == "ground") ground();

if (num_layers == 4) {
    if (part == "all" || part == "inner1") inner_plane(substrate_thickness * 0.33);
    if (part == "all" || part == "inner2") inner_plane(substrate_thickness * 0.66);
}

if (part == "port1") port(0);
if (part == "port2") port(substrate_length - 0.5);
