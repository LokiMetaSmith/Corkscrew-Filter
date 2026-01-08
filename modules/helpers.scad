// =============================================================================
// --- Helper & Utility Modules ---
// =============================================================================
// This file contains general-purpose utility modules that are used by the
// main assembly modules to create complex geometry.

/**
 * Module: StagedHelicalStructure
 * Description: Generates the helical filter core for the Hex Array and Single Cell filters.
 * It creates stacked helical stages with gaps between them and applies the selected slit cutter.
 * Arguments:
 * total_h: The total height of the cell.
 * dia:     The outer diameter of the helical structure.
 * helices: The number of interleaved helices.
 * stages:  The number of stages to build (1, 2, or 3).
 */
module StagedHelicalStructure(total_h, dia, helices, stages) {
    stage_defs = [ [[0, 0.85]], [[0, 0.35], [0.45, 0.85]], [[0, 0.25], [0.30, 0.58], [0.63, 0.92]] ];
    stages_to_build = stage_defs[stages - 1];

    for (stage = stages_to_build) {
        start_z_frac = stage[0];
        end_z_frac = stage[1];
        stage_h = (end_z_frac - start_z_frac) * total_h;
        center_z = (start_z_frac + end_z_frac) / 2 * total_h - total_h / 2;
        revolutions = total_revolutions * (stage_h / total_h);
        twist = 360 * revolutions;

        translate([0, 0, center_z]) {
            difference() {
                MultiHelixRamp(stage_h, twist, dia, helices);
                if (slit_type == "simple") {
                    SimpleSlitCutter(stage_h, twist, dia, helices);
                } else if (slit_type == "ramped") {
                    RampedSlitKnife(stage_h, twist, dia, helices);
                }
            }
        }
    }
}

/**
 * Module: MultiHelixRamp
 * Description: Creates the solid, interleaved helical ramps (like a parking garage ramp).
 * Arguments:
 * h:       The height of the ramp.
 * twist:   The total twist angle in degrees.
 * dia:     The outer diameter of the ramp.
 * helices: The number of interleaved ramps to create.
 */
module MultiHelixRamp(h, twist, dia, helices) {
    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices)]) {
            linear_extrude(height = h, twist = twist, center = true, slices = h > 0 ? h * 2 : 1) {
                polygon(points = [
                    [0, 0],
                    [dia / 2, 0],
                    [dia / 2 * cos(ramp_width_degrees), dia / 2 * sin(ramp_width_degrees)]
                ]);
            }
        }
    }
}

/**
 * Module: HelicalOuterSupport
 * Description: Creates a lattice-like helical support structure that connects spacers in
 * the modular assembly, adding rigidity.
 * Arguments:
 * target_dia:      The outer diameter that the support structure should conform to.
 * target_height:   The height of the support structure (i.e., the length of a screw segment).
 * rib_thickness:   The diameter of the individual support struts.
 * twist_rate:      The twist rate in degrees per mm.
 */
module HelicalOuterSupport(target_dia, target_height, rib_thickness, twist_rate) {
    twist_angle = twist_rate * target_height;
    radius = target_dia / 2 - rib_thickness;

    for( i = [0:1:support_density-1]){
        rotate([0,0,i*(360/support_density)]) {
            union() {
                linear_extrude(height = target_height, center = false, convexity = 10, twist = -twist_angle)
                    translate([radius,0,0])
                        circle(d=rib_thickness);
                linear_extrude(height = target_height, center = false, convexity = 10, twist = twist_angle)
                    rotate([0,0,120])
                        translate([radius,0,0])
                            circle(d=rib_thickness);
                linear_extrude(height = target_height, center = false, convexity = 10, twist = 0)
                    rotate([0,0,240])
                        translate([radius,0,0])
                            circle(d=rib_thickness);
            }
        }
    }
}

/**
 * Module: HexArrayLayout
 * Description: A powerful utility module that arranges any child elements into a hexagonal grid.
 * Arguments:
 * layers: The number of hexagonal rings to create around the central element.
 * spacing: The distance between the centers of adjacent elements.
 */
module HexArrayLayout(layers, spacing) {
    children(); // Center element
    if (layers > 0) {
        for (l = [1 : layers]) {
            for (a = [0 : 5]) {
                for (s = [0 : l - 1]) {
                    angle1 = a * 60;
                    angle2 = (a + 1) * 60;
                    pos = (l * spacing) * [(1 - s / l) * cos(angle1) + (s / l) * cos(angle2), (1 - s / l) * sin(angle1) + (s / l) * sin(angle2)];
                    translate(pos) children();
                }
            }
        }
    }
}
