// =============================================================================
// --- Cutter Modules ---
// =============================================================================
// This file contains all the modules that are used as "knives" or cutting
// tools to subtract geometry from other parts.

/**
 * Module: SimpleSlitCutter
 * Description: Creates a simple rectangular helical cutting tool for making slits.
 * Arguments: (Same as MultiHelixRamp)
 */
module SimpleSlitCutter(h, twist, dia, helices) {
    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices) + ramp_width_degrees / 2])
        linear_extrude(height = h, twist = twist, center = true, slices = h > 0 ? h * 2 : 1)
            translate([dia / 2 - slit_depth_mm / 2, 0])
                square([slit_depth_mm, slit_width_mm], center = true);
    }
}

/**
 * Module: RampedSlitKnife
 * Description: Creates a more complex cutting tool for making slits with a ramped lead-in.
 * Arguments: (Same as MultiHelixRamp)
 */
module RampedSlitKnife(h, twist, dia, helices) {
    // Define the 3D shape of the cutting tool using a polyhedron
    // This creates a single ramped cutter.
    cutter_shape_points = [
        // Bottom face (thin start of ramp)
        [dia/2, -slit_width_mm/2, 0],                // 0
        [dia/2,  slit_width_mm/2, 0],                // 1
        [dia/2-0.1,  slit_width_mm/2, 0],            // 2
        [dia/2-0.1, -slit_width_mm/2, 0],            // 3
        // Top face (full size end of ramp)
        [dia/2, -slit_width_mm/2, slit_ramp_length_mm], // 4
        [dia/2,  slit_width_mm/2, slit_ramp_length_mm], // 5
        [dia/2-slit_depth_mm,  slit_width_mm/2, slit_ramp_length_mm], // 6
        [dia/2-slit_depth_mm, -slit_width_mm/2, slit_ramp_length_mm], // 7
    ];
    cutter_shape_faces = [
        [0,1,2,3], [4,5,6,7], [0,1,5,4], [1,2,6,5], [2,3,7,6], [3,0,4,7]
    ];

    for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices) + ramp_width_degrees/2]) {
            // Apply the same helical transformation as the ramp itself
            linear_extrude(height=h, twist=twist, center=true, slices=h > 0 ? h*2 : 1) {
                 // Place the ramp and slit cutters in the 2D space
                 translate([dia/2 - slit_depth_mm, 0, -h/2 + slit_ramp_length_mm/2])
                    polyhedron(points = cutter_shape_points, faces = cutter_shape_faces);

                 translate([dia/2 - slit_depth_mm, 0, -h/2 + slit_ramp_length_mm + slit_open_length_mm/2])
                    cube([slit_depth_mm, slit_width_mm, slit_open_length_mm], center=true);
            }
        }
    }
}

/**
 * Module: CorkscrewSlitKnife
 * Description: Creates cutting tools to separate bins on the `FlatEndScrew` model.
 * Arguments: (Same as FlatEndScrew)
 */
module CorkscrewSlitKnife(twist, depth, num_bins) {
    pitch_mm = twist == 0 ? 1e9 : depth / (twist / 360);
    de = depth / num_bins;
    yrot = 360 * (1 / pitch_mm) * de;
    slit_axial_length_mm = 1.5;

    for (i = [1:num_bins-1]) {
        j = -num_bins/2 + i;
        rotate([0, 0, -yrot * j])
        translate([0, 0, j * de])
            linear_extrude(height = slit_axial_length_mm, center = true, twist = twist / depth * slit_axial_length_mm)
                translate([helix_path_radius_mm, 0, 0])
                    polygon(points = [[0, 0], [helix_profile_radius_mm*2, -helix_profile_radius_mm*2], [helix_profile_radius_mm*2, helix_profile_radius_mm*2]]);
    }
}

// --- Debris Exit Channel Cutters (from corkscrew_filter_v22.scad) ---

/**
 * Module: HelicalChannelCutter
 * Description: Creates a single helical cutting tool that extends radially outward from a cell.
 * Arguments: (Same as MultiHelixRamp)
 */
module HelicalChannelCutter(h, twist, dia, helices) {
     for (i = [0 : helices - 1]) {
        rotate([0, 0, i * (360 / helices) + ramp_width_degrees/2]) {
            linear_extrude(height = h, twist = twist, center=true, slices = h > 0 ? h*2:1) {
                // This cutter starts at the ramp's outer edge and extends far outwards
                // to cut through the hex array frame.
                translate([dia, 0, 0]) {
                    square([dia*2, slit_width_mm], center=true);
                }
            }
        }
    }
}

/**
 * Module: StagedExitChannelCutter
 * Description: Creates staged helical channels that match the filter core stages.
 * Arguments: (Same as StagedHelicalStructure)
 */
module StagedExitChannelCutter(total_h, dia, helices, stages) {
    stage_defs = [ [[0, 0.85]], [[0, 0.35], [0.45, 0.85]], [[0, 0.25], [0.30, 0.58], [0.63, 0.92]] ];
    stages_to_build = stage_defs[stages-1];

    for (stage = stages_to_build) {
        start_z_frac = stage[0];
        end_z_frac = stage[1];
        stage_h = (end_z_frac - start_z_frac) * total_h;
        center_z = (start_z_frac + end_z_frac) / 2 * total_h - total_h / 2;
        revolutions = total_revolutions * (stage_h / total_h);
        twist = 360 * revolutions;

        translate([0,0,center_z]) {
            HelicalChannelCutter(stage_h, twist, dia, helices);
        }
    }
}
