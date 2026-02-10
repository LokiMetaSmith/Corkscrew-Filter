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
 * Module: RampedKnifeShape
 * Description: Helper module to create a single knife with a chamfered leading edge.
 */
module RampedKnifeShape(h, twist, radius, profile_radius) {
    chamfer_h = slit_chamfer_height;
    body_h = h - chamfer_h;
    twist_per_mm = h > 0 ? twist / h : 0;
    chamfer_twist = twist_per_mm * chamfer_h;
    body_twist = twist_per_mm * body_h;

    // Define the 2D profile polygon dimensions
    w = profile_radius * 2;

    // Calculate points for the chamfer polyhedron
    // Bottom points: Scaled by 0.5, at Z=0, translated by radius
    // Top points: Full scale, at Z=chamfer_h, translated by radius, rotated by chamfer_twist

    // Bottom Polygon (Scaled 0.5)
    // Original: [0,0], [w, -w], [w, w]
    // Scaled: [0,0], [0.5w, -0.5w], [0.5w, 0.5w]
    // Translated by [radius, 0]: [radius, 0], [radius+0.5w, -0.5w], [radius+0.5w, 0.5w]
    p0 = [radius, 0, 0];
    p1 = [radius + 0.5*w, -0.5*w, 0];
    p2 = [radius + 0.5*w, 0.5*w, 0];

    // Top Polygon (Full size)
    // Translated by [radius, 0]: [radius, 0], [radius+w, -w], [radius+w, w]
    // Then Rotated by chamfer_twist
    ct_rad = chamfer_twist;

    // Function to rotate point around Z
    function rotZ(p, angle) = [
        p[0]*cos(angle) - p[1]*sin(angle),
        p[0]*sin(angle) + p[1]*cos(angle),
        p[2] + chamfer_h
    ];

    p3 = rotZ([radius, 0, 0], ct_rad);
    p4 = rotZ([radius + w, -w, 0], ct_rad);
    p5 = rotZ([radius + w, w, 0], ct_rad);

    chamfer_points = [p0, p1, p2, p3, p4, p5];
    chamfer_faces = [
        [0, 2, 1], // Bottom
        [3, 4, 5], // Top
        [0, 1, 4, 3], // Side 1
        [1, 2, 5, 4], // Side 2
        [2, 0, 3, 5]  // Side 3
    ];

    // Shift to match center=true of original linear_extrude
    translate([0, 0, -h/2]) {
        // Chamfer Section (Polyhedron)
        polyhedron(points = chamfer_points, faces = chamfer_faces);

        // Main Body Section - Standard helical extrusion
        // Using shifted points to avoid translate() inside linear_extrude which causes issues in WASM
        translate([0, 0, chamfer_h])
        rotate([0, 0, chamfer_twist])
        linear_extrude(height = body_h, twist = body_twist, center = false)
             polygon(points = [[radius, 0], [radius+w, -w], [radius+w, w]]);
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

    for (i = [1:num_bins-1]) {
        j = -num_bins/2 + i;
        rotate([0, 0, -yrot * j])
        translate([0, 0, j * de])
            RampedKnifeShape(slit_axial_length_mm, twist / depth * slit_axial_length_mm, helix_path_radius_mm, helix_profile_radius_mm);
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
