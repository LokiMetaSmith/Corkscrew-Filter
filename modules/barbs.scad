// =============================================================================
// --- Parameterized Barb Module ---
// =============================================================================
// This module replaces the legacy BarbGenerator and specific barb implementations.
// It is fully parameterized to support standard and custom barb geometries.

/**
 * Module: Barb
 * Description: Generates a hose barb.
 *
 * Parameters:
 * hose_id: (float) The inner diameter of the hose (target for the barb root).
 * hose_od: (float) The outer diameter of the hose (determines barb retention).
 * barb_count: (int) Number of barbs.
 * barb_length: (float) Length of a single barb segment.
 * swell: (float) How much the barb flares out (d2 = hose_od + swell).
 * wall_thickness: (float) Thickness of the barb wall (determines internal bore).
 * bore: (bool) If true, creates the internal hole.
 * shell: (bool) If true, creates the solid barb geometry.
 * ezprint: (bool) Alternative print optimization (legacy support).
 */
module Barb(
    hose_id = 5,
    hose_od = 6.5,
    barb_count = 4,
    barb_length = 2,
    swell = 1,
    wall_thickness = 1,
    bore = true,
    shell = true,
    ezprint = false
) {
    id = hose_id - (2 * wall_thickness);

    // We create a standard "Upright" Barb starting at Z=0.

    difference() {
        union() {
            if (shell) {
                for (z = [0 : barb_count - 1]) {
                    translate([0, 0, z * barb_length])
                        cylinder(d1 = hose_od + swell, d2 = hose_od, h = barb_length, $fn = $fn);
                }
                 translate([0, 0, barb_count * barb_length])
                     cylinder(d = hose_od, h = barb_length, $fn = $fn); // Simple tip
            }

            // EZPrint Logic (Legacy)
            if (ezprint && !shell) {
                 difference() {
                    cylinder(d = hose_id + (swell * 3), h = (barb_length * (barb_count + 1)), $fn = $fn);
                    translate([swell, 0, 0])
                        cylinder(d = hose_id + (swell ), h = (barb_length * (barb_count + 1)), $fn = $fn);
                }
            }
        }

        if (bore) {
             translate([0, 0, -0.1])
                cylinder(d = id, h = (barb_length * (barb_count + 1)) + 1, $fn = $fn);
        }
    }
}
